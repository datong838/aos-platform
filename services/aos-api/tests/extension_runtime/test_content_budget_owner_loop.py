"""Original producer loop retains uncertain claims without blocking independent work."""

import asyncio
from uuid import uuid4

import pytest

from aos_api.ecommerce_content_budget_command_owner import (
    ContentBudgetCommandConflict,
    ContentBudgetCommandOwner,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


@pytest.mark.parametrize("phase", ["claim", "execute"])
@pytest.mark.parametrize("failure", [ContentBudgetCommandConflict, TimeoutError])
def test_uncertain_item_is_not_reclaimed_and_next_item_continues(monkeypatch, phase, failure):
    owner = ContentBudgetCommandOwner()
    pending = ["uncertain", "independent"]
    claimed = {}
    executed = []
    def select(scope, *, limit):
        assert scope == SCOPE and limit == 2
        return [key for key in pending if key not in claimed][:limit]
    def claim(scope, key):
        claimed[key] = uuid4()  # Simulates the original durable one-attempt claim.
        if key == "uncertain" and phase == "claim":
            raise failure("claim readback unknown")
        return claimed[key]
    def execute(scope, key, token):
        assert token == claimed[key]
        executed.append(key)
        if key == "uncertain":
            raise failure("commit/readback unknown")
        return {"status": "CONTENT_BUDGET_PENDING", "reviewKey": key}
    monkeypatch.setattr(owner, "list_pending", select)
    monkeypatch.setattr(owner, "claim", claim)
    monkeypatch.setattr(owner, "execute_claim", execute)
    assert owner.run_once(SCOPE, limit=2) == [
        {"status": "RECONCILE_REQUIRED", "reviewKey": "uncertain"},
        {"status": "CONTENT_BUDGET_PENDING", "reviewKey": "independent"},
    ]
    assert owner.run_once(SCOPE, limit=2) == []
    assert executed == (["independent"] if phase == "claim" else ["uncertain", "independent"])


def test_unclassified_error_propagates_and_does_not_claim_next_item(monkeypatch):
    owner = ContentBudgetCommandOwner()
    calls = []
    monkeypatch.setattr(owner, "list_pending", lambda *args, **kwargs: ["first", "next"])
    def claim(scope, key):
        calls.append(key)
        raise RuntimeError("programming failure")
    monkeypatch.setattr(owner, "claim", claim)
    with pytest.raises(RuntimeError, match="programming failure"):
        owner.run_once(SCOPE)
    assert calls == ["first"]


def test_selector_failure_is_not_hidden(monkeypatch):
    owner = ContentBudgetCommandOwner()
    def select(*args, **kwargs):
        raise TimeoutError("selector unavailable")
    monkeypatch.setattr(owner, "list_pending", select)
    with pytest.raises(TimeoutError, match="selector unavailable"):
        owner.run_once(SCOPE)


def test_serve_survives_item_timeout_to_process_independent_item(monkeypatch):
    owner = ContentBudgetCommandOwner()
    stop = asyncio.Event()
    calls = []
    monkeypatch.setattr(owner, "list_pending", lambda *args, **kwargs: ["uncertain", "next"])
    monkeypatch.setattr(owner, "claim", lambda *args: uuid4())
    def execute(scope, key, token):
        calls.append(key)
        if key == "uncertain":
            raise TimeoutError("commit unknown")
        stop.set()
        return {"status": "CONTENT_BUDGET_PENDING", "reviewKey": key}
    monkeypatch.setattr(owner, "execute_claim", execute)
    asyncio.run(owner.serve(stop, host_ready=lambda: True, interval_seconds=1))
    assert calls == ["uncertain", "next"]
