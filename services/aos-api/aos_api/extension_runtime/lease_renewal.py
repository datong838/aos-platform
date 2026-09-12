"""Renew a live verified generation; never revive released/expired resources."""
from datetime import timedelta
from uuid import UUID
from aos_api.asset_registry.installation_service import _load_current_lock
from .lifecycle_store import _require_transaction, _values, RuntimeConflict, RuntimeOperationStore
from .preparation_commit import _expected_backend_claims, _registered_resources
from .verification_commit import _fresh_health
from .runtime_gate import _reject_deferred


def renew_verified_lease(conn, *, installation_store, revalidator, check_current_permission,
                         check_current_conditions, org_id, project_id, installation_id,
                         operation_id, generation, health_checked_at):
    _require_transaction(conn)
    installation_id, operation_id, generation = map(UUID, map(str, (installation_id, operation_id, generation)))
    target = (org_id, project_id, installation_id)
    head = conn.execute('''SELECT etag_version FROM bundle_installation
        WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''', target).fetchone()
    if head is None: raise LookupError('installation not found')
    locked = installation_store.lock_for_transition_in_transaction(conn, org_id=org_id,
        project_id=project_id, installation_id=str(installation_id),
        expected_etag_version=_values(head, ('etag_version',))[0])
    if locked.record.state != 'active':
        raise RuntimeConflict('lease renewal requires active installation')
    operation = conn.execute('''SELECT kind,status,phase,requested_by,revision
        FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s
        AND installation_id=%s AND operation_id=%s FOR UPDATE''', (*target, operation_id)).fetchone()
    if operation is None: raise LookupError('preparation operation not found')
    kind, status, phase, actor, revision = _values(operation, ('kind','status','phase','requested_by','revision'))
    if (kind, status, phase) != ('runtime-apply', 'succeeded', 'succeeded'):
        raise RuntimeConflict('lease renewal requires committed preparation')
    permission = check_current_permission(conn=conn, locked=locked, actor=actor)
    _reject_deferred(permission)
    if permission is not True: raise RuntimeConflict('current lease permission required')
    lock = _load_current_lock(conn, locked=locked, org_id=org_id, project_id=project_id)
    binding = conn.execute('''SELECT installation_revision,package_lock_ref,observed_state,
        desired_state,resource_handle_ref FROM extension_runtime_binding
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s FOR UPDATE''',
        (*target, generation)).fetchone()
    if binding is None: raise LookupError('verified binding not found')
    installed, package, observed, desired, handle = _values(binding,
        ('installation_revision','package_lock_ref','observed_state','desired_state','resource_handle_ref'))
    if (installed != locked.record.current_revision or package != {'lockHash': lock.lock_hash}
            or observed != 'ready' or desired not in {'disabled','enabled'}
            or not isinstance(handle, dict) or handle.get('preparationOperationId') != str(operation_id)):
        raise RuntimeConflict('verified binding cannot renew')
    checked = revalidator.revalidate_in_transaction(conn, lock=lock)
    expected = _expected_backend_claims(lock, checked)
    now = _values(conn.execute('SELECT clock_timestamp() AS now').fetchone(), ('now',))[0]
    expires = now + timedelta(seconds=180)
    proofs, expiries = _registered_resources(conn, (org_id,project_id,operation_id), generation, expected, expires)
    if handle.get('resources') != proofs:
        raise RuntimeConflict('lease resources differ from verified binding')
    conditions = check_current_conditions(conn=conn, locked=locked, lock=lock, actor=actor)
    _reject_deferred(conditions)
    if conditions is not True: raise RuntimeConflict('current lease conditions required')
    _fresh_health(conn, health_checked_at)
    rows = conn.execute('''UPDATE extension_runtime_resource_lease SET expires_at=%s
        WHERE org_id=%s AND project_id=%s AND operation_id=%s AND generation=%s
        AND NOT observed_release AND cleanup_state='pending' AND expires_at>clock_timestamp()
        RETURNING resource_id''', (expires,org_id,project_id,operation_id,generation)).fetchall()
    if len(rows) != len(expected):
        raise RuntimeConflict('lease expired before renewal commit')
    conn.execute('''UPDATE extension_runtime_operation SET revision=revision+1
        WHERE org_id=%s AND project_id=%s AND operation_id=%s''', (org_id,project_id,operation_id))
    RuntimeOperationStore._event(conn,org_id,project_id,operation_id,revision+1,
        'runtime_lease_renewed', {'generation':str(generation), 'expiresAt':expires.isoformat(),
                               'healthCheckedAt':health_checked_at.isoformat()})
    return expires
