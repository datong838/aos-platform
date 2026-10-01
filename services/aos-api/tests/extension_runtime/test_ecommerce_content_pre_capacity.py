"""Stage tests, not proof of current business-source availability."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner, ContentBudgetCommandConflict
import aos_api.ecommerce_content_first_action_binding as binding

SCOPE = TenantScope("org-org", "dev-project")


class Cursor:
    def __init__(self, row): self.row = row
    def fetchone(self): return self.row
    def fetchall(self): return [] if self.row is None else [self.row]


def test_approval_request_can_wait_without_a_capacity_reservation(monkeypatch):
    now = datetime.now(timezone.utc)
    sources = SimpleNamespace(snapshot=SimpleNamespace(checked_at=now),
        task_ref=SimpleNamespace(resource_id="task-1"),
        action_context=SimpleNamespace(capacity=None,
            request=SimpleNamespace(task_run_ref=SimpleNamespace(resource_id="run-1")),
            budget_policy=SimpleNamespace(effective_until=now + timedelta(hours=1))),
        quota=SimpleNamespace(effective_until=now + timedelta(hours=1)))
    monkeypatch.setattr(binding, "source_envelope", lambda *a: {"schemaVersion": 2})
    request = binding._request(None, SCOPE, "review-1", 500, now + timedelta(minutes=10), sources)
    assert request.expires_at > now + timedelta(minutes=1)
    with pytest.raises(Exception, match="CURRENT_EXPIRY_REQUIRED"):
        binding._request(None, SCOPE, "review-1", 500, now + timedelta(minutes=16), sources)


def test_approval_selector_uses_capacity_intent_only_before_budget_intent(monkeypatch):
    calls = []
    class Conn:
        def execute(self, sql, args):
            assert args == (*SCOPE.key, "review-1")
            if "budget_command_intent" in sql: return Cursor(None)
            assert "content_capacity_intent" in sql
            return Cursor(dict(state="pending", attempt=0, claim_token=None))
    monkeypatch.setattr(ContentBudgetCommandOwner, "_prepare_sources", classmethod(
        lambda cls, *a, **kw: calls.append(kw) or "sources"))
    assert ContentBudgetCommandOwner._prepare_approval_sources(HostTransaction(Conn()), SCOPE, "review-1") == "sources"
    assert calls == [dict(before_capacity=True, claimed_token=None)]


def test_budget_source_default_never_falls_back_to_pre_capacity(monkeypatch):
    class Conn:
        def execute(self, sql, args):
            assert "budget_command_intent" in sql
            return Cursor(None)
    monkeypatch.setattr(ContentBudgetCommandOwner, "_prepare_approval_sources",
        classmethod(lambda *a: pytest.fail("execution fell back to approval-only source")))
    with pytest.raises(Exception, match="CURRENT_INTENT_REQUIRED"):
        binding.require_first_content_budget_source(Conn(), SCOPE, {},
            dict(firstContentReviewKey="review-1", firstContentSources={}, budgetUpperBoundMinor=500))


@pytest.mark.parametrize("state,attempt,token", [("unknown",1,uuid4()),("accepted",1,uuid4()),("pending",1,None),("claimed",1,None)])
def test_approval_selector_rejects_invalid_capacity_attempt(monkeypatch, state, attempt, token):
    class Conn:
        def execute(self, sql, args):
            return Cursor(None if "budget_command_intent" in sql else
                dict(state=state, attempt=attempt, claim_token=token))
    monkeypatch.setattr(ContentBudgetCommandOwner, "_prepare_sources", classmethod(
        lambda *a, **kw: pytest.fail("invalid attempt admitted")))
    with pytest.raises(ContentBudgetCommandConflict):
        ContentBudgetCommandOwner._prepare_approval_sources(HostTransaction(Conn()), SCOPE, "review-1")
