"""Expire delivery records only after existing execution authority has settled."""
from aos_api.extension_runtime.generation_attempts import _scope
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, _require_transaction, _values
from aos_api.tenant_scope import TenantScope


def expire_ui_read_deliveries(*,conn,scope:TenantScope,limit:int=100):
    _require_transaction(conn)
    if type(scope) is not TenantScope or type(limit) is not int or not 1<=limit<=100:
        raise RuntimeConflict('bounded scoped UI recovery required')
    _scope(conn,*scope.key)
    rows=conn.execute('''SELECT q.request_id,q.revision,q.attempt_id
        FROM extension_runtime_ui_read_request q
        WHERE q.org_id=%s AND q.project_id=%s AND q.state IN ('requested','claimed')
          AND q.deadline<=clock_timestamp()
          AND (q.attempt_id IS NULL OR EXISTS(
            SELECT 1 FROM extension_runtime_execution_attempt a
            WHERE a.org_id=q.org_id AND a.project_id=q.project_id AND a.attempt_id=q.attempt_id
              AND a.state IN ('succeeded','failed','abandoned')))
        ORDER BY q.deadline,q.request_id FOR UPDATE OF q SKIP LOCKED LIMIT %s''',(*scope.key,limit)).fetchall()
    expired=[]
    for row in rows:
        request,revision,attempt=_values(row,('request_id','revision','attempt_id'))
        if attempt is not None:
            current=conn.execute('''SELECT state FROM extension_runtime_execution_attempt
                WHERE org_id=%s AND project_id=%s AND attempt_id=%s FOR SHARE''',(*scope.key,attempt)).fetchone()
            if current is None or _values(current,('state',))[0] not in {'succeeded','failed','abandoned'}:
                raise RuntimeConflict('UI recovery attempt is not terminal')
        conn.execute('''UPDATE extension_runtime_ui_read_request
            SET state='expired',revision=%s,completed_at=clock_timestamp(),failure_code='READ_DEADLINE_EXPIRED'
            WHERE org_id=%s AND project_id=%s AND request_id=%s''',(revision+1,*scope.key,request))
        expired.append(request)
    return tuple(expired)
