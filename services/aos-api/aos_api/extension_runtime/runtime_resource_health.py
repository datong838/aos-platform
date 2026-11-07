"""Read durable resource liveness evidence, never recreate or authorize a session."""
from uuid import UUID


def current_resources_live(conn, *, org_id, project_id, installation_id, generation):
    row = conn.execute('''SELECT count(*) AS resource_count,
        COALESCE(bool_and(COALESCE(o.kind='runtime-apply' AND o.status='succeeded'
            AND o.phase='succeeded' AND r.observed_release IS FALSE
            AND r.cleanup_state='pending' AND r.container_id IS NOT NULL
            AND r.create_claimed_at IS NOT NULL AND r.expires_at>clock_timestamp(),false)),false) AS live,
        count(*) FILTER (WHERE o.kind='runtime-recover') AS recovery_count
        FROM extension_runtime_resource_lease r
        JOIN extension_runtime_operation o USING(org_id,project_id,operation_id)
        WHERE r.org_id=%s AND r.project_id=%s AND o.installation_id=%s AND r.generation=%s''',
        (org_id,project_id,UUID(str(installation_id)),UUID(str(generation)))).fetchone()
    if row is None:return False
    count,live=(row['resource_count'],row['live']) if isinstance(row,dict) else row[:2]
    if type(count) is not int or count <= 0:return False
    if live is True:return True
    recovered = row.get('recovery_count', 0) if isinstance(row, dict) else row[2]
    if recovered != count:return False
    return _recovered_resources_live(conn, (org_id, project_id, UUID(str(installation_id))), UUID(str(generation)))


def _recovered_resources_live(conn, target, generation):
    from .lifecycle_store import RuntimeConflict, _digest
    from .lease_renewal import _require_recovery_renewal_proof

    binding = conn.execute('''SELECT b.*,i.current_revision
        FROM extension_runtime_binding b JOIN bundle_installation i
          ON i.org_id=b.org_id AND i.project_id=b.project_id AND i.installation_id=b.installation_id
        JOIN bundle_installation_revision v
          ON v.installation_pk=i.installation_pk AND v.revision=i.current_revision
        WHERE b.org_id=%s AND b.project_id=%s AND b.installation_id=%s AND b.generation=%s
          AND i.active_revision=i.current_revision AND v.state='active' ''', (*target, generation)).fetchone()
    if (not isinstance(binding, dict) or binding['installation_revision'] != binding['current_revision']
            or binding['observed_state'] != 'ready' or binding['desired_state'] != 'disabled'):
        return False
    handle = binding['resource_handle_ref']
    if not isinstance(handle, dict) or not isinstance(handle.get('resources'), list) or not handle['resources']:
        return False
    try:
        operation = UUID(handle['preparationOperationId'])
        _require_recovery_renewal_proof(conn=conn, target=target, operation_id=operation,
            generation=generation, current_revision=binding['current_revision'], binding=binding, handle=handle)
    except (RuntimeConflict, KeyError, ValueError, TypeError):
        return False
    rows = conn.execute('''SELECT r.resource_id,r.container_id,r.package_hash,
        COALESCE(o.kind='runtime-recover' AND o.status='succeeded' AND o.phase='succeeded'
          AND o.operation_id=%s AND r.observed_release IS FALSE AND r.cleanup_state='pending'
          AND r.container_id IS NOT NULL AND r.create_claimed_at IS NOT NULL
          AND r.expires_at>clock_timestamp(),false) AS live,
        (SELECT jsonb_agg(jsonb_build_object('payload',e.payload,'payload_hash',e.payload_hash))
          FROM extension_runtime_event e WHERE e.org_id=r.org_id AND e.project_id=r.project_id
          AND e.operation_id=r.operation_id AND e.type='resource_registered'
          AND e.payload->>'resourceId'=r.resource_id::text) AS registrations
        FROM extension_runtime_resource_lease r JOIN extension_runtime_operation o
          USING(org_id,project_id,operation_id)
        WHERE r.org_id=%s AND r.project_id=%s AND o.installation_id=%s AND r.generation=%s
        ORDER BY r.resource_id''', (operation, *target, generation)).fetchall()
    proofs = handle['resources']
    if len(rows) != len(proofs):
        return False
    actual = []
    for row in rows:
        registrations = row['registrations']
        if row['live'] is not True or not isinstance(registrations, list) or len(registrations) != 1:
            return False
        event = registrations[0]
        proof = event.get('payload')
        if (not isinstance(proof, dict) or event.get('payload_hash') != _digest(proof)
                or proof.get('resourceId') != str(row['resource_id'])
                or proof.get('containerId') != row['container_id']
                or proof.get('packageHash') != row['package_hash']
                or not isinstance(proof.get('claimsHash'), str)):
            return False
        actual.append(proof)
    return actual == proofs and len({p['resourceId'] for p in actual}) == len(actual)
