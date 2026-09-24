"""Verification/enable delivery through an existing signed preparation owner."""
import asyncio
from dataclasses import dataclass
from uuid import UUID
from aos_api.tenant_scope import TenantScope
from .consumer_connection import consumer_connection
from .lifecycle_store import _values,RuntimeConflict
from .outbox_store import RuntimeOutboxStore
from .preparation_worker import PreparedJob
from .preparation_owner import _observe
from .journaled_session import _settle
from .configuration_request import load_enable_target


async def _settled(awaitable):
    result,cancelled=await _settle(asyncio.create_task(awaitable))
    if cancelled:raise asyncio.CancelledError
    return result


@dataclass(frozen=True)
class OwnedDeliveryResult:
    operation_id: UUID
    operation_status: str
    delivery_status: str


class OwnedControlConsumer:
    def __init__(self,*,connect,job,kind,org_id,project_id,host_lease=None):
        scope=TenantScope(org_id,project_id)
        if not isinstance(job,PreparedJob) or job.tenant_scope!=scope:
            raise ValueError('owned consumer requires exact PreparedJob scope')
        if kind not in ('runtime-verify','enable') or not callable(connect):
            raise ValueError('trusted owned consumer inputs required')
        self.scope=dict(org_id=org_id,project_id=project_id)
        if host_lease is not None:
            from .host_lease import OptInHostLease
            if type(host_lease) is not OptInHostLease or host_lease.scope != scope:
                raise TypeError('exact OwnedControlConsumer Host lease scope required')
        self.host_lease=host_lease
        self.installation=UUID(str(job.plan.installation_id))
        self.connect,self.job,self.kind=connect,job,kind
        self.outbox=RuntimeOutboxStore()
        self._task=None

    def _current(self,conn,operation):
        row=conn.execute('''SELECT installation_id,kind,status,phase,revision
            FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s''',
            (self.scope['org_id'],self.scope['project_id'],operation)).fetchone()
        if row is None:raise LookupError('owned operation missing')
        installation,kind,status,phase,revision=_values(row,('installation_id','kind','status','phase','revision'))
        if installation!=self.installation or kind!=self.kind:
            raise RuntimeConflict('owned operation routing changed')
        return status,phase,revision

    def _claim(self):
        fence=self.host_lease.fence_in_transaction if self.host_lease is not None else None
        with consumer_connection(self.connect,self.scope,fence=fence) as conn:
            return self.outbox.claim(conn,**self.scope,operation_kind=self.kind,installation_id=self.installation)

    def _read(self,lease):
        with consumer_connection(self.connect,self.scope) as conn:
            status,phase,revision=self._current(conn,lease.operation_id)
            matching=True
            if self.kind=='enable' and status not in ('succeeded','failed','cancelled') and phase=='accepted':
                target=load_enable_target(conn,**self.scope,operation_id=lease.operation_id)
                matching=UUID(target.generation)==self.job.plan.generation
            return status,phase,revision,matching

    def _finish(self,lease):
        fence=self.host_lease.fence_in_transaction if self.host_lease is not None else None
        with consumer_connection(self.connect,self.scope,fence=fence) as conn:
            status,_,_=self._current(conn,lease.operation_id)
            terminal=status in ('succeeded','failed','cancelled')
            if terminal:self.outbox.ack(conn,**self.scope,lease=lease)
            else:self.outbox.retry(conn,**self.scope,lease=lease)
            return OwnedDeliveryResult(lease.operation_id,status,'acknowledged' if terminal else 'deferred')

    async def _run(self):
        lease=await _settled(asyncio.to_thread(self._claim))
        if lease is None:return None
        status,phase,revision,matching=await _settled(asyncio.to_thread(self._read,lease))
        if matching and status not in ('succeeded','failed','cancelled') and phase=='accepted':
            command=self.job.verify if self.kind=='runtime-verify' else self.job.enable
            await _settled(command(operation_id=lease.operation_id,expected_revision=revision))
        return await _settled(asyncio.to_thread(self._finish,lease))

    async def run_once(self):
        if self._task is not None and not self._task.done():
            raise RuntimeError('owned consumer work in progress')
        # No await between admission and registration. Request cancellation only
        # cancels its shield; the host must wait_idle before stopping the owner.
        self._task=asyncio.create_task(self._run())
        self._task.add_done_callback(_observe)
        return await asyncio.shield(self._task)

    async def wait_idle(self):
        if self._task is None:return None
        return await asyncio.shield(self._task)
