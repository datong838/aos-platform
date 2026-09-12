"""Internal enable transaction, exclusively inside the verified resource owner.

No business invocation or budget reservation is performed here. The host must
retain the exact preparation group until this transaction settles.
"""
from uuid import UUID

from aos_api.asset_registry.installation_service import _load_current_lock
from .configuration_request import load_enable_target
from .configuration_store import read_configuration, _target
from .lifecycle_store import (_require_transaction, _values, _deadline_valid,
    RuntimeConflict, RuntimeRevisionConflict, RuntimeOperationStore)
from .preparation_commit import _expected_backend_claims, _registered_resources
from .runtime_gate import _reject_deferred
from .verification_commit import _fresh_health


def commit_enabled(conn, *, installation_store, revalidator, check_current_permission,
                   check_current_conditions, authorize, org_id, project_id, operation_id,
                   expected_revision, preparation_operation_id, generation, health_checked_at):
    _require_transaction(conn)
    identity=(org_id,project_id,UUID(str(operation_id)))
    preparation=(org_id,project_id,UUID(str(preparation_operation_id)))
    generation=UUID(str(generation))
    row=conn.execute('''SELECT installation_id,expected_installation_etag FROM extension_runtime_operation
        WHERE org_id=%s AND project_id=%s AND operation_id=%s''',identity).fetchone()
    if row is None:raise LookupError('enable operation not found')
    installation_id,etag=_values(row,('installation_id','expected_installation_etag'))
    locked=installation_store.lock_for_transition_in_transaction(conn,org_id=org_id,project_id=project_id,
        installation_id=str(installation_id),expected_etag_version=etag)
    lock=_load_current_lock(conn,locked=locked,org_id=org_id,project_id=project_id)
    installation_store.guard_replacement_activation_in_transaction(conn,locked=locked,
        requested_ref=lock.payload.current_installation_ref)
    row=conn.execute('''SELECT kind,phase,status,revision,requested_by,deadline FROM extension_runtime_operation
        WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE''',identity).fetchone()
    kind,phase,status,revision,actor,deadline=_values(row,('kind','phase','status','revision','requested_by','deadline'))
    if type(expected_revision) is not int or expected_revision!=revision:
        raise RuntimeRevisionConflict('enable operation revision changed')
    if (kind,phase,status,locked.record.state)!=('enable','accepted','accepted','active'):
        raise RuntimeConflict('enable requires current active installation and accepted operation')
    request=load_enable_target(conn,org_id=org_id,project_id=project_id,operation_id=operation_id)
    if UUID(request.generation)!=generation:
        raise RuntimeConflict('enable generation differs from owned resource group')
    prepared=conn.execute('''SELECT phase,status FROM extension_runtime_operation
        WHERE org_id=%s AND project_id=%s AND operation_id=%s AND installation_id=%s
        AND kind='runtime-apply' FOR UPDATE''',(*preparation,installation_id)).fetchone()
    if prepared is None:raise LookupError('owned preparation not found')
    pphase,pstatus=_values(prepared,('phase','status'))
    if (pphase,pstatus)!=('succeeded','succeeded'):
        raise RuntimeConflict('owned preparation is not committed')
    target=_target(conn,org_id,project_id,installation_id,generation)
    row=conn.execute('''SELECT revision,enabled,operation_fence,observed_state,desired_state,
        installation_revision,package_lock_ref,config_ref,resource_handle_ref,execution_epoch
        FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s
        AND generation=%s FOR UPDATE''',target).fetchone()
    if row is None:raise LookupError('enable binding not found')
    brev,enabled,fence,observed,desired,irev,lockref,config,resources,epoch=_values(row,
        ('revision','enabled','operation_fence','observed_state','desired_state','installation_revision',
         'package_lock_ref','config_ref','resource_handle_ref','execution_epoch'))
    if (brev!=request.bindingRevision or enabled is not False or fence is not True
            or observed not in ('unknown','ready') or desired!='disabled'
            or irev!=locked.record.current.revision or lockref!={'lockHash':lock.lock_hash}
            or config!=request.configRef.model_dump(mode='json')):
        raise RuntimeConflict('enable binding differs from accepted configuration')
    permission=check_current_permission(conn=conn,locked=locked,actor=actor)
    _reject_deferred(permission)
    if permission is not True:raise RuntimeConflict('current enable permission required')
    def configuration():
        return read_configuration(conn,org_id=org_id,project_id=project_id,installation_id=installation_id,
            generation=generation,actor=actor,ref=request.configRef,authorize=authorize)
    configuration()
    checked=revalidator.revalidate_in_transaction(conn,lock=lock)
    # A committed preparation is bounded by its renewable resource leases.
    # Its historical execution deadline does not expire the live generation.
    proofs,expiries=_registered_resources(conn,preparation,generation,
        _expected_backend_claims(lock,checked),deadline)
    if resources!={'preparationOperationId':str(preparation[2]),'resources':proofs}:
        raise RuntimeConflict('owned resources differ from verified binding')
    conditions=check_current_conditions(conn=conn,locked=locked,lock=lock,actor=actor)
    _reject_deferred(conditions)
    if conditions is not True:raise RuntimeConflict('current schema and platform conditions required')
    _fresh_health(conn,health_checked_at)
    operations=RuntimeOperationStore()
    for next_phase in ('validating','committing'):
        revision=operations.advance(conn,org_id=org_id,project_id=project_id,operation_id=operation_id,
            expected_revision=revision,phase=next_phase).revision
    conn.execute('''UPDATE extension_runtime_binding SET enabled=true,operation_fence=false,
        observed_state='ready',desired_state='enabled',revision=revision+1,execution_epoch=execution_epoch+1
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s''',target)
    conn.execute('UPDATE extension_runtime_operation SET revision=revision+1 WHERE org_id=%s AND project_id=%s AND operation_id=%s',identity)
    revision+=1
    operations._event(conn,*identity,revision,'enabled_committed',dict(installationId=str(installation_id),
        generation=str(generation),configRef=config,bindingRevision=brev+1,executionEpoch=epoch+1,
        preparationOperationId=str(preparation[2]),healthCheckedAt=health_checked_at.isoformat()))
    configuration()
    _fresh_health(conn,health_checked_at)
    if not _deadline_valid(conn,min(expiries)):
        raise RuntimeConflict('enable resource expired before final commit')
    return operations.advance(conn,org_id=org_id,project_id=project_id,operation_id=operation_id,
        expected_revision=revision,phase='succeeded')
