from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from aos_api.aip_production_contract_store import ProductionContractDependencyBlocked
from aos_api.aip_production_contracts import CreateResponsibilityPlanRequest, ExactRevisionRef
from aos_api.aip_responsibility_profile import (
    ConfirmResponsibilityProfileRequest,
    CreateMergeDecisionRequest,
    CreateMergePolicyRequest,
    RecommendResponsibilityProfileRequest,
    ResponsibilityProfile,
)
from aos_api.aip_responsibility_profile_store import AipResponsibilityProfileStore
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 25, 5, 0, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")


def _ref(resource_type: str, resource_id: str, content_hash: str = "a" * 64) -> ExactRevisionRef:
    return ExactRevisionRef(
        resourceType=resource_type, resourceId=resource_id, revision=1, contentHash=content_hash
    )


class Result:
    def __init__(self, row: Any = None, rows: list[Any] | None = None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class ProfileConnection:
    def __init__(self) -> None:
        self.policy: dict[str, Any] | None = None
        self.recommendation: dict[str, Any] | None = None
        self.confirmation: dict[str, Any] | None = None
        self.merge_receipt: dict[str, Any] | None = None
        self.plan = {
            "slots": [
                {"slotId": "research", "responsibilityType": "research", "requiredCapabilityIds": ["cap.research"]},
                {"slotId": "draft", "responsibilityType": "drafting", "requiredCapabilityIds": ["cap.draft"]},
                {"slotId": "maker", "responsibilityType": "production", "requiredCapabilityIds": ["cap.make"]},
            ],
            "content_hash": "d" * 64,
        }
        self.assignee = {
            "status": "resolved",
            "required_capability_refs": [
                {"assetType": "CapabilityRevision", "assetId": item, "revision": 1, "contentHash": "c" * 64}
                for item in ("cap.research", "cap.draft", "cap.make")
            ],
            "snapshot_hash": "e" * 64,
            "expires_at": NOW + timedelta(minutes=10),
        }

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> Result:
        compact = " ".join(sql.split())
        values = params or ()
        if compact.startswith("INSERT INTO aip_merge_policy_revision"):
            self.policy = {
                "policy_id": values[2], "revision": values[3], "minimum_profile": values[4],
                "maximum_risk_level": values[5], "allowed_merge_groups": json.loads(values[6]),
                "protected_responsibility_types": json.loads(values[7]), "expires_at": values[8],
                "content_hash": values[9], "created_by": values[10], "created_at": values[11],
            }
            return Result()
        if "SELECT * FROM aip_merge_policy_revision" in compact:
            return Result(self.policy)
        if compact.startswith("INSERT INTO aip_profile_recommendation_revision"):
            self.recommendation = {
                "recommendation_id": values[2], "revision": 1, "subject_ref": json.loads(values[3]),
                "recommended_profile": values[4], "candidate_template_refs": json.loads(values[5]),
                "selected_template_ref": json.loads(values[6]), "policy_ref": json.loads(values[7]),
                "risk_level": values[8], "channel_count": values[9], "reason_codes": json.loads(values[10]),
                "unknown_codes": json.loads(values[11]), "snapshot_hash": values[12], "content_hash": values[13],
                "expires_at": values[14], "created_by": values[15], "created_at": values[16],
            }
            return Result()
        if "SELECT * FROM aip_profile_recommendation_revision" in compact:
            return Result(self.recommendation)
        if compact.startswith("INSERT INTO aip_profile_confirmation_receipt"):
            self.confirmation = {
                "confirmation_id": values[2], "recommendation_id": values[3], "recommendation_revision": values[4],
                "recommendation_hash": values[5], "selected_profile": values[6], "selected_template_ref": json.loads(values[7]),
                "policy_ref": json.loads(values[8]), "actor": values[9], "reason": values[10], "content_hash": values[11],
                "created_at": values[12],
            }
            return Result()
        if "SELECT * FROM aip_profile_confirmation_receipt" in compact:
            return Result(self.confirmation)
        if "SELECT slots,content_hash FROM aip_responsibility_plan_revision" in compact:
            return Result(self.plan)
        if "SELECT status,required_capability_refs,snapshot_hash,expires_at" in compact:
            return Result(self.assignee)
        if compact.startswith("INSERT INTO aip_merge_decision_receipt"):
            self.merge_receipt = {
                "receipt_id": values[2], "plan_ref": json.loads(values[3]), "policy_ref": json.loads(values[4]),
                "confirmation_id": values[5], "source_slot_ids": json.loads(values[6]), "target_slot_id": values[7],
                "merged_responsibility_types": json.loads(values[8]), "capability_union": json.loads(values[9]),
                "target_assignee_resolution_receipt_id": values[10], "actor": values[11], "reason": values[12],
                "content_hash": values[13], "created_at": values[14],
            }
            return Result()
        if "SELECT * FROM aip_merge_decision_receipt" in compact:
            return Result(self.merge_receipt)
        raise AssertionError(compact)

    def commit(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _store(connection: ProfileConnection) -> AipResponsibilityProfileStore:
    @contextmanager
    def factory(_scope: TenantScope):
        yield connection

    return AipResponsibilityProfileStore(factory, template_resolver=lambda _scope, _ref: True)


def _policy(store: AipResponsibilityProfileStore, connection: ProfileConnection):
    result = store.create_policy(
        SCOPE,
        CreateMergePolicyRequest(
            policyId="merge-policy-1", revision=1, minimumProfile="LITE",
            allowedMergeGroups=[["research", "draft", "maker"]],
            expiresAt=NOW + timedelta(hours=1),
        ),
        "user:maker", now=NOW,
    )
    assert connection.policy is not None
    return result


def _recommend(store: AipResponsibilityProfileStore, policy_hash: str):
    templates = {
        profile: _ref("ResponsibilityTemplateRevision", f"bundle://test/{profile.value.lower()}")
        for profile in ResponsibilityProfile
    }
    return store.recommend(
        SCOPE,
        RecommendResponsibilityProfileRequest(
            subjectRef=_ref("TaskBriefRevision", "brief-1"), candidateTemplateRefs=templates,
            policyRef=_ref("MergePolicyRevision", "merge-policy-1", policy_hash),
            riskLevel=2, channelCount=3, unknownCodes=[], freshnessSeconds=600,
        ),
        "user:maker", now=NOW,
    )


def test_recommendation_is_deterministic_and_confirmation_cannot_downgrade() -> None:
    connection = ProfileConnection()
    store = _store(connection)
    policy = _policy(store, connection)
    recommendation = _recommend(store, policy.content_hash)
    assert recommendation.recommended_profile is ResponsibilityProfile.STANDARD
    replay = _recommend(store, policy.content_hash)
    assert replay.recommendation_id == recommendation.recommendation_id
    assert replay.snapshot_hash == recommendation.snapshot_hash
    with pytest.raises(ProductionContractDependencyBlocked, match="DOWNGRADE"):
        store.confirm(
            SCOPE,
            ConfirmResponsibilityProfileRequest(
                recommendationId=recommendation.recommendation_id, recommendationRevision=1,
                recommendationHash=recommendation.content_hash, selectedProfile="LITE", reason="降档",
            ),
            "user:checker", now=NOW,
        )
    receipt = store.confirm(
        SCOPE,
        ConfirmResponsibilityProfileRequest(
            recommendationId=recommendation.recommendation_id, recommendationRevision=1,
            recommendationHash=recommendation.content_hash, selectedProfile="FULL", reason="主动升档",
        ),
        "user:checker", now=NOW,
    )
    assert receipt.selected_profile is ResponsibilityProfile.FULL


def test_merge_requires_allowed_real_slots_and_exact_capability_union() -> None:
    connection = ProfileConnection()
    store = _store(connection)
    policy = _policy(store, connection)
    recommendation = _recommend(store, policy.content_hash)
    confirmation = store.confirm(
        SCOPE,
        ConfirmResponsibilityProfileRequest(
            recommendationId=recommendation.recommendation_id, recommendationRevision=1,
            recommendationHash=recommendation.content_hash, selectedProfile="STANDARD", reason="接受建议",
        ),
        "user:checker", now=NOW,
    )
    request = CreateMergeDecisionRequest(
        planRef=_ref("ResponsibilityPlanRevision", "plan-1", "d" * 64),
        policyRef=_ref("MergePolicyRevision", "merge-policy-1", policy.content_hash),
        confirmationId=confirmation.confirmation_id, sourceSlotIds=["research", "draft"],
        targetSlotId="maker", targetAssigneeResolutionReceiptId="assignee-receipt-1",
        reason="相邻生产职责合并",
    )
    receipt = store.create_merge_decision(SCOPE, request, "user:maker", now=NOW)
    assert receipt.capability_union == ["cap.draft", "cap.make", "cap.research"]
    connection.assignee["required_capability_refs"] = []
    with pytest.raises(ProductionContractDependencyBlocked, match="CAPABILITY_UNION"):
        store.create_merge_decision(SCOPE, request, "user:maker", now=NOW)


def test_merge_protected_responsibility_fails_closed() -> None:
    connection = ProfileConnection()
    connection.plan["slots"][0]["responsibilityType"] = "independent_review"
    store = _store(connection)
    policy = _policy(store, connection)
    recommendation = _recommend(store, policy.content_hash)
    confirmation = store.confirm(
        SCOPE,
        ConfirmResponsibilityProfileRequest(
            recommendationId=recommendation.recommendation_id, recommendationRevision=1,
            recommendationHash=recommendation.content_hash, selectedProfile="STANDARD", reason="接受建议",
        ),
        "user:checker", now=NOW,
    )
    with pytest.raises(ProductionContractDependencyBlocked, match="PROTECTED"):
        store.create_merge_decision(
            SCOPE,
            CreateMergeDecisionRequest(
                planRef=_ref("ResponsibilityPlanRevision", "plan-1", "d" * 64),
                policyRef=_ref("MergePolicyRevision", "merge-policy-1", policy.content_hash),
                confirmationId=confirmation.confirmation_id, sourceSlotIds=["research", "draft"],
                targetSlotId="maker", targetAssigneeResolutionReceiptId="assignee-receipt-1",
                reason="非法合并",
            ),
            "user:maker", now=NOW,
        )


def test_responsibility_plan_rejects_overlapping_or_cyclic_merge_groups() -> None:
    slot = lambda slot_id: {
        "slotId": slot_id,
        "responsibilityType": f"type-{slot_id}",
        "requiredCapabilityIds": [f"cap.{slot_id}"],
        "inputSchemaRef": {"resourceType": "Schema", "resourceId": "in", "revision": "1", "authority": "aip"},
        "outputSchemaRef": {"resourceType": "Schema", "resourceId": "out", "revision": "1", "authority": "aip"},
        "gateRefs": [],
        "returnStage": "review",
        "assignee": {"kind": "agent_instance", "resourceId": "agent-1", "version": 1},
    }
    with pytest.raises(ValueError, match="overlap or form a cycle"):
        CreateResponsibilityPlanRequest.model_validate(
            {
                "profile": "legacy-standard",
                "templateRef": _ref("ResponsibilityTemplateRevision", "template-1").model_dump(by_alias=True),
                "slots": [slot(item) for item in ("research", "draft", "maker", "review")],
                "mergeDecisions": [
                    {
                        "sourceSlotIds": ["research"],
                        "targetSlotId": "maker",
                        "reason": "first",
                        "mergedResponsibilityTypes": ["type-research", "type-maker"],
                    },
                    {
                        "sourceSlotIds": ["maker"],
                        "targetSlotId": "review",
                        "reason": "cycle-through-target",
                        "mergedResponsibilityTypes": ["type-maker", "type-review"],
                    },
                ],
                "mergeDecisionReceiptIds": ["receipt-1", "receipt-2"],
            }
        )
