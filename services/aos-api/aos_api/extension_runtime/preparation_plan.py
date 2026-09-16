"""One-shot trusted worker claim. No engine operations inside this transaction."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from aos_api.asset_registry.composition_contracts import ResolvedBundle
from aos_api.asset_registry.installation_service import _load_current_lock
from .lifecycle_store import _require_transaction, _values, RuntimeConflict, RuntimeRevisionConflict, RuntimeOperationStore
from .preparation_commit import _expected_backend_claims, _registered_resources
from .reconciler import ResourceJournal, ResourceIntent
from .runtime_gate import _reject_deferred
from .supervisor import ResourceIdentity


@dataclass(frozen=True)
class PreparationMember:
    selected: ResolvedBundle
    intent: ResourceIntent
    container_id: str | None = None


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


def rehydrate_current_preparation(conn, *, installation_store, revalidator,
                                  check_current_permission, check_current_conditions,
                                  org_id, project_id, installation_id, engine_context):
    """Atomically revalidate and lease an exact still-live ready generation."""
    _require_transaction(conn)
    if not callable(check_current_conditions):
        raise RuntimeConflict('current rehydration conditions required')
    installation_id=UUID(str(installation_id))
    target=(org_id,project_id,installation_id)
    head=conn.execute('''SELECT etag_version FROM bundle_installation
        WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',target).fetchone()
    if head is None:raise LookupError('installation not found')
    locked=installation_store.lock_for_transition_in_transaction(conn,org_id=org_id,
        project_id=project_id,installation_id=str(installation_id),
        expected_etag_version=_values(head,('etag_version',))[0])
    if locked.record.state!='active':
        raise RuntimeConflict('rehydration requires active installation')
    rows=conn.execute('''SELECT generation,revision,resource_handle_ref
        FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s
        AND installation_id=%s AND enabled AND NOT operation_fence
        AND observed_state='ready' AND desired_state='enabled' FOR UPDATE''',target).fetchall()
    if len(rows)!=1:raise RuntimeConflict('exact ready binding required for rehydration')
    generation,binding_revision,handle=_values(rows[0],('generation','revision','resource_handle_ref'))
    if not isinstance(handle,dict) or not isinstance(handle.get('preparationOperationId'),str):
        raise RuntimeConflict('ready binding resource handle required')
    operation_id=UUID(handle['preparationOperationId'])
    operation=conn.execute('''SELECT kind,status,phase,revision,requested_by
        FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s
        AND installation_id=%s AND operation_id=%s FOR UPDATE''',(*target,operation_id)).fetchone()
    if operation is None:raise LookupError('preparation operation not found')
    kind,status,phase,revision,actor=_values(operation,('kind','status','phase','revision','requested_by'))
    if (kind,status,phase)!=('runtime-apply','succeeded','succeeded'):
        raise RuntimeConflict('committed preparation required for rehydration')
    permission=check_current_permission(conn=conn,locked=locked,actor=actor)
    _reject_deferred(permission)
    if permission is not True:raise RuntimeConflict('current rehydration permission required')
    lock=_load_current_lock(conn,locked=locked,org_id=org_id,project_id=project_id)
    checked=revalidator.revalidate_in_transaction(conn,lock=lock)
    expected=_expected_backend_claims(lock,checked)
    conditions=check_current_conditions(conn=conn,locked=locked,lock=lock,actor=actor)
    _reject_deferred(conditions)
    if conditions is not True:raise RuntimeConflict('current rehydration conditions required')
    now=_values(conn.execute('SELECT clock_timestamp() AS now').fetchone(),('now',))[0]
    deadline=now+timedelta(seconds=180)
    proofs,_=_registered_resources(conn,(org_id,project_id,operation_id),generation,expected,deadline)
    if handle.get('resources')!=proofs:
        raise RuntimeConflict('ready binding resources differ for rehydration')
    resource_rows=conn.execute('''SELECT resource_id,package_id,package_hash,owner_token_ref,
        engine_context,container_id FROM extension_runtime_resource_lease
        WHERE org_id=%s AND project_id=%s AND operation_id=%s AND generation=%s
        ORDER BY resource_id FOR UPDATE''',(org_id,project_id,operation_id,generation)).fetchall()
    selected={(item.id,item.content_hash):item for item in lock.payload.resolved}
    members=[]
    for row in resource_rows:
        resource,package,digest,owner,context,container=_values(row,('resource_id','package_id',
            'package_hash','owner_token_ref','engine_context','container_id'))
        if context!=engine_context or (package,digest) not in expected or container is None:
            raise RuntimeConflict('rehydration resource identity differs')
        members.append(PreparationMember(selected[(package,digest)],ResourceIntent(
            resource,ResourceIdentity(owner),context,True),container))
    if len(members)!=len(expected):raise RuntimeConflict('rehydration resource set differs')
    updated=conn.execute('''UPDATE extension_runtime_resource_lease SET expires_at=%s
        WHERE org_id=%s AND project_id=%s AND operation_id=%s AND generation=%s
        AND NOT observed_release AND cleanup_state='pending' AND expires_at>clock_timestamp()
        RETURNING resource_id''',(deadline,org_id,project_id,operation_id,generation)).fetchall()
    if len(updated)!=len(expected):raise RuntimeConflict('rehydration lease expired before commit')
    conn.execute('''UPDATE extension_runtime_operation SET revision=revision+1
        WHERE org_id=%s AND project_id=%s AND operation_id=%s''',(org_id,project_id,operation_id))
    RuntimeOperationStore._event(conn,org_id,project_id,operation_id,revision+1,
        'runtime_lease_rehydrated',{'generation':str(generation),'bindingRevision':binding_revision,
            'expiresAt':deadline.isoformat()})
    return PreparationPlan(installation_id,operation_id,generation,deadline,revision+1,tuple(members))
