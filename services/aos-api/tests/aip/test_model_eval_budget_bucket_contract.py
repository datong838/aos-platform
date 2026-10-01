"""Model first-Eval must address the ordinary BudgetRevision ledger."""

from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_budget_reservation_contracts import (
    BudgetExactRef, ReserveBudgetRequest, derive_bucket_authorities,
    derive_model_eval_bucket_authorities,
)


NOW = datetime(2026, 10, 2, 4, 30, tzinfo=UTC)
START = NOW - timedelta(days=1)
END = NOW + timedelta(days=40)
HASH = "sha256:" + "a" * 64


def _ref(kind: str, identity: str) -> BudgetExactRef:
    return BudgetExactRef(resourceType=kind, resourceId=identity,
                          revision=1, contentHash=HASH)


def _business(budget_id: str = "budget-one"):
    request = ReserveBudgetRequest(
        operationId="ecommerce_growth_content_generate", invocationKey="content-1",
        taskRef=_ref("Task", "real-task"), policyRef=_ref("BudgetRevision", budget_id),
        pricingRef=_ref("ModelPriceSnapshotRevision", "price"),
        approvalRef=_ref("ActionApprovalEvent", "approval"),
        currency="CNY", upperBoundMinor=200,
    )
    return derive_bucket_authorities(
        request, checked_at=NOW, budget_effective_from=START,
        budget_effective_until=END, daily_limit_minor=500,
        pilot_limit_minor=5000,
    )


def _eval(**changes):
    values = dict(
        request_id="model-eval-request-1",
        budget_revision_ref=_ref("BudgetRevision", "budget-one"),
        upper_bound_minor=200, checked_at=NOW,
        budget_effective_from=START, budget_effective_until=END,
        daily_limit_minor=500, pilot_limit_minor=5000,
    )
    return derive_model_eval_bucket_authorities(**(values | changes))


def test_model_eval_and_business_share_exact_daily_and_pilot_accounts():
    business, eval_buckets = _business(), _eval()
    assert tuple(item.kind for item in eval_buckets) == ("task", "daily", "pilot")
    assert eval_buckets[1:] == business[1:]
    assert eval_buckets[0].account_id == "model-eval/model-eval-request-1"
    assert eval_buckets[0].account_id != business[0].account_id
    assert eval_buckets[0].limit_minor == 200


def test_model_eval_accounts_follow_budget_revision_not_model_policy():
    first, second = _eval(), _eval(
        budget_revision_ref=_ref("BudgetRevision", "budget-two"))
    assert first[1].account_id == "budget-one:daily"
    assert first[2].account_id == "budget-one:pilot"
    assert second[1].account_id == "budget-two:daily"
    assert second[2].account_id == "budget-two:pilot"


@pytest.mark.parametrize("change", [
    {"request_id": ""}, {"request_id": " bad"}, {"request_id": "x:y"},
    {"request_id": "x" * 190},
    {"budget_revision_ref": _ref("BudgetPolicyRevision", "budget-one")},
    {"upper_bound_minor": 0}, {"upper_bound_minor": 100_000_001},
    {"checked_at": datetime(2026, 10, 2)},
    {"checked_at": END},
])
def test_model_eval_bucket_authority_rejects_invalid_or_expired_input(change):
    with pytest.raises(ValueError):
        _eval(**change)
