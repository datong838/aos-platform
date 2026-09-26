"""Budget command Owner never substitutes a guessed amount or retries unknown Host commits."""

from types import SimpleNamespace
from datetime import UTC, datetime, timedelta
from contextlib import contextmanager

import pytest

from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 9, 26, tzinfo=UTC)
TASK_REF = BudgetExactRef(resource_type="Task", resource_id="task-1", revision=1,
                          content_hash="sha256:" + "1" * 64)


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class _ApprovalConn:
    def __init__(self, events, snapshot):
        self.events = events
        self.snapshot = snapshot

    def execute(self, query, params):
        assert params[:2] == SCOPE.key
        if "FROM public.aip_action_approval_event" in query:
            return _Cursor(self.events)
        if "FROM public.aip_action_draft" in query:
            return _Cursor([{"snapshot": self.snapshot, "proposal_hash": "2" * 64}])
        raise AssertionError(query)


def _event():
    return {
        "approval_event_id": "approval-1", "proposal_id": "proposal-1",
        "proposal_version": 1, "proposal_hash": "2" * 64,
        "decision": "approved", "actor_id": "reviewer", "reason": "OK",
        "expires_at": NOW + timedelta(hours=1), "created_at": NOW,
        "action_binding_hash": "3" * 64,
    }


def test_approval_must_be_unique_exact_and_bound_to_original_amount(monkeypatch):
    from aos_api.ecommerce_content_budget_command_owner import (
        ContentBudgetCommandOwner, ContentBudgetCommandConflict,
    )
    checked = []
    def verify(self, conn, scope, ref, checked_at, *, task_ref, operation_id, upper_bound_minor):
        checked.append((ref, task_ref, operation_id, upper_bound_minor))
    monkeypatch.setattr(
        "aos_api.aip_budget_reservation_store.AipBudgetReservationStore._approval_authority", verify,
    )
    event = _event()
    ref, amount = ContentBudgetCommandOwner._approved_action(
        _ApprovalConn([event], {"payload": {"budgetUpperBoundMinor": 500}}),
        SCOPE, TASK_REF, checked_at=NOW,
    )
    assert ref.resource_type == "ActionApprovalEvent"
    assert ref.resource_id == "approval-1"
    assert ref.revision == 1
    assert ref.content_hash == canonical_hash(event, prefixed=True)
    assert amount == 500
    assert checked == [(ref, TASK_REF, "ecommerce_growth_content_generate", 500)]
    for events, snapshot in (
        ([], {"payload": {"budgetUpperBoundMinor": 500}}),
        ([event, {**event, "approval_event_id": "approval-2"}], {"payload": {"budgetUpperBoundMinor": 500}}),
        ([event], {"payload": {}}),
        ([event], {"payload": {"budgetUpperBoundMinor": 0}}),
        ([event], {"payload": {"budgetUpperBoundMinor": True}}),
    ):
        with pytest.raises(ContentBudgetCommandConflict):
            ContentBudgetCommandOwner._approved_action(
                _ApprovalConn(events, snapshot), SCOPE, TASK_REF, checked_at=NOW,
            )


def test_pending_selector_is_bounded_scoped_and_current_only():
    from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner

    class Conn:
        def execute(self, query, params):
            assert "ecommerce_growth_content_budget_command_current_a0v_104" in query
            assert "state='pending'" in query and "attempt=0" in query
            assert params == (*SCOPE.key, 2)
            return _Cursor([{"review_key": "review-1"}])

    @contextmanager
    def read(scope):
        assert scope == SCOPE
        yield Conn()

    owner = ContentBudgetCommandOwner(connect_read=read)
    assert owner.list_pending(SCOPE, limit=2) == ["review-1"]
    with pytest.raises(ValueError):
        owner.list_pending(SCOPE, limit=17)


def test_pricing_bound_uses_exact_token_unit_and_requires_approved_cover():
    from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner

    price = SimpleNamespace(input_token_price=0.5, output_token_price=1.0,
                            token_unit=1000, development_cost_authorization=None)
    assert ContentBudgetCommandOwner._minimum_bound_fen(
        price, max_input_tokens=4000, max_output_tokens=2000) == 400
    assert ContentBudgetCommandOwner._approved_bound(
        price, 500, max_input_tokens=4000, max_output_tokens=2000) == 500
    with pytest.raises(ValueError, match="approved upper bound"):
        ContentBudgetCommandOwner._approved_bound(
            price, 399, max_input_tokens=4000, max_output_tokens=2000)
    with pytest.raises(ValueError, match="price"):
        ContentBudgetCommandOwner._minimum_bound_fen(
            SimpleNamespace(input_token_price=None, output_token_price=1.0,
                            token_unit=1000, development_cost_authorization=None),
            max_input_tokens=4000, max_output_tokens=2000)
