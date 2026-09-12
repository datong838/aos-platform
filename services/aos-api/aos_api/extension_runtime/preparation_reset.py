"""Trusted preparation recovery guards; no engine or business effects."""
from .lifecycle_store import RuntimeConflict


def reset_preparation(conn, *, installation_store, check_current_permission,
                      org_id, project_id, installation_id, expected_etag, actor):
    """Called only inside the idempotent command transaction; never creates one."""
    from .lifecycle_store import _require_transaction, _values, _digest, RuntimeOperationStore
    from .runtime_gate import _reject_deferred
    from aos_api.asset_registry.installation_service import _load_current_lock
    from aos_api.asset_registry.installation_evidence import build_event_evidence
    _require_transaction(conn)
    locked = installation_store.lock_for_transition_in_transaction(conn,
        org_id=org_id, project_id=project_id, installation_id=installation_id,
        expected_etag_version=expected_etag)
    permission = check_current_permission(conn=conn, locked=locked, actor=actor)
    _reject_deferred(permission)
    if permission is not True:
        raise RuntimeConflict("current preparation permission required")
    _load_current_lock(conn, locked=locked, org_id=org_id, project_id=project_id)
    target = (org_id, project_id, installation_id)
    bindings = conn.execute('''SELECT installation_id FROM extension_runtime_binding
        WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''', target).fetchall()
    rows = conn.execute('''SELECT operation_id,kind,status,phase,revision
        FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND installation_id=%s
        ORDER BY operation_id FOR UPDATE''', target).fetchall()
    operations = [_values(row, ('operation_id','kind','status','phase','revision')) for row in rows]
    resources = conn.execute('''SELECT r.observed_release,r.cleanup_state
        FROM extension_runtime_resource_lease r JOIN extension_runtime_operation o
        ON o.org_id=r.org_id AND o.project_id=r.project_id AND o.operation_id=r.operation_id
        WHERE o.org_id=%s AND o.project_id=%s AND o.installation_id=%s
        ORDER BY r.resource_id FOR UPDATE OF r''', target).fetchall()
    validate_reset_snapshot(state=locked.record.state, bindings=bindings,
        resources=[_values(row, ('observed_release','cleanup_state')) for row in resources],
        operations=[(kind,status,phase) for _,kind,status,phase,_ in operations])
    current = locked.record.current
    proofs = conn.execute('''SELECT e.payload,e.payload_hash FROM extension_runtime_event e
        JOIN extension_runtime_operation o ON o.org_id=e.org_id AND o.project_id=e.project_id
        AND o.operation_id=e.operation_id WHERE o.org_id=%s AND o.project_id=%s
        AND o.installation_id=%s AND o.kind='runtime-apply' AND o.status='succeeded'
        AND e.type='preparation_committed' AND e.payload->>'installationRevision'=%s''',
        (*target, str(current.revision))).fetchall()
    if len(proofs) != 1:
        raise RuntimeConflict("exact committed preparation proof required")
    proof, digest = _values(proofs[0], ('payload','payload_hash'))
    if digest != _digest(proof) or proof.get('lockHash') != current.lock_hash:
        raise RuntimeConflict("committed preparation proof differs")
    for operation_id, kind, status, phase, revision in operations:
        if status not in {'succeeded','failed','cancelled'}:
            conn.execute('''UPDATE extension_runtime_operation SET status='failed',
                revision=revision+1,failure_code='PREPARATION_OWNER_LOST'
                WHERE org_id=%s AND project_id=%s AND operation_id=%s''',
                (org_id,project_id,operation_id))
            RuntimeOperationStore._event(conn,org_id,project_id,operation_id,revision+1,
                'verification_abandoned',{'phase':phase,'installationRevision':current.revision})
    observed_at = installation_store.read_control_clock_in_transaction(conn)
    evidence = build_event_evidence(evidence_type='preparation_reset',
        installation_id=installation_id,from_revision=current.revision,to_revision=current.revision+1,
        lock_hash=current.lock_hash,permission_diff_hash=current.permission_diff_hash,
        migration_plan_hash=current.migration_plan_hash,contribution_diff_hash=current.contribution_diff_hash,
        decision_id=current.decision_id,observed_at=observed_at)
    return installation_store._append_transition(conn,locked=locked,actor=actor,
        to_state='approved',evidence=evidence,preparation_reset=True)


def validate_reset_snapshot(*, state, bindings, resources, operations):
    """Validate locked rows before any operation or installation mutation.

    Resources are (observed_release, cleanup_state). Operations are
    (kind, status, phase). A succeeded verification cannot be reset, even if
    another fault removed its binding. History must be investigated instead.
    """
    if state != "applied" or bindings:
        raise RuntimeConflict("only unbound applied preparation may reset")
    if not resources or any(released is not True or cleanup != "released"
                            for released, cleanup in resources):
        raise RuntimeConflict("preparation resources are not confirmed released")
    if ("runtime-apply", "succeeded", "succeeded") not in operations:
        raise RuntimeConflict("committed preparation history is required")
    for kind, status, phase in operations:
        if kind == "runtime-verify" and (phase == "committing" or status == "succeeded"):
            raise RuntimeConflict("committed verification cannot reset")
        if status in {"failed", "cancelled", "succeeded"}:
            continue
        if (kind != "runtime-verify" or status not in {"accepted", "running"}
                or phase not in {"accepted", "validating"}):
            raise RuntimeConflict("unresolved runtime operation prevents reset")
