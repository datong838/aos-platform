"""Renew a live verified generation; never revive released/expired resources."""
from datetime import timedelta
from uuid import UUID
from psycopg.types.json import Jsonb
from aos_api.asset_registry.installation_service import _load_current_lock
from .lifecycle_store import _require_transaction, _values, RuntimeConflict, RuntimeOperationStore, _digest, _deadline_valid
from .preparation_commit import _expected_backend_claims, _registered_resources
from .verification_commit import _fresh_health
from .runtime_gate import _reject_deferred


def _renew_live_recoverable_store(conn, *, org_id, project_id, installation_id,
                                  operation_id, generation, health_checked_at):
    """Keep verified resources alive while one exact Store attempt drains.

    This path deliberately does not lock or revalidate the installation or
    binding. The attempt was admitted by the current binding, disable drains
    that attempt, and the final resource update uses the exact binding as a
    statement-time CAS before extending only its already registered resources.
    """
    target=(org_id,project_id,installation_id,generation)
    exists=conn.execute('''SELECT 1 FROM extension_runtime_execution_attempt
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
          AND operation_kind='recoverable_store' AND state='running' LIMIT 1''',target).fetchone()
    if exists is None:return None
    binding=conn.execute('''SELECT execution_epoch,enabled,operation_fence,desired_state,
        observed_state,resource_handle_ref,revision FROM extension_runtime_binding
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s''',target).fetchone()
    if binding is None:raise RuntimeConflict('live Store attempt binding unavailable')
    epoch,enabled,fence,desired,observed,handle,binding_revision=_values(binding,
        ('execution_epoch','enabled','operation_fence','desired_state','observed_state',
         'resource_handle_ref','revision'))
    if (enabled is not True or fence is not False or desired!='enabled' or observed!='ready'
            or type(epoch) is not int or type(handle) is not dict
            or handle.get('preparationOperationId')!=str(operation_id)
            or type(handle.get('resources')) is not list or not handle['resources']):
        raise RuntimeConflict('live Store attempt binding is not renewable')
    _fresh_health(conn,health_checked_at)
    attempts=conn.execute('''SELECT attempt_id,accepted_at,heartbeat_at,lease_until
        FROM extension_runtime_execution_attempt WHERE org_id=%s AND project_id=%s
          AND installation_id=%s AND generation=%s AND execution_epoch=%s
          AND operation_kind='recoverable_store' AND state='running'
        ORDER BY attempt_id FOR UPDATE''',(*target,epoch)).fetchall()
    if len(attempts)!=1:
        raise RuntimeConflict('exact live Store attempt required')
    attempt=attempts[0]
    now=_values(conn.execute('SELECT clock_timestamp() AS now').fetchone(),('now',))[0]
    accepted,heartbeat,attempt_expiry=_values(attempt,('accepted_at','heartbeat_at','lease_until'))
    last=heartbeat or accepted
    if (last is None or last>now or attempt_expiry<=now or last+timedelta(seconds=120)<now):
        raise RuntimeConflict('live Store attempt lease is not fresh')
    operation=conn.execute('''SELECT kind,status,phase,revision FROM extension_runtime_operation
        WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE''',
        (org_id,project_id,operation_id)).fetchone()
    if operation is None or _values(operation,('kind','status','phase'))!=('runtime-apply','succeeded','succeeded'):
        raise RuntimeConflict('live Store preparation operation differs')
    revision=_values(operation,('revision',))[0]
    rows=conn.execute('''SELECT resource_id,container_id,package_hash,cleanup_state,
        observed_release,expires_at FROM extension_runtime_resource_lease
        WHERE org_id=%s AND project_id=%s AND operation_id=%s AND generation=%s
        ORDER BY resource_id FOR UPDATE''',(org_id,project_id,operation_id,generation)).fetchall()
    proofs=handle['resources']
    expected={(proof.get('resourceId'),proof.get('containerId'),proof.get('packageHash'))
              for proof in proofs if type(proof) is dict and type(proof.get('claimsHash')) is str}
    actual={(str(_values(row,('resource_id',))[0]),_values(row,('container_id',))[0],
             _values(row,('package_hash',))[0]) for row in rows}
    if (len(rows)!=len(proofs) or len(expected)!=len(proofs) or actual!=expected
            or any(_values(row,('cleanup_state','observed_release'))!=('pending',False)
                   or _values(row,('expires_at',))[0]<=now for row in rows)):
        raise RuntimeConflict('live Store resource set is not renewable')
    expires=now+timedelta(seconds=180)
    renewed=conn.execute('''UPDATE extension_runtime_resource_lease r SET expires_at=%s
        WHERE org_id=%s AND project_id=%s AND operation_id=%s AND generation=%s
          AND cleanup_state='pending' AND NOT observed_release AND expires_at>clock_timestamp()
          AND EXISTS (SELECT 1 FROM extension_runtime_binding b
            WHERE b.org_id=r.org_id AND b.project_id=r.project_id
              AND b.installation_id=%s AND b.generation=r.generation
              AND b.revision=%s AND b.execution_epoch=%s AND b.enabled
              AND NOT b.operation_fence AND b.desired_state='enabled'
              AND b.observed_state='ready' AND b.resource_handle_ref=%s)
        RETURNING resource_id''',(expires,org_id,project_id,operation_id,generation,
            installation_id,binding_revision,epoch,Jsonb(handle))).fetchall()
    if len(renewed)!=len(rows):raise RuntimeConflict('live Store resources expired before renewal commit')
    conn.execute('''UPDATE extension_runtime_operation SET revision=revision+1
        WHERE org_id=%s AND project_id=%s AND operation_id=%s AND revision=%s''',
        (org_id,project_id,operation_id,revision))
    RuntimeOperationStore._event(conn,org_id,project_id,operation_id,revision+1,
        'runtime_inflight_lease_renewed',{'generation':str(generation),'executionEpoch':epoch,
        'attemptId':str(_values(attempt,('attempt_id',))[0]),'expiresAt':expires.isoformat(),
        'healthCheckedAt':health_checked_at.isoformat()})
    return expires


def _configuration_transition_owned(conn, *, target, generation, binding):
    """Retain healthy fenced resources; this never authorizes business dispatch."""
    observed, desired, enabled, fence, revision, config = _values(binding,
        ('observed_state', 'desired_state', 'enabled', 'operation_fence', 'revision', 'config_ref'))
    if (observed not in {'unknown', 'draining'} or desired not in {'disabled', 'enabled'}
            or (observed == 'unknown' and desired != 'disabled')
            or enabled is not False or fence is not True):
        return False
    rows = conn.execute("""SELECT o.operation_id,o.status,o.phase,o.deadline,e.payload,e.payload_hash
        FROM extension_runtime_operation o JOIN extension_runtime_event e
          ON e.org_id=o.org_id AND e.project_id=o.project_id AND e.operation_id=o.operation_id
        WHERE o.org_id=%s AND o.project_id=%s AND o.installation_id=%s AND o.kind='configure'
          AND ((o.status='succeeded' AND o.phase='succeeded' AND e.type='configuration_committed')
            OR (o.status='running' AND o.phase='fencing' AND e.type='fencing' AND e.sequence=o.revision))""", target).fetchall()
    matches = 0
    for row in rows:
        operation, status, phase, deadline, payload, digest = _values(row,
            ('operation_id', 'status', 'phase', 'deadline', 'payload', 'payload_hash'))
        if not isinstance(payload, dict) or _digest(payload) != digest:
            continue
        if observed == 'unknown' and (status, phase) == ('succeeded', 'succeeded'):
            if (config is not None and payload.get('installationId') == str(target[2])
                    and payload.get('generation') == str(generation)
                    and payload.get('configRef') == config and payload.get('bindingRevision') == revision
                    and payload.get('enabled') is False and payload.get('observedState') == 'unknown'):
                matches += 1
        elif observed == 'draining' and (status, phase) == ('running', 'fencing'):
            if payload != {'previousPhase': 'validating'} or not _deadline_valid(conn, deadline):
                continue
            from .configuration_request import load_configure_target
            accepted = load_configure_target(conn, org_id=target[0], project_id=target[1], operation_id=operation)
            if accepted.generation == str(generation) and accepted.bindingRevision + 1 == revision:
                matches += 1
    return matches == 1


def renew_verified_lease(conn, *, installation_store, revalidator, check_current_permission,
                         check_current_conditions, org_id, project_id, installation_id,
                         operation_id, generation, health_checked_at):
    _require_transaction(conn)
    installation_id, operation_id, generation = map(UUID, map(str, (installation_id, operation_id, generation)))
    inflight=_renew_live_recoverable_store(conn,org_id=org_id,project_id=project_id,
        installation_id=installation_id,operation_id=operation_id,generation=generation,
        health_checked_at=health_checked_at)
    if inflight is not None:return inflight
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
        desired_state,resource_handle_ref,enabled,operation_fence,revision,config_ref FROM extension_runtime_binding
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s FOR UPDATE''',
        (*target, generation)).fetchone()
    if binding is None: raise LookupError('verified binding not found')
    installed, package, observed, desired, handle = _values(binding,
        ('installation_revision','package_lock_ref','observed_state','desired_state','resource_handle_ref'))
    if (installed != locked.record.current_revision or package != {'lockHash': lock.lock_hash}
            or desired not in {'disabled','enabled'}
            or not isinstance(handle, dict) or handle.get('preparationOperationId') != str(operation_id)):
        raise RuntimeConflict('verified binding cannot renew')
    if observed != 'ready' and not _configuration_transition_owned(
            conn, target=target, generation=generation, binding=binding):
        raise RuntimeConflict('verified binding cannot renew')
    # Freshness is an admission gate after current identity locks.  Deterministic
    # lock-scoped revalidation below may exceed the three-second probe window on
    # a remote control database; it must not retroactively stale a probe that was
    # fresh when this exact generation entered its atomic renewal transaction.
    _fresh_health(conn, health_checked_at)
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
