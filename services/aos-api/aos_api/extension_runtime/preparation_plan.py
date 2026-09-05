"""One-shot trusted worker claim. No engine operations inside this transaction."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from aos_api.asset_registry.composition_contracts import ResolvedBundle
from aos_api.asset_registry.installation_service import _load_current_lock
from .lifecycle_store import _require_transaction, _values, RuntimeConflict, RuntimeRevisionConflict, RuntimeOperationStore
from .preparation_commit import _expected_backend_claims
from .reconciler import ResourceJournal, ResourceIntent
from .runtime_gate import _reject_deferred


@dataclass(frozen=True)
class PreparationMember:
    selected: ResolvedBundle
    intent: ResourceIntent


@dataclass(frozen=True)
class PreparationPlan:
    installation_id: UUID
    operation_id: UUID
    generation: UUID
    deadline: datetime
    revision: int
    members: tuple[PreparationMember, ...]


def claim_preparation(conn, *, installation_store, revalidator, check_current_permission,
                      org_id, project_id, operation_id, expected_revision, engine_context):
    _require_transaction(conn)
    target=(org_id,project_id,UUID(str(operation_id)))
    identity=conn.execute('''SELECT installation_id,expected_installation_etag FROM extension_runtime_operation
        WHERE org_id=%s AND project_id=%s AND operation_id=%s''',target).fetchone()
    if identity is None:raise LookupError('operation not found')
    installation_id,etag=_values(identity,('installation_id','expected_installation_etag'))
    locked=installation_store.lock_for_transition_in_transaction(conn,org_id=org_id,project_id=project_id,
        installation_id=str(installation_id),expected_etag_version=etag)
    row=conn.execute('''SELECT kind,phase,status,revision,deadline,requested_by FROM extension_runtime_operation
        WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE''',target).fetchone()
    kind,phase,status,revision,deadline,actor=_values(row,('kind','phase','status','revision','deadline','requested_by'))
    if type(expected_revision) is not int or revision!=expected_revision:
        raise RuntimeRevisionConflict('operation version changed')
    if (kind,phase,status,locked.record.state)!=('runtime-apply','accepted','accepted','approved'):
        raise RuntimeConflict('preparation already claimed or installation not approved')
    permission=check_current_permission(conn=conn,locked=locked,actor=actor)
    _reject_deferred(permission)
    if permission is not True:raise RuntimeConflict('current preparation permission required')
    lock=_load_current_lock(conn,locked=locked,org_id=org_id,project_id=project_id)
    checked=revalidator.revalidate_in_transaction(conn,lock=lock)
    expected=_expected_backend_claims(lock,checked)
    # A pre-existing intent is recovery work, never a fresh execution claim.
    prior=conn.execute('''SELECT resource_id FROM extension_runtime_resource_lease
        WHERE org_id=%s AND project_id=%s AND operation_id=%s LIMIT 1''',target).fetchone()
    if prior is not None:raise RuntimeConflict('existing resources require reconciliation')
    operations=RuntimeOperationStore()
    validating=operations.advance(conn,org_id=org_id,project_id=project_id,operation_id=operation_id,
        expected_revision=revision,phase='validating')
    generation=uuid4()
    members=[]
    for selected in lock.payload.resolved:
        if (selected.id,selected.content_hash) in expected:
            intent=ResourceJournal().prepare(conn,org_id=org_id,project_id=project_id,operation_id=operation_id,
                generation=generation,package_id=selected.id,package_hash=selected.content_hash,
                engine_context=engine_context,expires_at=deadline)
            members.append(PreparationMember(selected,intent))
    preparing=operations.advance(conn,org_id=org_id,project_id=project_id,operation_id=operation_id,
        expected_revision=validating.revision,phase='preparing')
    return PreparationPlan(installation_id,target[2],generation,deadline,preparing.revision,tuple(members))
