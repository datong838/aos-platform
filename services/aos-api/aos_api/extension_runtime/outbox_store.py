"""At-least-once runtime event consumption, not an execution authorization."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .lifecycle_store import _require_transaction,_values,_digest,_deadline_valid,RuntimeConflict


@dataclass(frozen=True)
class OutboxLease:
    event_id: UUID
    operation_id: UUID
    sequence: int
    event_type: str
    attempt: int
    claim_until: datetime


def _scope(conn,org_id,project_id):
    _require_transaction(conn)
    actual=conn.execute("SELECT current_setting('aos.org_id',true) AS org_id,current_setting('aos.project_id',true) AS project_id").fetchone()
    if not org_id or not project_id or _values(actual,('org_id','project_id'))!=(org_id,project_id):
        raise PermissionError('outbox requires exact transaction tenant scope')


def _seconds(value):
    if type(value) is not int or not 1<=value<=300:raise ValueError('duration must be 1..300 seconds')
    return value


class RuntimeOutboxStore:
    def claim(self,conn,*,org_id,project_id,lease_seconds=30,operation_kind=None,installation_id=None):
        _scope(conn,org_id,project_id);_seconds(lease_seconds)
        if operation_kind not in (None,'disable','runtime-verify','enable'):raise ValueError('unsupported internal consumer kind')
        installation_id=UUID(str(installation_id)) if installation_id is not None else None
        row=conn.execute('''SELECT b.event_id,e.operation_id,e.sequence,e.type,e.payload,e.payload_hash
            FROM extension_runtime_outbox b JOIN extension_runtime_event e
              ON (e.org_id,e.project_id,e.event_id)=(b.org_id,b.project_id,b.event_id)
            JOIN extension_runtime_operation o ON (o.org_id,o.project_id,o.operation_id)=(e.org_id,e.project_id,e.operation_id)
            WHERE b.org_id=%s AND b.project_id=%s AND b.consumer_id='runtime-reconciler'
              AND b.delivered_at IS NULL AND b.next_attempt<=clock_timestamp()
              AND (b.claim_until IS NULL OR b.claim_until<=clock_timestamp()) AND b.attempt<2147483647
              AND (CAST(%s AS text) IS NULL OR o.kind=%s)
              AND (CAST(%s AS uuid) IS NULL OR o.installation_id=%s)
            ORDER BY b.next_attempt,b.event_id LIMIT 1 FOR UPDATE OF b SKIP LOCKED''',(org_id,project_id,operation_kind,operation_kind,installation_id,installation_id)).fetchone()
        if row is None:return None
        event,operation,sequence,event_type,payload,payload_hash=_values(row,('event_id','operation_id','sequence','type','payload','payload_hash'))
        if _digest(payload)!=payload_hash:raise RuntimeConflict('immutable outbox event hash mismatch')
        row=conn.execute('''UPDATE extension_runtime_outbox SET attempt=attempt+1,
            claim_until=clock_timestamp()+(%s * interval '1 second')
            WHERE org_id=%s AND project_id=%s AND event_id=%s AND consumer_id='runtime-reconciler'
            RETURNING attempt,claim_until''',(lease_seconds,org_id,project_id,event)).fetchone()
        attempt,until=_values(row,('attempt','claim_until'))
        return OutboxLease(event,operation,sequence,event_type,attempt,until)

    def _locked(self,conn,org_id,project_id,lease):
        _scope(conn,org_id,project_id)
        if not isinstance(lease,OutboxLease) or type(lease.attempt) is not int or lease.attempt<1:
            raise ValueError('invalid outbox lease')
        target=(org_id,project_id,lease.event_id)
        row=conn.execute('''SELECT b.attempt,b.claim_until,b.delivered_at,e.operation_id,e.sequence,e.type
            FROM extension_runtime_outbox b JOIN extension_runtime_event e
              ON (e.org_id,e.project_id,e.event_id)=(b.org_id,b.project_id,b.event_id)
            WHERE b.org_id=%s AND b.project_id=%s AND b.event_id=%s AND b.consumer_id='runtime-reconciler'
            FOR UPDATE OF b''',target).fetchone()
        if row is None:raise RuntimeConflict('outbox lease not found')
        attempt,until,delivered,operation,sequence,event_type=_values(row,('attempt','claim_until','delivered_at','operation_id','sequence','type'))
        if (operation,sequence,event_type)!=(lease.operation_id,lease.sequence,lease.event_type):
            raise RuntimeConflict('outbox event reference changed')
        if delivered is not None or attempt!=lease.attempt or until is None or until!=lease.claim_until or not _deadline_valid(conn,until):
            raise RuntimeConflict('outbox claim expired or superseded')
        return target

    def ack(self,conn,*,org_id,project_id,lease):
        target=self._locked(conn,org_id,project_id,lease)
        conn.execute('''UPDATE extension_runtime_outbox SET delivered_at=clock_timestamp(),claim_until=NULL
            WHERE org_id=%s AND project_id=%s AND event_id=%s AND consumer_id='runtime-reconciler' ''',target)

    def retry(self,conn,*,org_id,project_id,lease,delay_seconds=5):
        _seconds(delay_seconds)
        target=self._locked(conn,org_id,project_id,lease)
        conn.execute('''UPDATE extension_runtime_outbox SET claim_until=NULL,
            next_attempt=clock_timestamp()+(%s * interval '1 second')
            WHERE org_id=%s AND project_id=%s AND event_id=%s AND consumer_id='runtime-reconciler' ''',(delay_seconds,*target))
