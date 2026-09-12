"""A replacement may enable only after the exact predecessor drain committed.

Caller owns both installation heads through the existing lineage guard. This
reader retains the predecessor binding lock through the successor transaction.
"""
from uuid import UUID

from .lifecycle_store import _require_transaction, _values, _digest, RuntimeConflict


def require_predecessor_drained(conn, *, org_id, project_id, requested_ref):
    _require_transaction(conn)
    if requested_ref is None:
        return
    predecessor=UUID(requested_ref.installation_id)
    scope=(org_id,project_id,predecessor)
    rows=conn.execute('''SELECT generation,installation_revision,package_lock_ref,revision,
        execution_epoch,enabled,operation_fence,desired_state,observed_state
        FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s
        ORDER BY generation FOR UPDATE''',scope).fetchall()
    if len(rows)!=1:
        raise RuntimeConflict('replacement requires one exact predecessor runtime binding')
    generation,irev,lockref,revision,epoch,enabled,fence,desired,observed=_values(rows[0],
        ('generation','installation_revision','package_lock_ref','revision','execution_epoch',
         'enabled','operation_fence','desired_state','observed_state'))
    if (irev!=requested_ref.revision or lockref!={'lockHash':requested_ref.lock_hash}
            or enabled is not False or fence is not True or desired!='disabled' or observed!='unknown'):
        raise RuntimeConflict('replacement predecessor is not currently disabled and fenced')
    events=conn.execute('''SELECT event.payload,event.payload_hash
        FROM extension_runtime_event event JOIN extension_runtime_operation operation
        ON (operation.org_id,operation.project_id,operation.operation_id)=
           (event.org_id,event.project_id,event.operation_id)
        WHERE operation.org_id=%s AND operation.project_id=%s AND operation.installation_id=%s
          AND operation.kind='disable' AND operation.status='succeeded' AND operation.phase='succeeded'
          AND event.type='disabled_committed' AND event.payload->>'generation'=%s
          AND event.payload->>'bindingRevision'=%s AND event.payload->>'executionEpoch'=%s''',
        (*scope,str(generation),str(revision),str(epoch))).fetchall()
    expected=dict(installationId=str(predecessor),generation=str(generation),bindingRevision=revision,
        executionEpoch=epoch,resourcesRetained=True)
    if len(events)!=1:
        raise RuntimeConflict('replacement predecessor exact drain evidence is unavailable')
    payload,digest=_values(events[0],('payload','payload_hash'))
    if (type(payload) is not dict or payload!=expected or _digest(payload)!=_digest(expected)
            or digest!=_digest(payload)):
        raise RuntimeConflict('replacement predecessor drain evidence differs')
