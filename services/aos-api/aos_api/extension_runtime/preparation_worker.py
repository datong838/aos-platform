"""Trusted in-process worker composition; durable dispatch/restart remains separate."""
import asyncio
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone

from .journaled_session import _settle
from .lifecycle_store import RuntimeOperationStore, RuntimeConflict, _values
from .oci_driver import CleanupUncertainError
from .preparation_commit import commit_prepared
from .preparation_owner import PreparationOwner, _observe
from .preparation_plan import claim_preparation
from .reconciler import ResourceJournal
from .signed_session import open_signed_session
from .verification_commit import commit_verified
from .enable_commit import commit_enabled
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope


class PreparedJob:
    def __init__(self, plan, owner, finalize, verify=None, enable=None):
        self.plan=plan
        self._owner=owner
        self._stopping=False
        self._finalize=finalize
        self._verify=verify
        self._enable=enable
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

    async def check_health(self):
        try:
            await self._owner.check_health()
        except BaseException as original:
            try:
                await self.stop()
            except BaseException as stopping_error:
                if isinstance(original,CleanupUncertainError) and original is not stopping_error:
                    raise original from stopping_error
                raise
            raise

    async def verify(self, *, operation_id, expected_revision):
        if self._verify is None:
            raise RuntimeError('current verification conditions reader required')
        async def commit(observed):
            result,cancelled=await _settle(asyncio.create_task(asyncio.to_thread(
                self._verify,operation_id,expected_revision,observed)))
            if cancelled:raise asyncio.CancelledError
            return result
        return await self._owner.verify(commit)

    async def enable(self, *, operation_id, expected_revision):
        if self._enable is None:
            raise RuntimeError('current enable configuration and permission readers required')
        async def commit(observed):
            result,cancelled=await _settle(asyncio.create_task(asyncio.to_thread(
                self._enable,operation_id,expected_revision,observed)))
            if cancelled:raise asyncio.CancelledError
            return result
        return await self._owner.control(commit)

    async def stop(self):
        self._stopping=True
        try:
            await self._owner.stop()
        finally:
            _,cancelled=await _settle(self._closed)
            if cancelled:raise asyncio.CancelledError


class PreparationWorker:
    def __init__(self, *, connect, driver, installation_store, revalidator,
                 check_current_permission, load_record, read_artifact, policy, platform,
                 check_current_conditions=None, check_verification_permission=None,
                 configuration_authorize=None, check_enable_permission=None):
        self.connect=connect
        self.driver=driver
        self.store=installation_store
        self.revalidator=revalidator
        self.permission=check_current_permission
        self.load_record=load_record
        self.read_artifact=read_artifact
        self.policy=policy
        self.platform=platform
        self.conditions=check_current_conditions
        self.verification_permission=check_verification_permission
        self.configuration_authorize=configuration_authorize
        self.enable_permission=check_enable_permission

    @contextmanager
    def _connection(self, scope):
        with self.connect() as conn:
            with conn.transaction():
                apply_asset_transaction_scope(conn, **scope)
                row=conn.execute('SELECT current_user AS role').fetchone()
                if _values(row,('role',))[0]!='aos_runtime':
                    raise RuntimeConflict('worker requires adopted runtime control role')
                yield conn

    def _verify(self,scope,plan,operation_id,expected_revision,observed):
        with self._connection(scope) as conn:
            with conn.transaction():
                return commit_verified(conn,installation_store=self.store,revalidator=self.revalidator,
                    check_current_permission=self.verification_permission,check_current_conditions=self.conditions,
                    **scope,operation_id=operation_id,expected_revision=expected_revision,
                    preparation_operation_id=plan.operation_id,generation=plan.generation,
                    health_checked_at=observed)

    def _claim(self,scope,operation_id,expected_revision):
        with self._connection(scope) as conn:
            with conn.transaction():
                return claim_preparation(conn,installation_store=self.store,revalidator=self.revalidator,
                    check_current_permission=self.permission,**scope,operation_id=operation_id,
                    expected_revision=expected_revision,engine_context=self.driver.context)

    def _enable(self,scope,plan,operation_id,expected_revision,observed):
        with self._connection(scope) as conn:
            return commit_enabled(conn,installation_store=self.store,revalidator=self.revalidator,
                check_current_permission=self.enable_permission,check_current_conditions=self.conditions,
                authorize=self.configuration_authorize,**scope,operation_id=operation_id,
                expected_revision=expected_revision,preparation_operation_id=plan.operation_id,
                generation=plan.generation,health_checked_at=observed)

    def _commit(self,scope,plan):
        with self._connection(scope) as conn:
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
        with self._connection(scope) as conn:
            with conn.transaction():
                for member in plan.members:
                    row=conn.execute('''SELECT create_claimed_at,observed_release FROM extension_runtime_resource_lease
                        WHERE org_id=%s AND project_id=%s AND resource_id=%s''',
                        (scope['org_id'],scope['project_id'],member.intent.resource_id)).fetchone()
                    if row is None:raise LookupError('resource not found')
                    claimed,released=_values(row,('create_claimed_at','observed_release'))
                    if claimed is None and not released:
                        ResourceJournal().cancel_unclaimed(conn,**scope,intent=member.intent)
        with self._connection(scope) as conn:
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
                    async with open_signed_session(driver=self.driver,connect=lambda:self._connection(scope),**scope,
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
            verify=(lambda operation_id,revision,observed:self._verify(scope,plan,operation_id,revision,observed)) if callable(self.conditions) and callable(self.verification_permission) else None
            enable=(lambda operation_id,revision,observed:self._enable(scope,plan,operation_id,revision,observed)) if callable(self.conditions) and callable(self.configuration_authorize) and callable(self.enable_permission) else None
            return PreparedJob(plan,owner,lambda code:self._finalize(scope,plan,code),verify,enable)
        except BaseException:
            await _settle(asyncio.create_task(asyncio.to_thread(self._finalize,scope,plan,'PREPARATION_STOPPED')))
            raise
