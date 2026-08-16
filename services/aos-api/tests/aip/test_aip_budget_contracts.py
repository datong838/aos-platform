from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_budget_contracts import BudgetRevisionCreate


NOW = datetime(2026, 8, 17, tzinfo=UTC)


def payload() -> dict:
    return {
        "budgetId": "budget-qyh-content-dev",
        "revision": 1,
        "environment": "development",
        "currency": "CNY",
        "dailyLimitMinor": 500,
        "monthlyLimitMinor": 5000,
        "alertThresholdPct": 80,
        "hardStop": True,
        "unknownUsageBehavior": "block",
        "effectiveFrom": NOW.isoformat(),
        "effectiveUntil": (NOW + timedelta(days=60)).isoformat(),
        "owner": "杜大同",
        "overBudgetApprover": "杜大同",
        "lifecycle": "active",
    }


def test_budget_create_freezes_safe_development_policy() -> None:
    item = BudgetRevisionCreate.model_validate(payload())
    assert item.daily_limit_minor == 500
    assert item.hard_stop is True
    assert item.unknown_usage_behavior == "block"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("environment", "production"),
        ("currency", "USD"),
        ("dailyLimitMinor", 0),
        ("monthlyLimitMinor", -1),
        ("alertThresholdPct", 0),
        ("hardStop", False),
        ("unknownUsageBehavior", "allow"),
    ],
)
def test_budget_create_rejects_unsafe_policy(field: str, value: object) -> None:
    body = payload()
    body[field] = value
    with pytest.raises(ValidationError):
        BudgetRevisionCreate.model_validate(body)


def test_budget_create_rejects_reverse_window_and_authority_injection() -> None:
    body = payload()
    body["effectiveUntil"] = (NOW - timedelta(seconds=1)).isoformat()
    with pytest.raises(ValidationError, match="effectiveUntil"):
        BudgetRevisionCreate.model_validate(body)

    for field, value in (
        ("tenant", {"orgId": "dev-org", "projectId": "dev-project"}),
        ("contentHash", "a" * 64),
        ("createdBy", "caller"),
        ("createdAt", NOW.isoformat()),
    ):
        injected = payload()
        injected[field] = value
        with pytest.raises(ValidationError):
            BudgetRevisionCreate.model_validate(injected)
