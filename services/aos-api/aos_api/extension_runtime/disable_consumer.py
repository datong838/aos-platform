"""Concrete single-message disable consumer. No generic execution callback."""
from dataclasses import dataclass
from uuid import UUID

from aos_api.tenant_scope import TenantScope
from .disable_executor import RuntimeDisableExecutor
from .outbox_store import RuntimeOutboxStore
from .lifecycle_store import _values,RuntimeConflict
from .consumer_connection import consumer_connection


@dataclass(frozen=True)
class DisableDeliveryResult:
    operation_id: UUID
    operation_status: str
    delivery_status: str


class RuntimeDisableConsumer:
    def __init__(self,*,connect,installation_store,check_current_permission,check_drained):
        self.connect=connect
        self.executor=RuntimeDisableExecutor(connect=connect,installation_store=installation_store,
            check_current_permission=check_current_permission,check_drained=check_drained)
        self.outbox=RuntimeOutboxStore()

    def _connection(self,scope):
        return consumer_connection(self.connect,scope)

    def _current(self,conn,scope,operation):
        row=conn.execute('''SELECT kind,status,phase,revision FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND operation_id=%s''',
            (scope['org_id'],scope['project_id'],operation)).fetchone()
        if row is None:raise LookupError('disable operation missing')
        kind,status,phase,revision=_values(row,('kind','status','phase','revision'))
        if kind!='disable':raise RuntimeConflict('consumer operation kind changed')
        return status,phase,revision

    def run_once(self,*,org_id,project_id):
        TenantScope(org_id,project_id)
        scope=dict(org_id=org_id,project_id=project_id)
        with self._connection(scope) as conn:
            lease=self.outbox.claim(conn,**scope,operation_kind='disable')
        if lease is None:return None
        with self._connection(scope) as conn:
            status,phase,revision=self._current(conn,scope,lease.operation_id)
        if status not in ('succeeded','failed','cancelled') and phase in ('accepted','fencing'):
            # Current permissions/CAS/drain are checked again by the concrete
            # executor; errors propagate, and a later delivery reads current state.
            self.executor.execute(**scope,operation_id=lease.operation_id,expected_revision=revision)
        with self._connection(scope) as conn:
            status,_,_=self._current(conn,scope,lease.operation_id)
            if status in ('succeeded','failed','cancelled'):
                self.outbox.ack(conn,**scope,lease=lease)
                return DisableDeliveryResult(lease.operation_id,status,'acknowledged')
            self.outbox.retry(conn,**scope,lease=lease)
            return DisableDeliveryResult(lease.operation_id,status,'deferred')
