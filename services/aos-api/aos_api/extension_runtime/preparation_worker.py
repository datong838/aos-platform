"""Trusted in-process worker composition; durable dispatch/restart remains separate."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from .journaled_session import _settle
from .lifecycle_store import RuntimeOperationStore, RuntimeConflict, _values
from .oci_driver import CleanupUncertainError
from .preparation_commit import commit_prepared
from .preparation_owner import PreparationOwner, _observe
from .preparation_plan import claim_preparation
from .reconciler import ResourceJournal
from .signed_session import open_signed_session


class PreparedJob:
    def __init__(self, plan, owner, finalize):
        self.plan=plan
        self._owner=owner
        self._stopping=False
        self._finalize=finalize
        self._closed=asyncio.create_task(self._watch())
        self._closed.add_done_callback(_observe)

    async def _watch(self):
        code='PREPARATION_EXECUTION_FAILED'
        original=None
        try:
            await self._owner.wait_closed()
        except BaseException as exc:
            original=exc
            if isinstance(exc,TimeoutError):code='PREPARATION_EXPIRED'
        if self._stopping:code='PREPARATION_STOPPED'
        try:
            _,cancelled=await _settle(asyncio.create_task(asyncio.to_thread(self._finalize,code)))
            if cancelled:raise asyncio.CancelledError
        except BaseException as finalization_error:
            if isinstance(original,CleanupUncertainError):
                raise original from finalization_error
            raise
        if original is not None:raise original

    async def prepared(self):
        try:
            return await self._owner.prepared()
        except asyncio.CancelledError:
            # A request disappearing is not a worker stop command.
            raise
        except Exception:
            await self.wait_closed()
            raise

    async def wait_closed(self):
        return await asyncio.shield(self._closed)

    async def stop(self):
        self._stopping=True
        try:
            await self._owner.stop()
        finally:
            _,cancelled=await _settle(self._closed)
            if cancelled:raise asyncio.CancelledError


class PreparationWorker:
    def __init__(self, *, connect, driver, installation_store, revalidator,
                 check_current_permission, load_record, read_artifact, policy, platform):
        self.connect=connect
        self.driver=driver
        self.store=installation_store
        self.revalidator=revalidator
        self.permission=check_current_permission
        self.load_record=load_record
        self.read_artifact=read_artifact
        self.policy=policy
        self.platform=platform

    def _claim(self,scope,operation_id,expected_revision):
        with self.connect() as conn:
            with conn.transaction():
                return claim_preparation(conn,installation_store=self.store,revalidator=self.revalidator,
                    check_current_permission=self.permission,**scope,operation_id=operation_id,
                    expected_revision=expected_revision,engine_context=self.driver.context)

    def _commit(self,scope,plan):
        with self.connect() as conn:
            with conn.transaction():
                row=conn.execute('''SELECT revision FROM extension_runtime_operation
                    WHERE org_id=%s AND project_id=%s AND operation_id=%s''',
                    (scope['org_id'],scope['project_id'],plan.operation_id)).fetchone()
                if row is None:raise LookupError('operation not found')
                registered=RuntimeOperationStore().advance(conn,**scope,operation_id=plan.operation_id,
                    expected_revision=_values(row,('revision',))[0],phase='registered')
                return commit_prepared(conn,installation_store=self.store,revalidator=self.revalidator,
                    check_current_permission=self.permission,**scope,operation_id=plan.operation_id,
                    expected_revision=registered.revision,generation=plan.generation)

    def _finalize(self,scope,plan,code):
        # Release unissued permits even when another member remains uncertain.
        # Claimed permits are never inferred absent from a missing container ID.
        with self.connect() as conn:
            with conn.transaction():
                for member in plan.members:
                    row=conn.execute('''SELECT create_claimed_at,observed_release FROM extension_runtime_resource_lease
                        WHERE org_id=%s AND project_id=%s AND resource_id=%s''',
                        (scope['org_id'],scope['project_id'],member.intent.resource_id)).fetchone()
                    if row is None:raise LookupError('resource not found')
                    claimed,released=_values(row,('create_claimed_at','observed_release'))
                    if claimed is None and not released:
                        ResourceJournal().cancel_unclaimed(conn,**scope,intent=member.intent)
        with self.connect() as conn:
            with conn.transaction():
                row=conn.execute('''SELECT revision,phase,status FROM extension_runtime_operation
                    WHERE org_id=%s AND project_id=%s AND operation_id=%s''',
                    (scope['org_id'],scope['project_id'],plan.operation_id)).fetchone()
                if row is None:raise LookupError('operation not found')
                revision,phase,status=_values(row,('revision','phase','status'))
                if (phase,status)==('succeeded','succeeded'):return
                if phase=='succeeded':raise RuntimeConflict('committed preparation requires cleanup reconciliation')
                RuntimeOperationStore().fail_uncommitted_preparation(conn,**scope,
                    operation_id=plan.operation_id,expected_revision=revision,failure_code=code)

    async def start(self, *, org_id, project_id, operation_id, expected_revision):
        scope=dict(org_id=org_id,project_id=project_id)
        plan,cancelled=await _settle(asyncio.create_task(asyncio.to_thread(self._claim,scope,operation_id,expected_revision)))
        try:
            if cancelled:raise asyncio.CancelledError
            remaining=min(300,(plan.deadline-datetime.now(timezone.utc)).total_seconds())
            if remaining<=0:raise TimeoutError('preparation lease expired')
            def factory(member):
                @asynccontextmanager
                async def open_member():
                    record=await asyncio.to_thread(self.load_record,member.selected)
                    async with open_signed_session(driver=self.driver,connect=self.connect,**scope,
                        resource_id=member.intent.resource_id,record=record,selected=member.selected,
                        policy=self.policy,checked_at=datetime.now(timezone.utc),read_artifact=self.read_artifact,
                        platform=self.platform) as session:
                        yield session
                return open_member
            async def commit():
                result,was_cancelled=await _settle(asyncio.create_task(asyncio.to_thread(self._commit,scope,plan)))
                if was_cancelled:raise asyncio.CancelledError
                return result
            owner=PreparationOwner([factory(member) for member in plan.members],commit,lease_seconds=remaining)
            return PreparedJob(plan,owner,lambda code:self._finalize(scope,plan,code))
        except BaseException:
            await _settle(asyncio.create_task(asyncio.to_thread(self._finalize,scope,plan,'PREPARATION_STOPPED')))
            raise
