"""Lost preparation may recover only before verification commits."""
import pytest
from aos_api.extension_runtime.preparation_reset import validate_reset_snapshot
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


def snapshot(**overrides):
    value = dict(state="applied", bindings=[], resources=[(True, "released")],
                 operations=[("runtime-apply", "succeeded", "succeeded"),
                             ("runtime-verify", "accepted", "accepted")])
    value.update(overrides)
    return value


def test_clean_lost_preparation_is_recoverable():
    validate_reset_snapshot(**snapshot())


@pytest.mark.parametrize("changes", [
    {"state": "active"}, {"bindings": ["binding"]}, {"resources": []},
    {"resources": [(False, "released")]}, {"resources": [(True, "pending")]},
    {"operations": [("runtime-verify", "running", "committing")]},
    {"operations": [("runtime-verify", "succeeded", "succeeded")]},
    {"operations": [("configure", "accepted", "accepted")]},
    {"operations": [("runtime-apply", "running", "registered")]},
])
def test_unsafe_snapshot_is_rejected(changes):
    with pytest.raises(RuntimeConflict):
        validate_reset_snapshot(**snapshot(**changes))


@pytest.mark.parametrize("denial", ["permission", "tenant", "cas"])
def test_reset_denial_never_mutates(denial):
    from unittest.mock import MagicMock
    from psycopg.pq import TransactionStatus
    from aos_api.extension_runtime.preparation_reset import reset_preparation
    conn, store, permission = MagicMock(), MagicMock(), MagicMock(return_value=False)
    conn.info.transaction_status = TransactionStatus.INTRANS
    if denial in {"tenant", "cas"}:
        store.lock_for_transition_in_transaction.side_effect = RuntimeConflict(denial)
    with pytest.raises(RuntimeConflict):
        reset_preparation(conn, installation_store=store, check_current_permission=permission,
            org_id="org-org", project_id="dev-project", installation_id="installation",
            expected_etag=4, actor="operator")
    conn.execute.assert_not_called()
    store._append_transition.assert_not_called()


def test_reset_evidence_preserves_source_and_hash():
    from datetime import datetime, UTC
    from aos_api.asset_registry.installation_evidence import build_event_evidence, verify_event_evidence
    args = dict(installation_id="installation", from_revision=4, to_revision=5,
        lock_hash="sha256:"+"a"*64, permission_diff_hash="sha256:"+"b"*64,
        migration_plan_hash="sha256:"+"c"*64, contribution_diff_hash="sha256:"+"d"*64,
        decision_id="decision", observed_at=datetime.now(UTC))
    evidence = build_event_evidence(evidence_type="preparation_reset", **args)
    verify_event_evidence(evidence, **args, from_state="applied")
    with pytest.raises(ValueError):
        verify_event_evidence(evidence, **args, from_state="active")
