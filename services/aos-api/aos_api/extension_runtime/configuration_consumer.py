"""Concrete configuration delivery: commit fence before attempting drain."""
from dataclasses import dataclass
from uuid import UUID
from aos_api.tenant_scope import TenantScope
from .consumer_connection import consumer_connection
from .configuration_commit import begin_configuration,commit_configuration
from .lifecycle_store import _values,RuntimeConflict
from .outbox_store import RuntimeOutboxStore


@dataclass(frozen=True)
class ConfigurationDeliveryResult:
    operation_id: UUID
    operation_status: str
    delivery_status: str


class ConfigurationConsumer:
    def __init__(self,*,connect,authorize,check_drained,host_lease=None):
        if not all(callable(value) for value in (connect,authorize,check_drained)):
            raise ValueError('trusted configuration consumers require current readers')
        self.connect,self.authorize,self.check_drained=connect,authorize,check_drained
        if host_lease is not None:
            from .host_lease import OptInHostLease
            if type(host_lease) is not OptInHostLease:
                raise TypeError('exact ConfigurationConsumer Host lease required')
        self.host_lease=host_lease
        self.outbox=RuntimeOutboxStore()

    def _connection(self,scope):
        fence=self.host_lease.fence_in_transaction if self.host_lease is not None else None
        return consumer_connection(self.connect,scope,fence=fence)

    def _current(self,conn,scope,operation):
        row=conn.execute('''SELECT kind,status,phase,revision FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND operation_id=%s''',
            (scope['org_id'],scope['project_id'],operation)).fetchone()
        if row is None:raise LookupError('configuration operation missing')
        kind,status,phase,revision=_values(row,('kind','status','phase','revision'))
        if kind!='configure':raise RuntimeConflict('configuration routing changed')
        return status,phase,revision

    def run_once(self,*,org_id,project_id):
        TenantScope(org_id,project_id)
        scope=dict(org_id=org_id,project_id=project_id)
        with self._connection(scope) as conn:
            lease=self.outbox.claim(conn,**scope,operation_kind='configure')
        if lease is None:return None
        with self._connection(scope) as conn:
            status,phase,revision=self._current(conn,scope,lease.operation_id)
        if status not in ('succeeded','failed','cancelled'):
            if phase=='accepted':
                with self._connection(scope) as conn:
                    fenced=begin_configuration(conn,**scope,operation_id=lease.operation_id,
                        expected_revision=revision,authorize=self.authorize)
                # No drain code runs until the preceding context committed.
                phase,revision='fencing',fenced.revision
            if phase=='fencing':
                with self._connection(scope) as conn:
                    commit_configuration(conn,**scope,operation_id=lease.operation_id,
                        expected_revision=revision,authorize=self.authorize,check_drained=self.check_drained)
        with self._connection(scope) as conn:
            status,_,_=self._current(conn,scope,lease.operation_id)
            terminal=status in ('succeeded','failed','cancelled')
            if terminal:self.outbox.ack(conn,**scope,lease=lease)
            else:self.outbox.retry(conn,**scope,lease=lease)
            return ConfigurationDeliveryResult(lease.operation_id,status,'acknowledged' if terminal else 'deferred')
