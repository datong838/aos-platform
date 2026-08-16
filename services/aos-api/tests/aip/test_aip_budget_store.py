from datetime import UTC, datetime, timedelta
import uuid

import pytest

from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_store import (
    AipBudgetAuthorityStore,
    BudgetIdempotencyConflict,
    BudgetNotFound,
)
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
        lifecycle="active",
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
