from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from aos_api.aip_action_models import CreateActionProposalRequest
from aos_api.aip_action_policy import RiskDecision
from aos_api.aip_action_store import AipActionStore, AipActionTransitionBlocked
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.aip_production_contract_store import compute_action_binding_hash
from aos_api.aip_production_contracts import ExternalActionPreviewBinding, ExactRevisionRef

from test_w2d_contracts import HASH, NOW, create_request, exact
from test_w2d_store import SCOPE, _seed


def _binding(**overrides: object) -> ExternalActionPreviewBinding:
    values: dict[str, object] = {
        "purpose": "受控订单备注",
        "action_type_ref": exact("ActionTypeRevision", "order.remark"),
        "capability_ref": exact("CapabilityRevision", "copy.generate"),
        "capability_binding_ref": ExactRevisionRef(
            resource_type="CapabilityBindingRevision",
            resource_id="binding-1",
            revision=2,
            content_hash=HASH,
        ),
        "account_ref": exact("AccountBindingRevision", "account-1"),
        "adapter_capability_ref": exact("AdapterCapabilityRevision", "order.remark"),
        "risk_policy_ref": exact("RiskPolicyRevision", "risk-r2"),
        "action_budget_policy_ref": exact("ActionBudgetPolicyRevision", "budget-r2"),
        "kill_policy_ref": exact("KillPolicyRevision", "kill-r2"),
        "dry_validation_receipt_ref": exact(
            "DryValidationReceiptRevision", "dry-order-remark"
        ),
    }
    values.update(overrides)
    return ExternalActionPreviewBinding.model_validate(values)


def test_external_action_binding_requires_exact_matching_preview_envelope() -> None:
    binding = _binding()
    request = create_request(external_action_binding=binding)
    assert request.external_action_binding == binding

    with pytest.raises(ValidationError, match="capabilityRef must match"):
        create_request(
            external_action_binding=binding,
            capability_ref=exact("CapabilityRevision", "other-capability"),
        )
    with pytest.raises(ValidationError, match="accountRef must match"):
        create_request(
            external_action_binding=binding,
            account_ref={
                "resourceType": "ShopAccountBinding",
                "resourceId": "account-1",
                "version": 2,
            },
        )


def test_external_action_binding_rejects_wrong_authority_kind() -> None:
    with pytest.raises(ValidationError, match="adapter_capability_ref must reference"):
        _binding(
            adapter_capability_ref=exact("CapabilityRevision", "order.remark")
        )


def test_action_binding_hash_covers_external_binding() -> None:
    request = create_request(external_action_binding=_binding())
    common = {
        "org_id": "org-org",
        "project_id": "dev-project",
        "preview_id": "preview-1",
        "revision": 1,
        "content_hash": HASH,
        "dependency_snapshot_hash": "b" * 64,
        "binding_refs": request.model_dump(mode="json", by_alias=True)["bindingRefs"],
        "capability_ref": request.model_dump(mode="json", by_alias=True)["capabilityRef"],
        "account_ref": request.model_dump(mode="json", by_alias=True)["accountRef"],
        "expires_at": NOW,
    }
    first = compute_action_binding_hash(
        **common,
        external_action_binding=_binding().model_dump(mode="json", by_alias=True),
    )
    second = compute_action_binding_hash(
        **common,
        external_action_binding=_binding(
            kill_policy_ref=ExactRevisionRef(
                resource_type="KillPolicyRevision",
                resource_id="kill-r2",
                revision=2,
                content_hash="c" * 64,
            )
        ).model_dump(mode="json", by_alias=True),
    )
    assert first != second


def test_w5_external_action_family_requires_impact_preview_before_proposal_write() -> None:
    request, _ = _seed()
    body = CreateActionProposalRequest(
        action_type_id="order.remark",
        task_id=request.task_id,
        purpose="受控订单备注",
        payload={"remark": "仅用于合同测试"},
    )
    risk = RiskDecision(
        level=ActionRiskLevel.R2,
        floor=ActionRiskLevel.R2,
        reasons=("single_external_effect",),
        approval_policy={"executionAllowed": False, "draftOnly": True},
    )
    with pytest.raises(
        AipActionTransitionBlocked, match="EXTERNAL_ACTION_PREVIEW_REQUIRED"
    ):
        AipActionStore().create_proposal(
            SCOPE,
            "test:w5-02",
            f"proposal-{uuid.uuid4().hex}",
            body,
            {"id": "order.remark", "revisionHash": HASH},
            risk,
        )
