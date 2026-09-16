"""Current internal Proposal authority in the caller's transaction; no writes."""
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.asset_registry.control_policy import (
    APPLY_INSTALLATION_OPERATION, APPROVE_INSTALLATION_OPERATION, require_target_markings,
)
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.ecommerce_growth_cutover_action_binding import internal_cutover_binding_hash
from aos_api.extension_runtime.current_permission import CurrentControlPermission
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.openfga import user_key, marking_key


def action_snapshot_from_row(row):
    snapshot = {
        'id': row['id'], 'name': row['name'], 'objectType': row['object_type'],
        'parameters': row['parameters'], 'requiredMarkings': row['required_markings'],
        'submissionCriteria': row['submission_criteria'],
    }
    snapshot['revisionHash'] = canonical_hash(snapshot)
    return snapshot


def require_internal_cutover_binding(*, conn, scope, actor, action_snapshot, payload, operation):
    _require_transaction(conn)
    if operation not in {APPLY_INSTALLATION_OPERATION, APPROVE_INSTALLATION_OPERATION}:
        raise ValueError('internal maker or checker operation required')
    binding = internal_cutover_binding_hash(scope=scope, action_snapshot=action_snapshot, payload=payload)
    installation_id = (payload['installationRef']['installationId']
        if action_snapshot['id'] == 'ecommerce_dispatch_configuration_refresh'
        else payload['targetInstallationId'])
    row = conn.execute('''SELECT etag_version FROM bundle_installation
        WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',
        (*scope.key, installation_id)).fetchone()
    if row is None:
        raise ValueError('current control installation unavailable')
    locked = PostgresInstallationStore().lock_for_transition_in_transaction(
        conn, org_id=scope.org_id, project_id=scope.project_id, installation_id=installation_id,
        expected_etag_version=row['etag_version'])
    CurrentControlPermission(operation=operation)(conn=conn, locked=locked, actor=actor)
    row = conn.execute('''SELECT id,name,object_type,parameters,required_markings,submission_criteria
        FROM meta_action_type WHERE id=%s FOR SHARE''', (action_snapshot['id'],)).fetchone()
    if row is None or action_snapshot_from_row(row) != action_snapshot:
        raise ValueError('current internal action snapshot differs')
    markings = action_snapshot['requiredMarkings']
    if any(type(label) is not str or not label.strip() for label in markings):
        raise ValueError('exact current action markings required')
    granted = []
    for label in sorted(set(markings)):
        rows = conn.execute('''SELECT object_key FROM authz_tuple
            WHERE org_id=%s AND project_id=%s AND user_key=%s
            AND relation='bearer' AND object_key=%s FOR SHARE''',
            (*scope.key, user_key(actor), marking_key(label))).fetchall()
        if len(rows) == 1:
            granted.append(label)
    require_target_markings(principal_markings=granted, target_markings=markings)
    # Permission has already share-locked this unique membership until caller commit.
    rows = conn.execute('''SELECT role FROM meta_membership
        WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE''', (*scope.key, actor)).fetchall()
    if len(rows) != 1:
        raise ValueError('current internal membership unavailable')
    return binding, (rows[0]['role'],)
