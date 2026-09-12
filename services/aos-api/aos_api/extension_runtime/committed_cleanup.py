"""Terminalize released committed preparations; never revive their generation."""
from uuid import UUID

from .lifecycle_store import (OperationResult, RuntimeConflict, RuntimeRevisionConflict,
                             RuntimeOperationStore, _digest, _require_transaction, _values)
from .storage_ports import require_runtime_role


def settle_committed_cleanup(conn, *, org_id, project_id, operation_id, expected_revision):
    _require_transaction(conn)
    require_runtime_role(conn,org_id=org_id,project_id=project_id,protected_tables=(
        'extension_runtime_operation','extension_runtime_binding','extension_runtime_resource_lease',
        'extension_runtime_event'))
    target=(org_id,project_id,UUID(str(operation_id)))
    identity=conn.execute('SELECT installation_id FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s',target).fetchone()
    if identity is None:raise LookupError('operation not found')
    installation=_values(identity,('installation_id',))[0]
    head=conn.execute('SELECT installation_id FROM bundle_installation WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE',(*target[:2],installation)).fetchone()
    if head is None:raise LookupError('installation not found')
    row=conn.execute('SELECT kind,phase,status,revision,failure_code FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE',target).fetchone()
    kind,phase,status,revision,reason=_values(row,('kind','phase','status','revision','failure_code'))
    if type(expected_revision) is not int or expected_revision!=revision:
        raise RuntimeRevisionConflict('operation version changed')
    replay=(status,reason)==('failed','PREPARED_RUNTIME_RELEASED')
    if kind!='runtime-apply' or phase!='succeeded' or (not replay and (status,reason)!=('needs_attention','RESOURCE_CLEANUP_UNCERTAIN')):
        raise RuntimeConflict('committed cleanup state required')
    proofs=conn.execute("SELECT payload,payload_hash FROM extension_runtime_event WHERE org_id=%s AND project_id=%s AND operation_id=%s AND type='preparation_committed'",target).fetchall()
    if len(proofs)!=1:raise RuntimeConflict('exact preparation proof required')
    proof,digest=_values(proofs[0],('payload','payload_hash'))
    if not isinstance(proof,dict) or digest!=_digest(proof) or proof.get('installationId')!=str(installation):
        raise RuntimeConflict('preparation proof integrity invalid')
    generation=proof.get('generation')
    try:generation=UUID(str(generation))
    except ValueError:raise RuntimeConflict('preparation generation invalid') from None
    binding=conn.execute('SELECT generation,enabled,operation_fence,observed_state FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE',(*target[:2],installation)).fetchone()
    if binding is None or _values(binding,('generation','enabled','operation_fence','observed_state'))!=(generation,False,True,'unknown'):
        raise RuntimeConflict('released generation must remain fenced')
    rows=conn.execute('SELECT resource_id,generation,container_id,package_hash,observed_release,cleanup_state FROM extension_runtime_resource_lease WHERE org_id=%s AND project_id=%s AND operation_id=%s ORDER BY resource_id FOR UPDATE',target).fetchall()
    resources=proof.get('resources')
    if not rows or not isinstance(resources,list) or len(resources)!=len(rows):
        raise RuntimeConflict('committed resource set differs')
    expected={}
    for item in resources:
        if not isinstance(item,dict) or not isinstance(item.get('resourceId'),str) or item['resourceId'] in expected:
            raise RuntimeConflict('committed resource proof invalid')
        expected[item['resourceId']]=item
    ids=[]
    for row in rows:
        resource,actual_generation,container,package_hash,released,cleanup=_values(row,('resource_id','generation','container_id','package_hash','observed_release','cleanup_state'))
        item=expected.get(str(resource))
        if (actual_generation!=generation or released is not True or cleanup!='released' or item is None
                or item.get('containerId')!=container or item.get('packageHash')!=package_hash):
            raise RuntimeConflict('resources not confirmed released with exact proof')
        ids.append(str(resource))
    payload={'installationId':str(installation),'generation':str(generation),'resourceIds':ids,
             'preparationProofHash':digest,'failureCode':'PREPARED_RUNTIME_RELEASED'}
    if replay:
        event=conn.execute("SELECT payload,payload_hash FROM extension_runtime_event WHERE org_id=%s AND project_id=%s AND operation_id=%s AND sequence=%s AND type='committed_preparation_released'",(*target,revision)).fetchone()
        if event is None or _values(event,('payload','payload_hash'))!=(payload,_digest(payload)):
            raise RuntimeConflict('released preparation replay proof invalid')
        return OperationResult(target[2],phase,status,revision,replayed=True)
    revision+=1
    conn.execute("UPDATE extension_runtime_operation SET status='failed',failure_code='PREPARED_RUNTIME_RELEASED',revision=%s WHERE org_id=%s AND project_id=%s AND operation_id=%s",(revision,*target))
    RuntimeOperationStore._event(conn,*target,revision,'committed_preparation_released',payload)
    return OperationResult(target[2],phase,'failed',revision)
