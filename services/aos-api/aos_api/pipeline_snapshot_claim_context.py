"""Private synchronous metadata-loop scope, never an execution permission."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import get_ident

from aos_api.extension_runtime.lifecycle_store import _require_transaction,_values
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_owner import CurrentSnapshotGroup


_active_loop=ContextVar('original_snapshot_source_claim_loop',default=None)


def _transaction_key(conn):
    _require_transaction(conn)
    row=conn.execute('SELECT pg_backend_pid() AS pid,pg_current_xact_id_if_assigned()::text AS xid').fetchone()
    pid,xid=_values(row,('pid','xid'))
    if xid is None:raise PermissionError('source claim loop requires locked transaction')
    return pid,xid


def _pairs(record):
    return tuple(sorted((m['runId'],PipelineExactRef.model_validate(m['controlRef'])) for m in record['members']))


def _reject_nested_source_claim_loop():
    if _active_loop.get() is not None:
        raise PermissionError('nested source claim loop is not supported')


@dataclass
class _ClaimLoop:
    conn: object
    transaction: tuple
    thread: int
    scope: object
    actor: str
    group_id: str
    pairs: tuple
    group: CurrentSnapshotGroup
    active: bool=True

    def check(self,conn,scope,actor):
        if (not self.active or self.conn is not conn or self.thread!=get_ident()
                or self.scope!=scope or self.actor!=actor):
            raise PermissionError('source claim loop identity differs or expired')
        if self.transaction!=_transaction_key(conn):
            raise PermissionError('source claim loop transaction changed')


@contextmanager
def _original_source_claim_loop(conn,*,scope,actor,record,group):
    # Only the original SourceGroupOwner's fixed metadata callback uses this.
    if record is None:
        yield
        return
    _reject_nested_source_claim_loop()
    if type(group) is not CurrentSnapshotGroup or record['schemaVersion']!='aos.snapshot-schedule-claim/v2':
        raise TypeError('original defined current source group required')
    pairs=_pairs(record)
    if ((record['request']['orgId'],record['request']['projectId'])!=scope.key
            or record['request']['actor']!=actor or len(pairs)!=len(group.members)
            or {ref for _,ref in pairs}!={ref for ref,_,_ in group.members}):
        raise PermissionError('source claim loop original members differ')
    context=_ClaimLoop(conn,_transaction_key(conn),get_ident(),scope,actor,record['request']['groupId'],pairs,group)
    token=_active_loop.set(context)
    try:
        yield
    finally:
        context.active=False
        _active_loop.reset(token)


def _check_source_claim_loop(conn,*,scope,actor,run_id,control_ref):
    context=_active_loop.get()
    if context is None:return
    # Reject another connection/thread before it can wait on our installation lock.
    context.check(conn,scope,actor)
    if (run_id,PipelineExactRef.model_validate(control_ref)) not in context.pairs:
        raise PermissionError('source claim loop member differs')


def _current_source_claim_group(conn,*,scope,actor,record):
    context=_active_loop.get()
    if context is None:return None
    context.check(conn,scope,actor)
    if context.group_id!=record['request']['groupId'] or context.pairs!=_pairs(record):
        raise PermissionError('source claim loop group differs')
    return context.group
