"""Immutable disable identity; not a current permission or drain grant."""
from uuid import UUID

from .disable_contracts import DisableTarget
from .lifecycle_store import _require_transaction, _values, _digest, _request_hash, RuntimeConflict


def load_disable_target(conn, *, org_id, project_id, operation_id):
    _require_transaction(conn)
    scope=conn.execute("SELECT current_setting('aos.org_id',true) AS org_id,current_setting('aos.project_id',true) AS project_id").fetchone()
    if not org_id or not project_id or _values(scope,('org_id','project_id'))!=(org_id,project_id):
        raise PermissionError('disable tenant scope mismatch')
    identity=(org_id,project_id,UUID(str(operation_id)))
    row=conn.execute('''SELECT kind,requested_by,expected_installation_etag,expected_binding_revision,
        deadline,request_hash FROM extension_runtime_operation
        WHERE org_id=%s AND project_id=%s AND operation_id=%s''',identity).fetchone()
    if row is None:raise LookupError('disable operation not found')
    kind,actor,etag,revision,deadline,request_hash=_values(row,
        ('kind','requested_by','expected_installation_etag','expected_binding_revision','deadline','request_hash'))
    row=conn.execute('''SELECT payload,payload_hash FROM extension_runtime_event
        WHERE org_id=%s AND project_id=%s AND operation_id=%s AND sequence=1 AND type='accepted' ''',identity).fetchone()
    if row is None:raise RuntimeConflict('disable accepted target unavailable')
    payload,digest=_values(row,('payload','payload_hash'))
    if kind!='disable' or set(payload)!={'kind','bindingTarget'} or payload['kind']!=kind or _digest(payload)!=digest:
        raise RuntimeConflict('disable accepted target invalid')
    target=DisableTarget.model_validate(payload['bindingTarget'])
    if revision!=target.bindingRevision or request_hash!=_request_hash(kind=kind,actor=actor,etag=etag,
            deadline=deadline,binding_target=target.model_dump(mode='json')):
        raise RuntimeConflict('disable accepted target differs from request')
    return target
