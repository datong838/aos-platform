"""Commit a fenced configuration pointer; never declares runtime ready/enabled.

Only the trusted lifecycle host may call this subordinate primitive. The drain
reader must cover every admitted and unresolved job of this generation under
the same installation lock, including older epochs. fence_epoch is a watermark,
not a filter restricting the reader to the newly fenced epoch.
"""
from uuid import UUID

from psycopg.types.json import Jsonb

from .configuration_request import load_configure_target
from .configuration_store import read_configuration, _target
from .lifecycle_store import (_require_transaction, _values, _deadline_valid, _digest,
    RuntimeConflict, RuntimeRevisionConflict, RuntimeOperationStore)
from .runtime_gate import _reject_deferred
from .binding_store import RuntimeBindingStore


def begin_configuration(conn, *, org_id,project_id,operation_id,expected_revision,authorize):
    """Caller commits this fence before any generation drain observation."""
    _require_transaction(conn)
    identity=(org_id,project_id,UUID(str(operation_id)))
    row=conn.execute('''SELECT installation_id FROM extension_runtime_operation
        WHERE org_id=%s AND project_id=%s AND operation_id=%s''',identity).fetchone()
    if row is None:raise LookupError('configuration operation not found')
    installation=_values(row,('installation_id',))[0]
    head=conn.execute('''SELECT etag_version FROM bundle_installation
        WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',
        (org_id,project_id,installation)).fetchone()
    if head is None:raise LookupError('configuration installation not found')
    row=conn.execute('''SELECT kind,status,phase,revision,expected_installation_etag,requested_by
        FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE''',identity).fetchone()
    kind,status,phase,revision,etag,actor=_values(row,('kind','status','phase','revision','expected_installation_etag','requested_by'))
    if type(expected_revision) is not int or expected_revision!=revision or _values(head,('etag_version',))[0]!=etag:
        raise RuntimeRevisionConflict('configuration operation or installation changed')
    if (kind,status,phase)!=('configure','accepted','accepted'):
        raise RuntimeConflict('configuration requires current accepted operation')
    request=load_configure_target(conn,org_id=org_id,project_id=project_id,operation_id=operation_id)
    row=conn.execute('''SELECT revision,desired_state,observed_state FROM extension_runtime_binding
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s FOR UPDATE''',
        (org_id,project_id,installation,UUID(request.generation))).fetchone()
    if row is None:raise LookupError('configuration binding not found')
    brev,desired,observed=_values(row,('revision','desired_state','observed_state'))
    if brev!=request.bindingRevision or desired=='uninstalled' or observed=='stopped':
        raise RuntimeConflict('configuration accepted binding is unavailable')
    read_configuration(conn,org_id=org_id,project_id=project_id,installation_id=installation,
        generation=request.generation,actor=actor,ref=request.configRef,authorize=authorize)
    validated=RuntimeOperationStore().advance(conn,org_id=org_id,project_id=project_id,
        operation_id=operation_id,expected_revision=revision,phase='validating')
    return RuntimeBindingStore().fence(conn,org_id=org_id,project_id=project_id,installation_id=installation,
        generation=request.generation,operation_id=operation_id,expected_operation_revision=validated.revision,
        expected_binding_revision=request.bindingRevision)


def commit_configuration(conn, *, org_id, project_id, operation_id, expected_revision,
                         authorize, check_drained):
    _require_transaction(conn)
    identity=(org_id,project_id,UUID(str(operation_id)))
    row=conn.execute('''SELECT installation_id FROM extension_runtime_operation
        WHERE org_id=%s AND project_id=%s AND operation_id=%s''',identity).fetchone()
    if row is None:raise LookupError('configuration operation not found')
    installation_id=_values(row,('installation_id',))[0]
    head=conn.execute('''SELECT etag_version FROM bundle_installation
        WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',
        (org_id,project_id,installation_id)).fetchone()
    if head is None:raise LookupError('configuration installation not found')
    row=conn.execute('''SELECT kind,phase,status,revision,expected_installation_etag,requested_by,deadline
        FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE''',identity).fetchone()
    kind,phase,status,revision,etag,actor,deadline=_values(row,
        ('kind','phase','status','revision','expected_installation_etag','requested_by','deadline'))
    if type(expected_revision) is not int or expected_revision!=revision or _values(head,('etag_version',))[0]!=etag:
        raise RuntimeRevisionConflict('configuration operation or installation changed')
    if (kind,phase,status)!=('configure','fencing','running') or not _deadline_valid(conn,deadline):
        raise RuntimeConflict('configuration requires current fenced operation')
    event=conn.execute('''SELECT payload,payload_hash FROM extension_runtime_event
        WHERE org_id=%s AND project_id=%s AND operation_id=%s AND sequence=%s AND type='fencing' ''',
        (*identity,revision)).fetchone()
    if event is None or _values(event,('payload','payload_hash')) != (
            {'previousPhase':'validating'},_digest({'previousPhase':'validating'})):
        raise RuntimeConflict('configuration fencing evidence unavailable')
    request=load_configure_target(conn,org_id=org_id,project_id=project_id,operation_id=operation_id)
    target=_target(conn,org_id,project_id,installation_id,request.generation)
    row=conn.execute('''SELECT revision,enabled,operation_fence,observed_state,execution_epoch,desired_state
        FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
        FOR UPDATE''',target).fetchone()
    if row is None:raise LookupError('configuration binding not found')
    binding_revision,enabled,fence,observed,epoch,desired=_values(row,
        ('revision','enabled','operation_fence','observed_state','execution_epoch','desired_state'))
    if (binding_revision!=request.bindingRevision+1 or enabled is not False or fence is not True
            or observed!='draining' or desired=='uninstalled'):
        raise RuntimeConflict('configuration binding is not the accepted fenced version')
    read_configuration(conn,org_id=org_id,project_id=project_id,installation_id=installation_id,
        generation=request.generation,actor=actor,ref=request.configRef,authorize=authorize)
    if not callable(check_drained):raise RuntimeConflict('current drain reader required')
    drained=check_drained(conn,org_id=org_id,project_id=project_id,installation_id=str(installation_id),
        generation=request.generation,fence_epoch=epoch)
    _reject_deferred(drained)
    if drained is not True:raise RuntimeConflict('configuration work remains undrained')
    operations=RuntimeOperationStore()
    revision=operations.advance(conn,org_id=org_id,project_id=project_id,operation_id=operation_id,
        expected_revision=revision,phase='committing').revision
    conn.execute('''UPDATE extension_runtime_binding SET config_ref=%s,revision=revision+1,
        desired_state='disabled',enabled=false,operation_fence=true,observed_state='unknown'
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s''',
        (Jsonb(request.configRef.model_dump(mode='json')),*target))
    conn.execute('UPDATE extension_runtime_operation SET revision=revision+1 WHERE org_id=%s AND project_id=%s AND operation_id=%s',identity)
    revision+=1
    operations._event(conn,*identity,revision,'configuration_committed',dict(installationId=str(installation_id),
        generation=request.generation,configRef=request.configRef.model_dump(mode='json'),
        bindingRevision=binding_revision+1,executionEpoch=epoch,enabled=False,observedState='unknown'))
    # Head locks prevent revocation races, not the passage of validity windows.
    read_configuration(conn,org_id=org_id,project_id=project_id,installation_id=installation_id,
        generation=request.generation,actor=actor,ref=request.configRef,authorize=authorize)
    return operations.advance(conn,org_id=org_id,project_id=project_id,operation_id=operation_id,
        expected_revision=revision,phase='succeeded')
