"""Read durable resource liveness evidence, never recreate or authorize a session."""
from uuid import UUID


def current_resources_live(conn, *, org_id, project_id, installation_id, generation):
    row = conn.execute('''SELECT count(*) AS resource_count,
        COALESCE(bool_and(COALESCE(o.kind='runtime-apply' AND o.status='succeeded'
            AND o.phase='succeeded' AND r.observed_release IS FALSE
            AND r.cleanup_state='pending' AND r.container_id IS NOT NULL
            AND r.create_claimed_at IS NOT NULL AND r.expires_at>clock_timestamp(),false)),false) AS live
        FROM extension_runtime_resource_lease r
        JOIN extension_runtime_operation o USING(org_id,project_id,operation_id)
        WHERE r.org_id=%s AND r.project_id=%s AND o.installation_id=%s AND r.generation=%s''',
        (org_id,project_id,UUID(str(installation_id)),UUID(str(generation)))).fetchone()
    if row is None:return False
    count,live=(row['resource_count'],row['live']) if isinstance(row,dict) else row
    return type(count) is int and count>0 and live is True
