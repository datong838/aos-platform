from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevisionCreate, QuotaPolicyRevisionCreate

NOW = datetime(2026, 8, 17, tzinfo=UTC)


def quota_body() -> dict:
    return {"policyId": "quota-dev", "revision": 1, "environment": "development",
            "effectiveFrom": NOW.isoformat(), "effectiveUntil": (NOW + timedelta(days=30)).isoformat(),
            "owner": "杜大同", "approvalRef": "approval:r1-07", "lifecycle": "active",
            "maxConcurrency": 2, "maxInputTokens": 8000, "maxOutputTokens": 2000,
            "hourlyRequestLimit": 50, "dailyRequestLimit": 200, "reservationLeaseSeconds": 60,
            "overflowBehavior": "queue", "allowPublicProviderFallback": False, "allowAutoScale": False}


def budget_body() -> dict:
    return {"policyId": "budget-policy-dev", "revision": 1, "environment": "development",
            "effectiveFrom": NOW.isoformat(), "effectiveUntil": (NOW + timedelta(days=30)).isoformat(),
            "owner": "杜大同", "approvalRef": "approval:r1-08", "lifecycle": "active",
            "budgetRevisionRef": {"assetType": "BudgetRevision", "assetId": "budget-dev", "revision": 1, "contentHash": "a" * 64},
            "currency": "CNY", "hardStop": True, "unknownUsageBehavior": "block",
            "unknownPriceBehavior": "block", "allowZeroPrice": False}


def test_approved_quota_and_budget_policy_contracts_are_fail_closed() -> None:
    quota = QuotaPolicyRevisionCreate.model_validate(quota_body())
    budget = BudgetPolicyRevisionCreate.model_validate(budget_body())
    assert quota.max_concurrency == 2 and quota.allow_auto_scale is False
    assert budget.hard_stop is True and budget.unknown_price_behavior == "block"


@pytest.mark.parametrize(("field", "value"), [
    ("maxConcurrency", 3), ("maxInputTokens", 8001), ("maxOutputTokens", 2001),
    ("hourlyRequestLimit", 51), ("dailyRequestLimit", 201), ("reservationLeaseSeconds", 30),
    ("allowPublicProviderFallback", True), ("allowAutoScale", True),
])
def test_quota_rejects_values_outside_approved_development_cap(field, value) -> None:
    body = quota_body(); body[field] = value
    with pytest.raises(ValidationError):
        QuotaPolicyRevisionCreate.model_validate(body)


def test_quota_daily_limit_must_cover_hourly_limit() -> None:
    body = quota_body(); body["hourlyRequestLimit"] = 50; body["dailyRequestLimit"] = 49
    with pytest.raises(ValidationError, match="dailyRequestLimit"):
        QuotaPolicyRevisionCreate.model_validate(body)


def test_quota_rpm_and_tpm_limits_must_be_configured_together() -> None:
    rpm_only = quota_body()
    rpm_only["rpmLimit"] = 120
    with pytest.raises(ValidationError, match="configured together"):
        QuotaPolicyRevisionCreate.model_validate(rpm_only)

    tpm_only = quota_body()
    tpm_only["tpmLimit"] = 240_000
    with pytest.raises(ValidationError, match="configured together"):
        QuotaPolicyRevisionCreate.model_validate(tpm_only)

    paired = quota_body()
    paired.update({"rpmLimit": 120, "tpmLimit": 240_000})
    quota = QuotaPolicyRevisionCreate.model_validate(paired)

    assert quota.rpm_limit == 120
    assert quota.tpm_limit == 240_000


@pytest.mark.parametrize(("field", "value"), [
    ("currency", "USD"), ("hardStop", False), ("unknownUsageBehavior", "reconcile"),
    ("unknownPriceBehavior", "reconcile"),
])
def test_budget_policy_rejects_non_fail_closed_boundary(field, value) -> None:
    body = budget_body(); body[field] = value
    with pytest.raises(ValidationError):
        BudgetPolicyRevisionCreate.model_validate(body)


def test_zero_price_requires_explicit_approval_and_authority_fields_cannot_be_injected() -> None:
    body = budget_body(); body["allowZeroPrice"] = True
    with pytest.raises(ValidationError, match="zeroPriceApprovalRef"):
        BudgetPolicyRevisionCreate.model_validate(body)
    for key, value in (("tenant", {"orgId": "dev-org", "projectId": "dev-project"}),
                       ("contentHash", "b" * 64), ("createdBy", "caller"), ("createdAt", NOW.isoformat())):
        injected = budget_body(); injected[key] = value
        with pytest.raises(ValidationError):
            BudgetPolicyRevisionCreate.model_validate(injected)
