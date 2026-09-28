"""Necessary exact-match checks for future formal budget activation consumption."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_budget_activation_authority import (
    BudgetActivationApprovalEvidence,
    BudgetActivationBlocked,
    BudgetActivationPreviewEvidence,
    require_exact_budget_activation_evidence,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 9, 28, 9, 0, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
OTHER = TenantScope("dev-org", "dev-project")


def budget() -> BudgetRevisionCreate:
    return BudgetRevisionCreate(
        budgetId="qyh-content-budget", revision=2, environment="development",
        currency="CNY", dailyLimitMinor=500, monthlyLimitMinor=5000,
        alertThresholdPct=80, hardStop=True, unknownUsageBehavior="block",
        effectiveFrom=NOW - timedelta(minutes=1),
        effectiveUntil=NOW + timedelta(days=30),
        owner="qyh-owner", overBudgetApprover="qyh-approver", lifecycle="active",
    )


def evidence():
    target = budget()
    target_hash = canonical_hash(target.model_dump(mode="json", by_alias=True))
    preview = BudgetActivationPreviewEvidence(
        scope=SCOPE, budget_id=target.budget_id, revision=target.revision,
        target_hash=target_hash, head_version=1, preview_hash="a" * 64,
        lifecycle="frozen", readiness="ready", usage_known=True,
        expires_at=NOW + timedelta(hours=1),
    )
    approval = BudgetActivationApprovalEvidence(
        scope=SCOPE, budget_id=target.budget_id, revision=target.revision,
        target_hash=target_hash, head_version=1, preview_hash=preview.preview_hash,
        maker="maker-1", checker="checker-2", checker_authorized=True,
        decision="approved", expires_at=NOW + timedelta(minutes=30),
        revoked=False, consumed=False,
    )
    return target, preview, approval


def check(target=None, preview=None, approval=None, *, scope=SCOPE, maker="maker-1", head_version=1, now=NOW):
    default_target, default_preview, default_approval = evidence()
    require_exact_budget_activation_evidence(
        scope=scope, maker=maker, target=target or default_target,
        expected_head_version=head_version, preview=preview or default_preview,
        approval=approval or default_approval, now=now,
    )


def test_exact_current_frozen_ready_approved_evidence_passes_necessary_checks() -> None:
    check()


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ("scope", "BUDGET_ACTIVATION_SCOPE_MISMATCH"),
        ("budget_id", "BUDGET_ACTIVATION_TARGET_DRIFT"),
        ("revision", "BUDGET_ACTIVATION_TARGET_DRIFT"),
        ("target_hash", "BUDGET_ACTIVATION_TARGET_DRIFT"),
        ("head_version", "BUDGET_ACTIVATION_HEAD_DRIFT"),
        ("preview_hash", "BUDGET_ACTIVATION_PREVIEW_DRIFT"),
        ("malformed_preview_hash", "BUDGET_ACTIVATION_PREVIEW_INVALID"),
        ("same_actor", "BUDGET_ACTIVATION_CHECKER_INVALID"),
        ("blank_checker", "BUDGET_ACTIVATION_CHECKER_INVALID"),
        ("unauthorized", "BUDGET_ACTIVATION_CHECKER_INVALID"),
        ("revoked", "BUDGET_ACTIVATION_APPROVAL_INVALID"),
        ("consumed", "BUDGET_ACTIVATION_APPROVAL_INVALID"),
        ("expired", "BUDGET_ACTIVATION_APPROVAL_INVALID"),
        ("unfrozen", "BUDGET_ACTIVATION_PREVIEW_INVALID"),
        ("unknown_usage", "BUDGET_ACTIVATION_PREVIEW_INVALID"),
        ("amount_drift", "BUDGET_ACTIVATION_TARGET_DRIFT"),
        ("window_drift", "BUDGET_ACTIVATION_TARGET_DRIFT"),
    ],
)
def test_stale_or_unapproved_evidence_is_blocked(change: str, code: str) -> None:
    target, preview, approval = evidence()
    kwargs = {}
    if change == "scope":
        kwargs["scope"] = OTHER
    elif change == "budget_id":
        approval = replace(approval, budget_id="other")
    elif change == "revision":
        approval = replace(approval, revision=3)
    elif change == "target_hash":
        approval = replace(approval, target_hash="b" * 64)
    elif change == "head_version":
        kwargs["head_version"] = 2
    elif change == "preview_hash":
        approval = replace(approval, preview_hash="b" * 64)
    elif change == "malformed_preview_hash":
        preview = replace(preview, preview_hash="invalid")
        approval = replace(approval, preview_hash="invalid")
    elif change == "same_actor":
        approval = replace(approval, checker="maker-1")
    elif change == "blank_checker":
        approval = replace(approval, checker="   ")
    elif change == "unauthorized":
        approval = replace(approval, checker_authorized=False)
    elif change == "revoked":
        approval = replace(approval, revoked=True)
    elif change == "consumed":
        approval = replace(approval, consumed=True)
    elif change == "expired":
        kwargs["now"] = NOW + timedelta(hours=2)
    elif change == "unfrozen":
        preview = replace(preview, lifecycle="draft")
    elif change == "unknown_usage":
        preview = replace(preview, usage_known=False)
    elif change == "amount_drift":
        target = target.model_copy(update={"daily_limit_minor": 501})
    elif change == "window_drift":
        target = target.model_copy(update={"effective_until": NOW + timedelta(days=29)})
    with pytest.raises(BudgetActivationBlocked) as error:
        check(target, preview, approval, **kwargs)
    assert error.value.code == code
