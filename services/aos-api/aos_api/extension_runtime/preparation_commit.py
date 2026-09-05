"""Atomic preparation history, not activation, liveness or business admission.

Only a trusted synchronous host worker may call this primitive. It performs no
engine I/O; current health is independently required by runtime-verify.
"""
from uuid import UUID

from aos_api.asset_registry.installation_service import _load_current_lock
from aos_api.asset_registry.installation_evidence import build_event_evidence
from .lifecycle_store import (
    _require_transaction, _values, _deadline_valid, _digest,
    RuntimeConflict, RuntimeRevisionConflict, RuntimeOperationStore,
)
from .runtime_gate import _reject_deferred


def commit_prepared(conn, *, installation_store, revalidator, check_current_permission,
                    org_id, project_id, operation_id, expected_revision, generation):
    _require_transaction(conn)
    target=(org_id,project_id,UUID(str(operation_id)))
    generation=UUID(str(generation))
    identity=conn.execute("""SELECT installation_id,expected_installation_etag
        FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s""",target).fetchone()
    if identity is None:
        raise LookupError('operation not found')
    installation_id,etag=_values(identity,('installation_id','expected_installation_etag'))
    head=conn.execute("""SELECT etag_version FROM bundle_installation
        WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE""",
        (org_id,project_id,installation_id)).fetchone()
    if head is None:raise LookupError('installation not found')
    current_etag=_values(head,('etag_version',))[0]
    locked=installation_store.lock_for_transition_in_transaction(conn,org_id=org_id,project_id=project_id,
        installation_id=str(installation_id),expected_etag_version=current_etag)
    row=conn.execute("""SELECT kind,phase,status,revision,deadline,requested_by
        FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE""",target).fetchone()
    kind,phase,status,revision,deadline,actor=_values(row,('kind','phase','status','revision','deadline','requested_by'))
    permission=check_current_permission(conn=conn,locked=locked,actor=actor)
    _reject_deferred(permission)
    if permission is not True:
        raise RuntimeConflict('current preparation permission required')
    if type(expected_revision) is not int:
        raise RuntimeRevisionConflict('operation version changed')
    if (kind,phase,status)==('runtime-apply','succeeded','succeeded'):
        prior=conn.execute("""SELECT payload,payload_hash FROM extension_runtime_event
            WHERE org_id=%s AND project_id=%s AND operation_id=%s AND type='preparation_committed'""",target).fetchall()
        if len(prior)==1:
            payload,digest=_values(prior[0],('payload','payload_hash'))
            if (digest==_digest(payload) and payload['generation']==str(generation)
                    and payload['expectedRevision']==expected_revision
                    and payload['installationRevision']==current_etag
                    and locked.record.state=='applied'):
                return locked.record
        raise RuntimeConflict('preparation replay differs or installation advanced; read current operation')
    if revision!=expected_revision or current_etag!=etag:
        raise RuntimeRevisionConflict('operation or installation version changed')
    if (kind,phase,status,locked.record.state)!=('runtime-apply','registered','running','approved'):
        raise RuntimeConflict('operation is not a registered preparation')
    lock=_load_current_lock(conn,locked=locked,org_id=org_id,project_id=project_id)
    checked=revalidator.revalidate_in_transaction(conn,lock=lock)
    members=checked.runtime_members
    claims=checked.backend_claims
    selected={(item.id,item.content_hash) for item in lock.payload.resolved}
    if (not 1<=len(members)<=64 or len(set(members))!=len(members)
            or len(claims)!=len(members) or {item[0] for item in claims}!=set(members)
            or any((item[0],item[1]) not in selected for item in claims)):
        raise RuntimeConflict('runtime preparation members unavailable or unsupported')
    expected={(item[0],item[1]):item[2] for item in claims}
    rows=conn.execute("""SELECT resource_id,generation,package_id,package_hash,container_id,
        create_claimed_at,cleanup_state,observed_release,expires_at
        FROM extension_runtime_resource_lease WHERE org_id=%s AND project_id=%s AND operation_id=%s
        ORDER BY resource_id FOR UPDATE""",target).fetchall()
    if len(rows)!=len(expected):
        raise RuntimeConflict('preparation resource set differs from lock')
    proofs=[]
    expiries=[deadline]
    seen=set()
    for row in rows:
        resource,resource_generation,package,digest,container,claimed,cleanup,released,expiry=_values(row,
            ('resource_id','generation','package_id','package_hash','container_id','create_claimed_at',
             'cleanup_state','observed_release','expires_at'))
        key=(package,digest)
        if (resource_generation!=generation or key not in expected or key in seen
                or container is None or claimed is None or cleanup!='pending' or released
                or not _deadline_valid(conn,expiry)):
            raise RuntimeConflict('preparation resource is incomplete or changed')
        seen.add(key)
        expiries.append(expiry)
        expected_payload={'resourceId':str(resource),'containerId':container,
                          'packageHash':digest,'claimsHash':expected[key]}
        observations=conn.execute("""SELECT payload,payload_hash FROM extension_runtime_event
            WHERE org_id=%s AND project_id=%s AND operation_id=%s AND type='resource_registered'
            AND payload->>'resourceId'=%s""",(*target,str(resource))).fetchall()
        if len(observations)!=1:
            raise RuntimeConflict('registration observation missing or ambiguous')
        payload,payload_hash=_values(observations[0],('payload','payload_hash'))
        if payload!=expected_payload or payload_hash!=_digest(expected_payload):
            raise RuntimeConflict('registration differs from current signed claims')
        proofs.append(expected_payload)
    # Separate wall clock check after every lock wait and policy revalidation.
    if not _deadline_valid(conn,min(expiries)):
        raise RuntimeConflict('operation or preparation resource deadline expired')
    observed_at=installation_store.read_control_clock_in_transaction(conn)
    current=locked.record.current
    evidence=build_event_evidence(evidence_type='runtime_preparation',
        installation_id=str(installation_id),from_revision=current.revision,to_revision=current.revision+1,
        lock_hash=current.lock_hash,permission_diff_hash=current.permission_diff_hash,
        migration_plan_hash=current.migration_plan_hash,contribution_diff_hash=current.contribution_diff_hash,
        decision_id=current.decision_id,observed_at=observed_at)
    operations=RuntimeOperationStore()
    progressed=operations.advance(conn,org_id=org_id,project_id=project_id,operation_id=operation_id,
        expected_revision=revision,phase='committing')
    result=installation_store.append_runtime_preparation_in_transaction(conn,locked=locked,actor=actor,evidence=evidence)
    # Link canonical old Installation history to the runtime proof without
    # changing any historical evidence serialization or checksum.
    conn.execute("""UPDATE extension_runtime_operation SET revision=revision+1
        WHERE org_id=%s AND project_id=%s AND operation_id=%s""",target)
    operations._event(conn,*target,progressed.revision+1,'preparation_committed',
        {'installationId':str(installation_id),'installationRevision':result.current_revision,
         'evidenceRef':evidence.evidence_ref,'evidenceHash':evidence.evidence_hash,
         'lockHash':current.lock_hash,'generation':str(generation),'resources':proofs,
         'expectedRevision':expected_revision})
    if not _deadline_valid(conn,min(expiries)):
        raise RuntimeConflict('preparation expired before final commit')
    operations.advance(conn,org_id=org_id,project_id=project_id,operation_id=operation_id,
        expected_revision=progressed.revision+1,phase='succeeded')
    return result
