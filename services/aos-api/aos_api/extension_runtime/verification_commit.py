"""Internal atomic verification. No HTTP entry, worker grant, or enable action.

Health time is a trusted owner observation, never a request field. Production
worker wiring must own the exact resource group through this transaction.
"""
from datetime import datetime
from uuid import UUID

from psycopg.types.json import Jsonb

from aos_api.asset_registry.installation_service import _load_current_lock
from aos_api.asset_registry.installation_evidence import build_event_evidence
from .lifecycle_store import (_require_transaction, _values, _digest, _deadline_valid,
    RuntimeConflict, RuntimeRevisionConflict, RuntimeOperationStore)
from .preparation_commit import _expected_backend_claims, _registered_resources
from .runtime_gate import _reject_deferred


def _fresh_health(conn, checked_at):
    if not isinstance(checked_at,datetime) or checked_at.utcoffset() is None:
        raise RuntimeConflict('trusted health time required')
    row=conn.execute('SELECT clock_timestamp() AS now').fetchone()
    age=(_values(row,('now',))[0]-checked_at).total_seconds()
    if not 0 <= age <= 3:
        raise RuntimeConflict('health observation is stale or in the future')


def commit_verified(conn, *, installation_store, revalidator, check_current_permission,
                    check_current_conditions, org_id, project_id, operation_id,
                    expected_revision, preparation_operation_id, generation, health_checked_at):
    _require_transaction(conn)
    target=(org_id,project_id,UUID(str(operation_id)))
    preparation=(org_id,project_id,UUID(str(preparation_operation_id)))
    generation=UUID(str(generation))
    identity=conn.execute('''SELECT installation_id,expected_installation_etag
        FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s''',target).fetchone()
    if identity is None:raise LookupError('verification operation not found')
    installation_id,etag=_values(identity,('installation_id','expected_installation_etag'))
    locked=installation_store.lock_for_transition_in_transaction(conn,org_id=org_id,project_id=project_id,
        installation_id=str(installation_id),expected_etag_version=etag)
    lock=_load_current_lock(conn,locked=locked,org_id=org_id,project_id=project_id)
    installation_store.guard_replacement_activation_in_transaction(conn,locked=locked,
        requested_ref=lock.payload.current_installation_ref)
    row=conn.execute('''SELECT kind,phase,status,revision,deadline,requested_by
        FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE''',target).fetchone()
    kind,phase,status,revision,deadline,actor=_values(row,('kind','phase','status','revision','deadline','requested_by'))
    if type(expected_revision) is not int or revision!=expected_revision:
        raise RuntimeRevisionConflict('verification revision changed')
    if (kind,phase,status,locked.record.state)!=('runtime-verify','accepted','accepted','applied'):
        raise RuntimeConflict('verification requires current applied preparation')
    permission=check_current_permission(conn=conn,locked=locked,actor=actor)
    _reject_deferred(permission)
    if permission is not True:raise RuntimeConflict('current verification permission required')
    prepared=conn.execute('''SELECT installation_id,kind,phase,status,deadline
        FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s
        AND installation_id=%s AND kind='runtime-apply' FOR UPDATE''',(*preparation,installation_id)).fetchone()
    if prepared is None:raise LookupError('preparation operation not found')
    prepared_id,pkind,pphase,pstatus,pdeadline=_values(prepared,('installation_id','kind','phase','status','deadline'))
    if (prepared_id,pkind,pphase,pstatus)!=(installation_id,'runtime-apply','succeeded','succeeded'):
        raise RuntimeConflict('preparation does not belong to this verification')
    binding=conn.execute('''SELECT generation FROM extension_runtime_binding
        WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',
        (org_id,project_id,installation_id)).fetchall()
    if binding:raise RuntimeConflict('existing binding requires lifecycle reconciliation')
    checked=revalidator.revalidate_in_transaction(conn,lock=lock)
    expected=_expected_backend_claims(lock,checked)
    proofs,expiries=_registered_resources(conn,preparation,generation,expected,min(deadline,pdeadline))
    events=conn.execute('''SELECT payload,payload_hash FROM extension_runtime_event
        WHERE org_id=%s AND project_id=%s AND operation_id=%s AND type='preparation_committed' ''',preparation).fetchall()
    if len(events)!=1:raise RuntimeConflict('preparation commit evidence unavailable')
    payload,digest=_values(events[0],('payload','payload_hash'))
    current=locked.record.current
    prepared_evidence=locked.record.events[-1].evidence
    if (digest!=_digest(payload) or payload.get('installationId')!=str(installation_id)
            or payload.get('installationRevision')!=current.revision
            or payload.get('lockHash')!=lock.lock_hash or payload.get('generation')!=str(generation)
            or payload.get('resources')!=proofs
            or prepared_evidence is None or prepared_evidence.type!='runtime_preparation'
            or payload.get('evidenceHash')!=prepared_evidence.evidence_hash
            or payload.get('evidenceRef')!=prepared_evidence.evidence_ref):
        raise RuntimeConflict('preparation evidence differs from current installation')
    conditions=check_current_conditions(conn=conn,locked=locked,lock=lock,actor=actor)
    _reject_deferred(conditions)
    if conditions is not True:raise RuntimeConflict('current schema and platform conditions required')
    _fresh_health(conn,health_checked_at)
    operations=RuntimeOperationStore()
    for next_phase in ('validating','committing'):
        revision=operations.advance(conn,org_id=org_id,project_id=project_id,
            operation_id=operation_id,expected_revision=revision,phase=next_phase).revision
    evidence=build_event_evidence(evidence_type='verification',installation_id=str(installation_id),
        from_revision=current.revision,to_revision=current.revision+1,lock_hash=current.lock_hash,
        permission_diff_hash=current.permission_diff_hash,migration_plan_hash=current.migration_plan_hash,
        contribution_diff_hash=current.contribution_diff_hash,decision_id=current.decision_id,
        observed_at=installation_store.read_control_clock_in_transaction(conn))
    result=installation_store.append_verify_in_transaction(conn,locked=locked,actor=actor,evidence=evidence)
    conn.execute('''INSERT INTO extension_runtime_binding
        (org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,profile_ref,
         desired_state,observed_state,enabled,operation_fence,resource_handle_ref)
        VALUES(%s,%s,%s,%s,%s,%s,'internal-python-v1','disabled','ready',false,true,%s)''',
        (org_id,project_id,installation_id,generation,result.current_revision,
         Jsonb({'lockHash':lock.lock_hash}),Jsonb({'preparationOperationId':str(preparation[2]),'resources':proofs})))
    conn.execute('UPDATE extension_runtime_operation SET revision=revision+1 WHERE org_id=%s AND project_id=%s AND operation_id=%s',target)
    revision+=1
    operations._event(conn,*target,revision,'verification_committed',{'installationId':str(installation_id),
        'installationRevision':result.current_revision,'generation':str(generation),
        'preparationOperationId':str(preparation[2]),'evidenceHash':evidence.evidence_hash,
        'healthCheckedAt':health_checked_at.isoformat(),'enabled':False})
    _fresh_health(conn,health_checked_at)
    if not _deadline_valid(conn,min(expiries)):
        raise RuntimeConflict('verification resource expired before final commit')
    operations.advance(conn,org_id=org_id,project_id=project_id,operation_id=operation_id,
        expected_revision=revision,phase='succeeded')
    return result
