"""Trusted in-process worker composition; durable dispatch/restart remains separate."""
import asyncio
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
import re
import traceback

from .journaled_session import _settle
from .lifecycle_store import RuntimeOperationStore, RuntimeConflict, _values
from .oci_driver import CleanupUncertainError
from .preparation_commit import commit_prepared
from .preparation_owner import PreparationOwner, _observe
from .preparation_plan import claim_preparation, rehydrate_current_preparation
from .reconciler import ResourceJournal
from .signed_session import open_signed_session, open_existing_signed_session
from .verification_commit import commit_verified
from .enable_commit import commit_enabled
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.logging_facade import get_logger
from aos_api.tenant_scope import TenantScope

_LOG = get_logger("aos-api.extension-runtime.preparation-worker")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_SAFE_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,79}$")


def _safe_failure_trace(error):
    """Bounded code locations only; never exception values or frame locals."""
    chain, seen = [], set()
    while error is not None and id(error) not in seen and len(chain) < 4:
        seen.add(id(error))
        name = type(error).__name__
        frames = []
        for frame in traceback.extract_tb(error.__traceback__)[-8:]:
            try:
                path = str(Path(frame.filename).relative_to(_REPOSITORY_ROOT))
            except ValueError:
                path = "<external>"
            function = frame.name if _SAFE_SYMBOL.fullmatch(frame.name) else "<unknown>"
            frames.append((path, function, frame.lineno))
        chain.append({"type": name if _SAFE_SYMBOL.fullmatch(name) else "UnknownError",
                      "frames": frames})
        error = error.__cause__ if error.__cause__ is not None else error.__context__
    return chain


class PreparedJob:
    def __init__(self, plan, owner, finalize, verify=None, enable=None, *, tenant_scope=None,
                 renew=None, already_verified=False):
        self.plan=plan
        self._tenant_scope=tenant_scope
        self._owner=owner
        self._stopping=False
        self._finalize=finalize
        self._verify=verify
        self._enable=enable
        self._renew=renew
        if type(already_verified) is not bool:raise TypeError('exact verified state required')
        self._verified=already_verified
        self._next_renewal=0.0
        self._closed=asyncio.create_task(self._watch())
        self._closed.add_done_callback(_observe)

    @property
    def tenant_scope(self):
        return self._tenant_scope

    async def _watch(self):
        code='PREPARATION_EXECUTION_FAILED'
        original=None
        try:
            await self._owner.wait_closed()
        except BaseException as exc:
            original=exc
            if isinstance(exc,TimeoutError):code='PREPARATION_EXPIRED'
            if not self._stopping and not isinstance(exc, asyncio.CancelledError):
                try:
                    _LOG.error("preparation_failed_safe_trace=%s", _safe_failure_trace(exc))
                except Exception:
                    pass  # Diagnostics must never alter resource finalization.
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

    async def invoke_selected_once(self, *, package_id, package_hash, operation, payload):
        if (
            type(package_id) is not str
            or not package_id
            or type(package_hash) is not str
            or not package_hash
            or type(operation) is not str
            or not operation
            or type(payload) is not dict
        ):
            raise ValueError("exact installed package invocation required")
        matches = tuple(
            index
            for index, member in enumerate(self.plan.members)
            if member.selected.id == package_id
            and member.selected.content_hash == package_hash
        )
        if len(matches) != 1:
            raise PermissionError("package is not owned by this live preparation")
        return await self._owner.invoke_once(matches[0], operation, payload)

    async def verify(self, *, operation_id, expected_revision):
        if self._verify is None:
            raise RuntimeError('current verification conditions reader required')
        async def commit(observed):
            result,cancelled=await _settle(asyncio.create_task(asyncio.to_thread(
                self._verify,operation_id,expected_revision,observed)))
            if cancelled:raise asyncio.CancelledError
            return result
        result = await self._owner.verify(commit)
        self._verified = True
        return result

    async def renew_if_due(self):
        if not self._verified or self._renew is None:
            return None
        now = asyncio.get_running_loop().time()
        if now < self._next_renewal:
            return None
        async def commit(observed):
            result, cancelled = await _settle(asyncio.create_task(asyncio.to_thread(self._renew, observed)))
            if cancelled: raise asyncio.CancelledError
            return result
        expires = await self._owner.renew(commit)
        self._next_renewal = asyncio.get_running_loop().time() + 60
        return expires

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
                 configuration_authorize=None, check_enable_permission=None,
                 read_member_artifact=None):
        self.connect=connect
        self.driver=driver
        self.store=installation_store
        self.revalidator=revalidator
        self.permission=check_current_permission
        self.load_record=load_record
        self.read_artifact=read_artifact
        self.read_member_artifact=read_member_artifact
        self.policy=policy
        self.platform=platform
        self.conditions=check_current_conditions
        self.verification_permission=check_verification_permission
        self.configuration_authorize=configuration_authorize
        self.enable_permission=check_enable_permission

    def _artifact_reader(self, member):
        if callable(self.read_member_artifact):
            return lambda path,limit:self.read_member_artifact(member.selected,path,limit)
        return self.read_artifact

    @contextmanager
    def _connection(self, scope):
        with self.connect() as conn:
            with conn.transaction():
                apply_asset_transaction_scope(conn, **scope)
                row=conn.execute('SELECT current_user AS role').fetchone()
                if _values(row,('role',))[0]!='aos_runtime':
                    raise RuntimeConflict('worker requires adopted runtime control role')
                yield conn

    def _read_health_clock(self,scope):
        with self._connection(scope) as conn:
            return _values(conn.execute('SELECT clock_timestamp() AS now').fetchone(),('now',))[0]

    def _verify(self,scope,plan,operation_id,expected_revision,observed):
        with self._connection(scope) as conn:
            with conn.transaction():
                return commit_verified(conn,installation_store=self.store,revalidator=self.revalidator,
                    check_current_permission=self.verification_permission,check_current_conditions=self.conditions,
                    **scope,operation_id=operation_id,expected_revision=expected_revision,
                    preparation_operation_id=plan.operation_id,generation=plan.generation,
                    health_checked_at=observed)

    def _renew(self, scope, plan, observed):
        from .lease_renewal import renew_verified_lease
        with self._connection(scope) as conn:
            with conn.transaction():
                return renew_verified_lease(conn, installation_store=self.store, revalidator=self.revalidator,
                    check_current_permission=self.permission, check_current_conditions=self.conditions,
                    **scope, installation_id=plan.installation_id, operation_id=plan.operation_id,
                    generation=plan.generation, health_checked_at=observed)

    def _claim(self,scope,operation_id,expected_revision):
        with self._connection(scope) as conn:
            with conn.transaction():
                return claim_preparation(conn,installation_store=self.store,revalidator=self.revalidator,
                    check_current_permission=self.permission,**scope,operation_id=operation_id,
                    expected_revision=expected_revision,engine_context=self.driver.context)

    def _rehydrate(self,scope,installation_id):
        with self._connection(scope) as conn:
            with conn.transaction():
                return rehydrate_current_preparation(conn,installation_store=self.store,
                    revalidator=self.revalidator,check_current_permission=self.permission,
                    check_current_conditions=self.conditions,**scope,installation_id=installation_id,
                    engine_context=self.driver.context)

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
                if phase=='succeeded':
                    from .committed_cleanup import settle_committed_cleanup
                    settle_committed_cleanup(conn,**scope,operation_id=plan.operation_id,expected_revision=revision)
                    return
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
                        policy=self.policy,checked_at=datetime.now(timezone.utc),read_artifact=self._artifact_reader(member),
                        platform=self.platform) as session:
                        yield session
                return open_member
            async def commit():
                result,was_cancelled=await _settle(asyncio.create_task(asyncio.to_thread(self._commit,scope,plan)))
                if was_cancelled:raise asyncio.CancelledError
                return result
            async def health_clock():
                observed,was_cancelled=await _settle(asyncio.create_task(asyncio.to_thread(self._read_health_clock,scope)))
                if was_cancelled:raise asyncio.CancelledError
                return observed
            owner=PreparationOwner([factory(member) for member in plan.members],commit,
                lease_seconds=remaining,health_clock=health_clock)
            verify=(lambda operation_id,revision,observed:self._verify(scope,plan,operation_id,revision,observed)) if callable(self.conditions) and callable(self.verification_permission) else None
            enable=(lambda operation_id,revision,observed:self._enable(scope,plan,operation_id,revision,observed)) if callable(self.conditions) and callable(self.configuration_authorize) and callable(self.enable_permission) else None
            return PreparedJob(plan,owner,lambda code:self._finalize(scope,plan,code),verify,enable,
                tenant_scope=TenantScope(**scope),
                renew=(lambda observed:self._renew(scope,plan,observed)) if verify is not None else None)
        except BaseException:
            await _settle(asyncio.create_task(asyncio.to_thread(self._finalize,scope,plan,'PREPARATION_STOPPED')))
            raise

    async def resume_current(self, *, org_id, project_id, installation_id):
        scope=dict(org_id=org_id,project_id=project_id)
        plan,cancelled=await _settle(asyncio.create_task(asyncio.to_thread(
            self._rehydrate,scope,installation_id)))
        try:
            if cancelled:raise asyncio.CancelledError
            remaining=min(180,(plan.deadline-datetime.now(timezone.utc)).total_seconds())
            if remaining<=0:raise TimeoutError('rehydration lease expired')
            def factory(member):
                if member.container_id is None:
                    raise RuntimeConflict('rehydration container identity required')
                @asynccontextmanager
                async def open_member():
                    record=await asyncio.to_thread(self.load_record,member.selected)
                    async with open_existing_signed_session(driver=self.driver,
                            connect=lambda:self._connection(scope),**scope,
                            resource_id=member.intent.resource_id,
                            container_id=member.container_id,record=record,selected=member.selected,
                            policy=self.policy,checked_at=datetime.now(timezone.utc),
                            read_artifact=self._artifact_reader(member),platform=self.platform) as session:
                        yield session
                return open_member
            async def committed():return None
            async def health_clock():
                observed,was_cancelled=await _settle(asyncio.create_task(asyncio.to_thread(
                    self._read_health_clock,scope)))
                if was_cancelled:raise asyncio.CancelledError
                return observed
            owner=PreparationOwner([factory(member) for member in plan.members],committed,
                lease_seconds=remaining,health_clock=health_clock,already_verified=True)
            return PreparedJob(plan,owner,lambda code:self._finalize(scope,plan,code),
                tenant_scope=TenantScope(**scope),
                renew=lambda observed:self._renew(scope,plan,observed),already_verified=True)
        except BaseException:
            await _settle(asyncio.create_task(asyncio.to_thread(
                self._finalize,scope,plan,'REHYDRATION_STOPPED')))
            raise
