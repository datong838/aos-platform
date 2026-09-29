from datetime import UTC, datetime, timedelta
import uuid

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevisionCreate, QuotaPolicyRevisionCreate
from aos_api.aip_model_governance_policy_store import (
    AipModelGovernancePolicyStore, ModelGovernancePolicyDependencyBlocked,
    ModelGovernancePolicyConflict,
    ModelGovernancePolicyIdempotencyConflict, ModelGovernancePolicyNotFound,
    QuotaPolicyApprovalRequired,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._budget_test_fixture import seed_isolated_active_budget
from tests.aip._model_governance_history_fixture import seed_historical_model_policy

SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime.now(UTC)
SUFFIX = uuid.uuid4().hex


def quota(revision=1, daily=100, *, name="primary", lifecycle="active", start=None, until=None, rpm=None, tpm=None):
    return QuotaPolicyRevisionCreate(policyId=f"test:quota:{name}:{SUFFIX}", revision=revision, environment="development",
        effectiveFrom=start or NOW - timedelta(hours=1), effectiveUntil=until or NOW + timedelta(days=30), owner="test",
        approvalRef="approval:test", lifecycle=lifecycle, maxConcurrency=2, maxInputTokens=8000,
        maxOutputTokens=2000, hourlyRequestLimit=50, dailyRequestLimit=daily,
        rpmLimit=rpm, tpmLimit=tpm, reservationLeaseSeconds=60, overflowBehavior="queue",
        allowPublicProviderFallback=False, allowAutoScale=False)


def publish_budget_revision():
    return seed_isolated_active_budget(SCOPE, "test", BudgetRevisionCreate(
        budgetId=f"test:budget:{SUFFIX}", revision=1, environment="development", currency="CNY",
        dailyLimitMinor=500, monthlyLimitMinor=5000, alertThresholdPct=80, hardStop=True,
        unknownUsageBehavior="block", effectiveFrom=NOW - timedelta(days=1), effectiveUntil=NOW + timedelta(days=60),
        owner="test", overBudgetApprover="test", lifecycle="active"))


def budget_policy(budget, *, until=None):
    return BudgetPolicyRevisionCreate(policyId=f"test:budget-policy:{SUFFIX}", revision=1, environment="development",
        effectiveFrom=NOW - timedelta(hours=1), effectiveUntil=until or NOW + timedelta(days=30), owner="test",
        approvalRef="approval:test", lifecycle="active", budgetRevisionRef={"assetType": "BudgetRevision",
        "assetId": budget.budget_id, "revision": budget.revision, "contentHash": budget.content_hash}, currency="CNY",
        hardStop=True, unknownUsageBehavior="block", unknownPriceBehavior="block", allowZeroPrice=False)


def ref(kind, item):
    return VersionedAssetRef(assetType=kind, assetId=item.policy_id, revision=item.revision, contentHash=item.content_hash)


def test_store_cas_replay_exact_read_and_tenant_isolation() -> None:
    store = AipModelGovernancePolicyStore()
    first = store.publish_quota(SCOPE, "test", f"quota-v1:{SUFFIX}", quota(lifecycle="draft"), expected_version=0)
    assert store.publish_quota(SCOPE, "test", f"quota-v1:{SUFFIX}", quota(lifecycle="draft"), expected_version=0) == first
    with pytest.raises(ModelGovernancePolicyIdempotencyConflict):
        store.publish_quota(SCOPE, "test", f"quota-v1:{SUFFIX}", quota(daily=101, lifecycle="draft"), expected_version=0)
    with pytest.raises(ModelGovernancePolicyNotFound):
        store.get_quota(CANARY, first.policy_id)
    with pytest.raises(ModelGovernancePolicyDependencyBlocked, match="not active"):
        store.require_exact_active(SCOPE, ref("QuotaPolicyRevision", first), now=NOW)


def test_quota_head_exposes_versioned_rpm_tpm_without_rewriting_old_revision() -> None:
    store = AipModelGovernancePolicyStore()
    first = store.publish_quota(
        SCOPE, "test", f"quota-head-v1:{SUFFIX}", quota(name="head", lifecycle="draft"), expected_version=0
    )
    assert first.rpm_limit is None and first.tpm_limit is None
    current, version = store.get_quota_head(SCOPE, first.policy_id)
    assert current.revision == 1 and version == 1

    second = store.publish_quota(
        SCOPE,
        "test",
        f"quota-head-v2:{SUFFIX}",
        quota(name="head", revision=2, rpm=40, tpm=40_000, lifecycle="draft"),
        expected_version=1,
    )
    head, version = store.get_quota_head(SCOPE, first.policy_id)
    assert (head.revision, head.rpm_limit, head.tpm_limit, version) == (2, 40, 40_000, 2)
    assert store.get_quota(SCOPE, first.policy_id, 1).rpm_limit is None
    assert store.get_quota(SCOPE, first.policy_id, 2) == second
    with pytest.raises(ModelGovernancePolicyConflict):
        store.publish_quota(
            SCOPE,
            "test",
            f"quota-head-v3-stale:{SUFFIX}",
            quota(name="head", revision=3, rpm=45, tpm=45_000, lifecycle="draft"),
            expected_version=1,
        )


def test_exact_policy_gate_blocks_missing_drift_inactive_and_expired() -> None:
    store = AipModelGovernancePolicyStore()
    missing = VersionedAssetRef(assetType="QuotaPolicyRevision", assetId=f"missing:{SUFFIX}", revision=1, contentHash="a" * 64)
    with pytest.raises(ModelGovernancePolicyDependencyBlocked, match="unavailable"):
        store.require_exact_active(SCOPE, missing, now=NOW)
    active = seed_historical_model_policy(SCOPE, "test-history", quota(name="active"))
    assert store.require_exact_active(SCOPE, ref("QuotaPolicyRevision", active), now=NOW) == active
    drifted = ref("QuotaPolicyRevision", active).model_copy(update={"content_hash": "f" * 64})
    with pytest.raises(ModelGovernancePolicyDependencyBlocked, match="drifted"):
        store.require_exact_active(SCOPE, drifted, now=NOW)
    inactive = store.publish_quota(SCOPE, "test", f"quota-inactive:{SUFFIX}", quota(name="inactive", lifecycle="blocked"))
    with pytest.raises(ModelGovernancePolicyDependencyBlocked, match="not active"):
        store.require_exact_active(SCOPE, ref("QuotaPolicyRevision", inactive), now=NOW)
    expired = seed_historical_model_policy(SCOPE, "test-history", quota(
        name="expired", start=NOW - timedelta(days=3), until=NOW - timedelta(days=1)))
    with pytest.raises(ModelGovernancePolicyDependencyBlocked, match="outside effective window"):
        store.require_exact_active(SCOPE, ref("QuotaPolicyRevision", expired), now=NOW)


def test_new_active_quota_rejects_string_only_approval() -> None:
    store = AipModelGovernancePolicyStore()
    request = quota(name="unapproved")
    with pytest.raises(QuotaPolicyApprovalRequired, match="exact approval"):
        store.publish_quota(SCOPE, "test", f"quota-unapproved:{SUFFIX}", request)
    with pytest.raises(ModelGovernancePolicyNotFound):
        store.get_quota(SCOPE, request.policy_id)


def test_budget_policy_requires_exact_active_budget_and_bounded_window() -> None:
    store = AipModelGovernancePolicyStore()
    budget = publish_budget_revision()
    item = store.publish_budget(SCOPE, "test", f"budget-policy:{SUFFIX}", budget_policy(budget))
    store.require_exact_active(SCOPE, ref("BudgetPolicyRevision", item), now=NOW)
    drifted = budget_policy(budget).model_copy(update={"budget_revision_ref": VersionedAssetRef(
        assetType="BudgetRevision", assetId=budget.budget_id, revision=1, contentHash="f" * 64)})
    with pytest.raises(ModelGovernancePolicyDependencyBlocked, match="drifted"):
        store.publish_budget(SCOPE, "test", f"budget-drift:{SUFFIX}", drifted)
    with pytest.raises(ModelGovernancePolicyDependencyBlocked, match="window exceeds"):
        store.publish_budget(SCOPE, "test", f"budget-window:{SUFFIX}", budget_policy(budget, until=NOW + timedelta(days=90)))
