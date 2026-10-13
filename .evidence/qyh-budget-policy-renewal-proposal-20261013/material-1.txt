"""Renewal proposals must preserve existing money authority and remain drafts."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from aos_api.aip_budget_policy_renewal_proposal import BudgetPolicyRenewalProposal
from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevisionCreate
from aos_api.aip_model_governance_policy_store import materialize_policy
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def proposal():
    tenant = {"orgId": "org-org", "projectId": "dev-project"}
    auth = {
        "tenant": tenant,
        "provider": {"assetType": "ProviderInstanceRevision", "assetId": "provider",
                     "revision": 1, "contentHash": "a" * 64},
        "providerModelId": "model", "approvalRef": "historical-approval",
        "environment": "development",
        "effectiveFrom": "2026-09-24T00:00:00Z",
        "effectiveUntil": "2026-09-25T00:00:00Z",
    }
    old = BudgetPolicyRevisionCreate(
        policyId="policy", revision=13, owner="owner", approvalRef="historical-approval",
        lifecycle="active", effectiveFrom=auth["effectiveFrom"],
        effectiveUntil=auth["effectiveUntil"], developmentCostAuthorization=auth,
        budgetRevisionRef={"assetType": "BudgetRevision", "assetId": "budget",
                           "revision": 1, "contentHash": "b" * 64},
    )
    source = materialize_policy(TenantScope("org-org", "dev-project"), "historical-maker", old)
    target = old.model_dump(mode="json", by_alias=True)
    target.update(revision=14, lifecycle="draft", approvalRef="renewal-proposal",
                  effectiveFrom="2026-10-13T04:00:00Z", effectiveUntil="2026-10-13T04:30:00Z")
    target["developmentCostAuthorization"].update(
        approvalRef="renewal-proposal", effectiveFrom=target["effectiveFrom"],
        effectiveUntil=target["effectiveUntil"])
    return dict(schemaVersion=1, tenant=tenant, sourcePolicy=source,
                targetPolicy=target, expectedHeadVersion=13,
                makerSubject="machine-maker", checkerSubject="human-checker")


def test_valid_renewal_is_draft_and_preserves_existing_budget(proposal):
    p = BudgetPolicyRenewalProposal.model_validate(proposal)
    assert p.target_policy.lifecycle.value == "draft"
    assert p.target_policy.budget_revision_ref == p.source_policy.budget_revision_ref
    assert p.canonical_payload()["targetPolicy"]["lifecycle"] == "draft"
    assert BudgetPolicyRenewalProposal.model_validate(p.canonical_payload()).proposal_hash == p.proposal_hash


@pytest.mark.parametrize("field,value", [
    ("lifecycle", "active"), ("policyId", "different"), ("revision", 15),
    ("revision", True), ("revision", 9007199254740992), ("owner", "different"),
    ("effectiveFrom", "2026-09-24T12:00:00Z"),
])
def test_reject_target_drift(proposal, field, value):
    proposal["targetPolicy"][field] = value
    with pytest.raises(ValidationError):
        BudgetPolicyRenewalProposal.model_validate(proposal)


@pytest.mark.parametrize("field,value", [
    ("assetId", "different-budget"), ("revision", 2), ("contentHash", "c" * 64),
])
def test_exact_budget_ref_cannot_be_replaced(proposal, field, value):
    proposal["targetPolicy"]["budgetRevisionRef"][field] = value
    with pytest.raises(ValidationError):
        BudgetPolicyRenewalProposal.model_validate(proposal)


@pytest.mark.parametrize("kind", ["tenant", "provider", "model", "old-approval", "window", "zero-price"])
def test_cost_scope_cannot_expand(proposal, kind):
    target = proposal["targetPolicy"]
    auth = target["developmentCostAuthorization"]
    if kind == "tenant":
        proposal["tenant"] = {"orgId": "dev-org", "projectId": "dev-project"}
    elif kind == "provider":
        auth["provider"]["contentHash"] = "d" * 64
    elif kind == "model":
        auth["providerModelId"] = "different-model"
    elif kind == "old-approval":
        auth["approvalRef"] = target["approvalRef"] = "historical-approval"
    elif kind == "window":
        target["effectiveUntil"] = "2026-10-13T05:00:00Z"
    else:
        target["allowZeroPrice"] = True
        target["zeroPriceApprovalRef"] = "new-zero-price"
    with pytest.raises(ValidationError):
        BudgetPolicyRenewalProposal.model_validate(proposal)


@pytest.mark.parametrize("field,value", [
    ("makerSubject", " human-checker"), ("checkerSubject", "machine-maker"),
    ("expectedHeadVersion", True), ("expectedHeadVersion", 0),
    ("expectedHeadVersion", 9007199254740992), ("schemaVersion", True),
])
def test_identity_and_integer_boundaries(proposal, field, value):
    proposal[field] = value
    with pytest.raises(ValidationError):
        BudgetPolicyRenewalProposal.model_validate(proposal)


def test_copy_and_nested_mutation_cannot_create_usable_hash(proposal):
    p = BudgetPolicyRenewalProposal.model_validate(proposal)
    changed = p.model_copy(deep=True)
    changed.target_policy.budget_revision_ref.content_hash = "e" * 64
    with pytest.raises(ValidationError):
        changed.canonical_payload()
    assert p.proposal_hash == BudgetPolicyRenewalProposal.model_validate(deepcopy(proposal)).proposal_hash


def test_revoked_source_cannot_be_renewed(proposal):
    raw = proposal["sourcePolicy"].model_dump(mode="json", by_alias=True)
    raw["lifecycle"] = "revoked"
    proposal["sourcePolicy"] = raw
    with pytest.raises(ValidationError):
        BudgetPolicyRenewalProposal.model_validate(proposal)
