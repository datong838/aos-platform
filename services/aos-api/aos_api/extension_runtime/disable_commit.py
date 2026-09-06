"""Two-transaction disable: the caller MUST commit begin before attempting finish.

Drain covers all epochs of this generation. No engine cleanup or ready claim.
"""
from uuid import UUID

from .binding_store import RuntimeBindingStore
from .disable_request import load_disable_target
from .lifecycle_store import (_require_transaction,_values,_digest,RuntimeConflict,
    RuntimeRevisionConflict,RuntimeOperationStore)
from .runtime_gate import _reject_deferred


def _locked(conn, *, org_id,project_id,operation_id,expected_revision,installation_store,check_current_permission,phase):
    _require_transaction(conn)
    identity=(org_id,project_id,UUID(str(operation_id)))
    row=conn.execute('''SELECT installation_id,expected_installation_etag FROM extension_runtime_operation
        WHERE org_id=%s AND project_id=%s AND operation_id=%s''',identity).fetchone()
    if row is None:raise LookupError('disable operation not found')
    installation_id,etag=_values(row,('installation_id','expected_installation_etag'))
    locked=installation_store.lock_for_transition_in_transaction(conn,org_id=org_id,project_id=project_id,
        installation_id=str(installation_id),expected_etag_version=etag)
    row=conn.execute('''SELECT kind,phase,status,revision,requested_by FROM extension_runtime_operation
        WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE''',identity).fetchone()
    kind,current,status,revision,actor=_values(row,('kind','phase','status','revision','requested_by'))
    if type(expected_revision) is not int or revision!=expected_revision:
        raise RuntimeRevisionConflict('disable revision changed')
    if (kind,current,status)!=('disable',phase,'accepted' if phase=='accepted' else 'running'):
        raise RuntimeConflict('disable phase differs')
    request=load_disable_target(conn,org_id=org_id,project_id=project_id,operation_id=operation_id)
    permission=check_current_permission(conn=conn,locked=locked,actor=actor)
    _reject_deferred(permission)
    if permission is not True:raise RuntimeConflict('current disable permission required')
    return identity,installation_id,request,revision


def begin_disable(conn, **args):
    identity,installation_id,request,revision=_locked(conn,**args,phase='accepted')
    return RuntimeBindingStore().fence(conn,org_id=identity[0],project_id=identity[1],installation_id=installation_id,
        generation=request.generation,operation_id=identity[2],expected_operation_revision=revision,
        expected_binding_revision=request.bindingRevision)


def finish_disable(conn, *, check_drained, **args):
    identity,installation_id,request,revision=_locked(conn,**args,phase='fencing')
    event=conn.execute('''SELECT payload,payload_hash FROM extension_runtime_event
        WHERE org_id=%s AND project_id=%s AND operation_id=%s AND sequence=%s AND type='fencing' ''',
        (*identity,revision)).fetchone()
    if event is None or _values(event,('payload','payload_hash'))!=({'previousPhase':'accepted'},_digest({'previousPhase':'accepted'})):
        raise RuntimeConflict('disable fence evidence unavailable')
    target=(*identity[:2],installation_id,UUID(request.generation))
    row=conn.execute('''SELECT revision,enabled,operation_fence,observed_state,execution_epoch
        FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s
        AND generation=%s FOR UPDATE''',target).fetchone()
    if row is None:raise LookupError('disable binding not found')
    brev,enabled,fence,observed,epoch=_values(row,('revision','enabled','operation_fence','observed_state','execution_epoch'))
    if (brev!=request.bindingRevision+1 or enabled is not False or fence is not True or observed!='draining'):
        raise RuntimeConflict('disable binding differs from accepted fence')
    if not callable(check_drained):raise RuntimeConflict('current generation drain reader required')
    drained=check_drained(conn,org_id=identity[0],project_id=identity[1],installation_id=str(installation_id),
        generation=request.generation,fence_epoch=epoch)
    _reject_deferred(drained)
    if drained is not True:raise RuntimeConflict('generation work remains undrained')
    operations=RuntimeOperationStore()
    for phase in ('draining','committing'):
        revision=operations.advance(conn,org_id=identity[0],project_id=identity[1],operation_id=identity[2],
            expected_revision=revision,phase=phase).revision
    conn.execute('''UPDATE extension_runtime_binding SET desired_state='disabled',observed_state='unknown',revision=revision+1
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s''',target)
    conn.execute('UPDATE extension_runtime_operation SET revision=revision+1 WHERE org_id=%s AND project_id=%s AND operation_id=%s',identity)
    revision+=1
    operations._event(conn,*identity,revision,'disabled_committed',dict(installationId=str(installation_id),
        generation=request.generation,bindingRevision=brev+1,executionEpoch=epoch,resourcesRetained=True))
    return operations.advance(conn,org_id=identity[0],project_id=identity[1],operation_id=identity[2],
        expected_revision=revision,phase='succeeded')
