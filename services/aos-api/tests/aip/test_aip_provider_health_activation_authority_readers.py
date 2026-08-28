"""Exact Provider Health Action authority and Binding reader acceptance."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_action_store import canonical_hash
from aos_api.aip_provider_health_activation_authority_readers import (
    ActionAuthorityRows,
    BindingAuthorityRows,
    ExactActionAuthoritySelection,
    ExactBindingRef,
    ExactBindingSelection,
    build_exact_action_authority_owner_reader,
    build_exact_binding_owner_reader,
    postgres_action_authority_rows_reader,
    postgres_binding_authority_rows_reader,
)


TENANT = "org-org/dev-project"
NOW = datetime(2026, 8, 29, 1, 0, tzinfo=UTC)
CUTOFF = NOW - timedelta(seconds=1)
FRESH = NOW + timedelta(minutes=10)
PROPOSAL_HASH = "a" * 64
ACTION_HASH = "b" * 64
BINDING_HASH = "c" * 64


ACTION_SELECTION = ExactActionAuthoritySelection(
    proposal_id="proposal-provider-health",
    proposal_hash=PROPOSAL_HASH,
    proposal_version=2,
    lease_id="lease-provider-health",
    lease_owner_id="service:aip-provider-health-maintenance",
    action_type_revision_hash=ACTION_HASH,
)
BINDING_SELECTION = ExactBindingSelection(
    refs=(
        ExactBindingRef("capability", "cap-provider-text", 3, BINDING_HASH),
        ExactBindingRef("skill", "skill-data-analysis", 5, "d" * 64),
    )
)


def _approval(**changes):
    item = {
        "approval_event_id": "approval-1",
        "actor_id": "checker-1",
        "slot_id": "checker.1",
        "decision": "approved",
        "expires_at": FRESH,
        "proposal_hash": PROPOSAL_HASH,
        "action_binding_hash": None,
        "approval_policy_hash": "policy-hash",
        "eligibility_snapshot_hash": "eligibility-hash",
    }
    item.update(changes)
    return item


def _action_rows(*, receipt_count=0, proposal_changes=None, approval_changes=None, lease_changes=None):
    approval = _approval(**(approval_changes or {}))
    approval_set_hash = canonical_hash(
        [
            {
                "approvalEventId": approval["approval_event_id"],
                "actorId": approval["actor_id"],
                "slotId": approval["slot_id"],
                "eligibilitySnapshotHash": approval["eligibility_snapshot_hash"],
                "expiresAt": approval["expires_at"],
            }
        ]
    )
    proposal = {
        "proposal_id": ACTION_SELECTION.proposal_id,
        "proposal_hash": PROPOSAL_HASH,
        "version": 2,
        "status": "leased",
        "expires_at": FRESH,
        "action_type_id": "aip.provider-health-probe",
        "action_type_revision_hash": ACTION_HASH,
        "action_binding_hash": None,
        "approval_policy_hash": "policy-hash",
        "minimum_approvals": 1,
    }
    proposal.update(proposal_changes or {})
    lease = {
        "lease_id": ACTION_SELECTION.lease_id,
        "proposal_id": ACTION_SELECTION.proposal_id,
        "proposal_hash": PROPOSAL_HASH,
        "status": "active",
        "owner_id": ACTION_SELECTION.lease_owner_id,
        "expires_at": FRESH,
        "action_binding_hash": None,
        "approval_set_hash": approval_set_hash,
    }
    lease.update(lease_changes or {})
    return ActionAuthorityRows(CUTOFF, proposal, (approval,), lease, receipt_count)


def _binding_item(kind, binding_id, version, dependency_hash, **changes):
    item = {
        "kind": kind,
        "binding_id": binding_id,
        "version": version,
        "status": "active",
        "dependency_snapshot_hash": dependency_hash,
        "readiness": "available",
        "last_evaluated_at": CUTOFF,
        "readiness_expires_at": FRESH,
    }
    item.update(changes)
    return item


def _binding_rows(*items):
    values = items or (
        _binding_item("capability", "cap-provider-text", 3, BINDING_HASH),
        _binding_item("skill", "skill-data-analysis", 5, "d" * 64),
    )
    return BindingAuthorityRows(NOW, tuple(values))


def test_exact_action_authority_is_green_and_read_once() -> None:
    calls = 0

    def rows(tenant, evaluated_at):
        nonlocal calls
        calls += 1
        return _action_rows()

    snapshot = build_exact_action_authority_owner_reader(
        ACTION_SELECTION, rows_reader=rows
    )(TENANT, NOW)

    assert snapshot.proposal_exact is True
    assert snapshot.approval_exact is True
    assert snapshot.lease_exact is True
    assert snapshot.receipt_authority_exact is True
    assert snapshot.lease_expires_at == FRESH
    assert calls == 1


@pytest.mark.parametrize(
    ("rows", "field"),
    [
        (_action_rows(proposal_changes={"proposal_hash": "x" * 64}), "proposal_exact"),
        (_action_rows(approval_changes={"expires_at": NOW}), "approval_exact"),
        (_action_rows(lease_changes={"approval_set_hash": "drift"}), "lease_exact"),
    ],
)
def test_action_authority_drift_fails_the_exact_stage(rows, field) -> None:
    snapshot = build_exact_action_authority_owner_reader(
        ACTION_SELECTION, rows_reader=lambda tenant, at: rows
    )(TENANT, NOW)

    assert getattr(snapshot, field) is False


def test_consumed_initial_receipt_is_not_available_receipt_authority() -> None:
    snapshot = build_exact_action_authority_owner_reader(
        ACTION_SELECTION, rows_reader=lambda tenant, at: _action_rows(receipt_count=1)
    )(TENANT, NOW)

    assert snapshot.lease_exact is True
    assert snapshot.receipt_authority_exact is False


def test_missing_action_rows_are_collected_as_false_not_exception() -> None:
    rows = ActionAuthorityRows(NOW, None, (), None, 0)
    snapshot = build_exact_action_authority_owner_reader(
        ACTION_SELECTION, rows_reader=lambda tenant, at: rows
    )(TENANT, NOW)

    assert snapshot.proposal_exact is False
    assert snapshot.approval_exact is False
    assert snapshot.lease_exact is False
    assert snapshot.receipt_authority_exact is False
    assert snapshot.lease_expires_at is None


def test_exact_binding_set_is_green_with_common_cutoff() -> None:
    snapshot = build_exact_binding_owner_reader(
        BINDING_SELECTION, rows_reader=lambda tenant, at: _binding_rows()
    )(TENANT, NOW)

    assert snapshot.exact is True
    assert snapshot.operational is True
    assert snapshot.cutoff == CUTOFF
    assert snapshot.expires_at == FRESH


@pytest.mark.parametrize(
    "items",
    [
        (_binding_item("capability", "cap-provider-text", 4, BINDING_HASH),),
        (
            _binding_item("capability", "cap-provider-text", 3, BINDING_HASH),
            _binding_item("skill", "skill-data-analysis", 5, "e" * 64),
        ),
        (
            _binding_item("capability", "cap-provider-text", 3, BINDING_HASH, status="suspended"),
            _binding_item("skill", "skill-data-analysis", 5, "d" * 64),
        ),
    ],
)
def test_binding_missing_version_hash_or_status_drift_is_not_exact(items) -> None:
    snapshot = build_exact_binding_owner_reader(
        BINDING_SELECTION,
        rows_reader=lambda tenant, at: _binding_rows(*items),
    )(TENANT, NOW)

    assert snapshot.exact is False
    assert snapshot.operational is False


def test_binding_readiness_or_cutoff_drift_is_not_operational() -> None:
    items = (
        _binding_item("capability", "cap-provider-text", 3, BINDING_HASH),
        _binding_item(
            "skill",
            "skill-data-analysis",
            5,
            "d" * 64,
            readiness="blocked",
            last_evaluated_at=CUTOFF - timedelta(seconds=1),
        ),
    )
    snapshot = build_exact_binding_owner_reader(
        BINDING_SELECTION,
        rows_reader=lambda tenant, at: _binding_rows(*items),
    )(TENANT, NOW)

    assert snapshot.exact is True
    assert snapshot.operational is False
    assert snapshot.cutoff == NOW


def test_empty_or_duplicate_binding_selection_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        ExactBindingSelection(())
    ref = ExactBindingRef("skill", "same", 1, "f" * 64)
    with pytest.raises(ValueError, match="unique"):
        ExactBindingSelection((ref, ref))


def test_wrong_tenant_rejected_before_any_owner_read() -> None:
    calls = 0

    def rows(tenant, evaluated_at):
        nonlocal calls
        calls += 1
        return _action_rows()

    reader = build_exact_action_authority_owner_reader(
        ACTION_SELECTION, rows_reader=rows
    )
    with pytest.raises(ValueError, match="not canonical"):
        reader("dev-org/dev-project", NOW)
    assert calls == 0


def test_public_snapshots_do_not_expose_payload_or_secret_fields() -> None:
    action = build_exact_action_authority_owner_reader(
        ACTION_SELECTION, rows_reader=lambda tenant, at: _action_rows()
    )(TENANT, NOW)
    binding = build_exact_binding_owner_reader(
        BINDING_SELECTION, rows_reader=lambda tenant, at: _binding_rows()
    )(TENANT, NOW)
    rendered = (repr(action) + repr(binding)).lower()

    for forbidden in ("secretref", "password", "payload", "provider_request"):
        assert forbidden not in rendered


class _Result:
    def __init__(self, *, row=None, rows=()):
        self._row = row
        self._rows = rows

    def fetchone(self):
        return self._row

    def fetchall(self):
        return list(self._rows)


class _ReadOnlyConnection:
    def __init__(self):
        self.statements = []

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.statements.append((normalized, params))
        if "CURRENT_TIMESTAMP AS observed_at" in normalized:
            return _Result(row={"observed_at": NOW})
        if "FROM aip_action_proposal" in normalized:
            return _Result(row=_action_rows().proposal)
        if "FROM aip_action_approval_event" in normalized:
            return _Result(rows=_action_rows().approvals)
        if "FROM aip_action_execution_lease" in normalized:
            return _Result(row=_action_rows().lease)
        if "FROM aip_action_receipt" in normalized:
            return _Result(row={"n": 0})
        if "FROM aip_capability_binding" in normalized:
            return _Result(rows=(_binding_rows().items[0],))
        if "FROM aip_skill_binding" in normalized:
            return _Result(rows=(_binding_rows().items[1],))
        return _Result(row={})


def test_postgres_sources_use_tenant_scoped_read_only_metadata_queries() -> None:
    conn = _ReadOnlyConnection()

    @contextmanager
    def factory():
        yield conn

    action = postgres_action_authority_rows_reader(
        ACTION_SELECTION, connect_factory=factory
    )(TENANT, NOW)
    binding = postgres_binding_authority_rows_reader(
        BINDING_SELECTION, connect_factory=factory
    )(TENANT, NOW)
    statements = " ".join(item[0] for item in conn.statements).lower()

    assert action.proposal is not None
    assert len(binding.items) == 2
    assert statements.count(
        "set transaction isolation level repeatable read read only"
    ) == 2
    assert "insert " not in statements
    assert "update " not in statements
    assert "delete " not in statements
    assert "secret_ref" not in statements
    assert "payload" not in statements
