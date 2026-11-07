"""Single-installation preparation delivery; retains, never recreates, its owner."""
import asyncio
from dataclasses import dataclass
from uuid import UUID
from aos_api.tenant_scope import TenantScope
from .consumer_connection import consumer_connection
from .lifecycle_store import _values,RuntimeConflict
from .outbox_store import RuntimeOutboxStore
from .owned_control_consumer import _settled
from .preparation_owner import _observe
from .preparation_worker import PreparationWorker,PreparedJob
from .oci_driver import CleanupUncertainError


@dataclass(frozen=True)
class PreparationDeliveryResult:
    operation_id: UUID
    operation_status: str
    delivery_status: str


class PreparationConsumer:
    def __init__(self,*,connect,worker,installation_id,org_id,project_id,live_directory=None,
                 rehydrate=False,host_lease=None):
        self.tenant_scope=TenantScope(org_id,project_id)
        if not callable(connect) or not isinstance(worker,PreparationWorker):
            raise ValueError('trusted preparation worker and connection required')
        if live_directory is not None:
            from .live_job_directory import LivePreparedJobDirectory
            if type(live_directory) is not LivePreparedJobDirectory:
                raise TypeError('exact live PreparedJob directory required')
        self.scope=dict(org_id=org_id,project_id=project_id)
        self.installation=UUID(str(installation_id))
        self.connect,self.worker=connect,worker
        if host_lease is not None:
            from .host_lease import OptInHostLease
            if type(host_lease) is not OptInHostLease or host_lease.scope != self.tenant_scope:
                raise TypeError('exact PreparationConsumer Host lease scope required')
        self.host_lease=host_lease
        self.live_directory=live_directory
        if type(rehydrate) is not bool:raise TypeError('exact rehydrate mode required')
        self.rehydrate=rehydrate
        self.outbox=RuntimeOutboxStore()
        self._task=self._job=self._close_task=None
        self._closing=False

    @property
    def job(self):return self._job

    def _current(self,conn,operation):
        row=conn.execute('''SELECT installation_id,kind,status,phase,revision FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND operation_id=%s''',
            (self.scope['org_id'],self.scope['project_id'],operation)).fetchone()
        if row is None:raise LookupError('preparation operation missing')
        installation,kind,status,phase,revision=_values(row,('installation_id','kind','status','phase','revision'))
        if installation!=self.installation or kind!='runtime-apply':
            raise RuntimeConflict('preparation delivery routing changed')
        return status,phase,revision

    def _claim(self):
        fence=self.host_lease.fence_in_transaction if self.host_lease is not None else None
        with consumer_connection(self.connect,self.scope,fence=fence) as conn:
            return self.outbox.claim(conn,**self.scope,operation_kind='runtime-apply',installation_id=self.installation)

    def _read(self,lease):
        with consumer_connection(self.connect,self.scope) as conn:
            return self._current(conn,lease.operation_id)

    def _finish(self,lease):
        fence=self.host_lease.fence_in_transaction if self.host_lease is not None else None
        with consumer_connection(self.connect,self.scope,fence=fence) as conn:
            status,_,_=self._current(conn,lease.operation_id)
            terminal=status in ('succeeded','failed','cancelled')
            if terminal:self.outbox.ack(conn,**self.scope,lease=lease)
            else:self.outbox.retry(conn,**self.scope,lease=lease)
            return PreparationDeliveryResult(lease.operation_id,status,'acknowledged' if terminal else 'deferred')

    async def _start_owned(self,operation,revision):
        job=await self.worker.start(**self.scope,operation_id=operation,expected_revision=revision)
        if not isinstance(job,PreparedJob):raise RuntimeConflict('worker did not return PreparedJob')
        # Register BEFORE returning to a cancellation point. The host must retain
        # even a mismatched job so its original cleanup can be awaited.
        self._job=job
        if (job.tenant_scope!=self.tenant_scope or job.plan.installation_id!=self.installation
                or job.plan.operation_id!=operation):
            await _settled(job.stop())
            raise RuntimeConflict('prepared owner routing mismatch')
        if self.live_directory is not None:
            try:self.live_directory.register(job)
            except BaseException:
                await _settled(job.stop())
                raise
        return job

    async def _run(self):
        if self.rehydrate:
            if self._job is None:
                job=await _settled(self.worker.resume_current(**self.scope,
                    installation_id=self.installation))
                if not isinstance(job,PreparedJob):
                    raise RuntimeConflict('worker did not return rehydrated PreparedJob')
                self._job=job
                if (job.tenant_scope!=self.tenant_scope
                        or job.plan.installation_id!=self.installation):
                    await _settled(job.stop())
                    raise RuntimeConflict('rehydrated owner routing mismatch')
                if self.live_directory is not None:
                    try:self.live_directory.register(job)
                    except BaseException:
                        await _settled(job.stop())
                        raise
                await _settled(job.prepared())
            return None
        lease=await _settled(asyncio.to_thread(self._claim))
        if lease is None:return None
        status,phase,revision=await _settled(asyncio.to_thread(self._read,lease))
        if status=='accepted' and phase=='accepted' and self._job is None:
            job=await _settled(self._start_owned(lease.operation_id,revision))
            await _settled(job.prepared())
        return await _settled(asyncio.to_thread(self._finish,lease))

    async def run_once(self):
        if self._closing:raise RuntimeError('preparation consumer is closed')
        if self._task is not None and not self._task.done():raise RuntimeError('preparation consumption in progress')
        self._task=asyncio.create_task(self._run())
        self._task.add_done_callback(_observe)
        return await asyncio.shield(self._task)

    async def wait_idle(self):
        if self._task is None:return None
        return await asyncio.shield(self._task)

    async def _close(self):
        original=None
        try:await _settled(self.wait_idle())
        except BaseException as exc:original=exc
        try:
            if self._job is not None:await _settled(self._job.stop())
        except BaseException as cleanup:
            if isinstance(original,CleanupUncertainError) and original is not cleanup:
                raise original from cleanup
            raise
        finally:
            if self._job is not None and self.live_directory is not None:
                self.live_directory.unregister(self._job)
        if original is not None:raise original

    async def stop(self):
        self._closing=True
        if self._close_task is None:
            self._close_task=asyncio.create_task(self._close())
            self._close_task.add_done_callback(_observe)
        return await asyncio.shield(self._close_task)
