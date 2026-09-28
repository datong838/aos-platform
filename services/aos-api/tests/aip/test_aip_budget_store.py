from datetime import UTC, datetime, timedelta
import uuid

import pytest

from aos_api.aip_budget_contracts import BudgetLifecycle, BudgetRevisionCreate
from aos_api.aip_budget_store import (
    AipBudgetAuthorityStore,
    BudgetActivationApprovalRequired,
    BudgetIdempotencyConflict,
    BudgetNotFound,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
ACTOR = "test:aip-budget-store"
NOW = datetime(2026, 8, 17, tzinfo=UTC)
BUDGET_ID = f"test:qyh-content-budget:{uuid.uuid4().hex}"


def item(*, daily: int = 500, revision: int = 1) -> BudgetRevisionCreate:
    return BudgetRevisionCreate(
        budgetId=BUDGET_ID,
        revision=revision,
        environment="development",
        currency="CNY",
        dailyLimitMinor=daily,
        monthlyLimitMinor=5000,
        alertThresholdPct=80,
        hardStop=True,
        unknownUsageBehavior="block",
        effectiveFrom=NOW,
        effectiveUntil=NOW + timedelta(days=60),
        owner="杜大同",
        overBudgetApprover="杜大同",
        lifecycle="draft",
    )


def test_budget_store_cas_replay_exact_read_and_tenant_isolation() -> None:
    store = AipBudgetAuthorityStore()
    first = store.publish(SCOPE, ACTOR, "budget-v1", item(), expected_version=0)
    assert first.tenant.org_id == "org-org"
    assert first.revision == 1
    assert len(first.content_hash) == 64
    assert store.publish(SCOPE, ACTOR, "budget-v1", item(), expected_version=0) == first

    with pytest.raises(BudgetIdempotencyConflict):
        store.publish(SCOPE, ACTOR, "budget-v1", item(daily=600), expected_version=0)

    second = store.publish(SCOPE, ACTOR, "budget-v2", item(daily=600, revision=2), expected_version=1)
    assert store.get(SCOPE, second.budget_id).revision == 2
    assert store.get(SCOPE, second.budget_id, 1).daily_limit_minor == 500
    with pytest.raises(BudgetNotFound):
        store.get(CANARY, second.budget_id)


def test_public_store_rejects_active_before_any_head_or_receipt_write() -> None:
    store = AipBudgetAuthorityStore()
    budget_id = f"test:active-block:{uuid.uuid4().hex}"
    active = item().model_copy(update={"budget_id": budget_id, "lifecycle": BudgetLifecycle.ACTIVE})
    with pytest.raises(BudgetActivationApprovalRequired):
        store.publish(SCOPE, ACTOR, "active-v1", active, expected_version=0)
    with connect(SCOPE) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_budget_head WHERE org_id=%s AND project_id=%s AND budget_id=%s",
            (*SCOPE.key, budget_id),
        ).fetchone()["n"] == 0

    draft = active.model_copy(update={"lifecycle": BudgetLifecycle.DRAFT})
    store.publish(SCOPE, ACTOR, "draft-before-active", draft, expected_version=0)
    with pytest.raises(BudgetActivationApprovalRequired):
        store.publish(
            SCOPE, ACTOR, "active-v2",
            active.model_copy(update={"revision": 2}), expected_version=1,
        )
    with connect(SCOPE) as conn:
        head = conn.execute(
            "SELECT current_revision,version FROM aip_budget_head WHERE org_id=%s AND project_id=%s AND budget_id=%s",
            (*SCOPE.key, budget_id),
        ).fetchone()
        assert (head["current_revision"], head["version"]) == (1, 1)
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_budget_receipt WHERE org_id=%s AND project_id=%s AND idempotency_key IN (%s,%s)",
            (*SCOPE.key, "active-v1", "active-v2"),
        ).fetchone()["n"] == 0
