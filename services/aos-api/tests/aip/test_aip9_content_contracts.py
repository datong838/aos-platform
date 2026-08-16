from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.aip_content_contracts import (
    AvatarSessionSnapshot,
    ContentBriefSpec,
    ContentDraftProjection,
    ContentPipelineRefs,
    MediaAssetRef,
    MediaJobSnapshot,
    PublishProposalPayload,
)


NOW = datetime.now(UTC)
HASH = "a" * 64
OTHER_HASH = "b" * 64


def exact(resource_type: str, resource_id: str, *, content_hash: str = HASH) -> dict[str, object]:
    return {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": 1,
        "contentHash": content_hash,
    }


def mutable(resource_type: str, resource_id: str) -> dict[str, object]:
    return {"resourceType": resource_type, "resourceId": resource_id, "version": 1}


def artifact(artifact_type: str, artifact_id: str) -> dict[str, object]:
    return {
        "artifactId": artifact_id,
        "artifactType": artifact_type,
        "revision": "1",
        "contentHash": HASH,
    }


def resource(resource_type: str, resource_id: str) -> dict[str, object]:
    return {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": "1",
        "authority": "aip-authority",
    }


def pipeline(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "briefRef": exact("TaskBriefRevision", "brief-1"),
        "stageTemplateRef": exact("StageTemplateRevision", "stage-1"),
        "responsibilityPlanRef": exact("ResponsibilityPlanRevision", "plan-1"),
        "evalContractRef": exact("EvalContractRevision", "eval-1"),
        "modelRouteRef": exact("ModelRouteRevision", "route-1"),
        "runtimePolicyRef": exact("RuntimePolicyRevision", "runtime-1"),
        "capabilityRefs": [exact("CapabilityRevision", "content.generate")],
        "toolBindingRefs": [mutable("ToolBinding", "tool-1")],
        "budgetRef": exact("BudgetRevision", "budget-1"),
        "readiness": "ready",
        "blockers": [],
    }
    value.update(overrides)
    return value


def media_asset() -> dict[str, object]:
    return {
        "artifactRef": artifact("image", "asset-1"),
        "mediaType": "image",
        "usage": "input",
        "provenanceRef": exact("AssetProvenanceRevision", "provenance-1"),
        "licenseRef": exact("AssetLicenseRevision", "license-1"),
        "evidenceBundleRef": exact("EvidenceBundleRevision", "evidence-1"),
        "withdrawalPolicyRef": exact("AssetWithdrawalPolicyRevision", "withdrawal-1"),
    }


def test_content_brief_is_strict_and_cannot_accept_tenant_or_unversioned_facts() -> None:
    value = {
        "briefType": "content_campaign",
        "objective": "生成真实商品种草内容",
        "deliverableKinds": ["seed_copy"],
        "channelTargets": ["weapp"],
        "productRefs": [resource("Product", "product-1")],
        "audienceRefs": [resource("AudienceSegment", "audience-1")],
        "evidenceBundleRef": exact("EvidenceBundleRevision", "evidence-1"),
        "factualClaimPolicy": "evidence_only",
        "contentConstraints": {"language": "zh-CN"},
        "cutoffAt": NOW,
    }
    assert ContentBriefSpec.model_validate(value).brief_type == "content_campaign"

    with pytest.raises(ValidationError):
        ContentBriefSpec.model_validate({**value, "orgId": "dev-org"})
    with pytest.raises(ValidationError, match="exact revision"):
        ContentBriefSpec.model_validate(
            {**value, "productRefs": [{**resource("Product", "product-1"), "revision": None}]}
        )


def test_pipeline_requires_exact_owner_refs_and_honest_blocked_state() -> None:
    assert ContentPipelineRefs.model_validate(pipeline()).readiness == "ready"

    with pytest.raises(ValidationError, match="responsibilityPlanRef"):
        ContentPipelineRefs.model_validate(
            pipeline(responsibilityPlanRef=exact("DisplayName", "content-team"))
        )
    with pytest.raises(ValidationError, match="ready pipeline cannot carry blockers"):
        ContentPipelineRefs.model_validate(
            pipeline(
                blockers=[
                    {
                        "code": "RESPONSIBILITY_TEMPLATE_AUTHORITY_MISSING",
                        "message": "missing",
                    }
                ]
            )
        )
    with pytest.raises(ValidationError, match="requires model route"):
        ContentPipelineRefs.model_validate(
            pipeline(modelRouteRef=None, runtimePolicyRef=None)
        )
    blocked = ContentPipelineRefs.model_validate(
        pipeline(
            readiness="blocked",
            modelRouteRef=None,
            runtimePolicyRef=None,
            blockers=[
                {
                    "code": "RESPONSIBILITY_TEMPLATE_AUTHORITY_MISSING",
                    "message": "ResponsibilityTemplateRevision resolver unavailable",
                    "resourceRef": exact("ResponsibilityTemplateRevision", "content-template"),
                }
            ],
        )
    )
    assert blocked.blockers[0].code == "RESPONSIBILITY_TEMPLATE_AUTHORITY_MISSING"


def test_media_asset_requires_exact_hash_provenance_license_and_withdrawal_policy() -> None:
    assert MediaAssetRef.model_validate(media_asset()).media_type == "image"
    for missing in ("provenanceRef", "licenseRef", "withdrawalPolicyRef"):
        value = media_asset()
        value.pop(missing)
        with pytest.raises(ValidationError):
            MediaAssetRef.model_validate(value)
    with pytest.raises(ValidationError, match="contentHash"):
        MediaAssetRef.model_validate(
            {**media_asset(), "artifactRef": {**artifact("image", "asset-1"), "contentHash": None}}
        )
    with pytest.raises(ValidationError, match="must match mediaType"):
        MediaAssetRef.model_validate({**media_asset(), "mediaType": "video"})


def test_content_draft_is_projection_only_and_rejects_non_draft_artifact() -> None:
    value = {
        "artifactRef": artifact("content_draft", "draft-1"),
        "briefRef": exact("TaskBriefRevision", "brief-1"),
        "pipeline": pipeline(),
        "variantKey": "weapp-seed-copy-v1",
        "channel": "weapp",
        "sourceAssets": [media_asset()],
        "evidenceBundleRef": exact("EvidenceBundleRevision", "evidence-1"),
        "evalReportRef": None,
        "reviewIssueRefs": [],
    }
    assert ContentDraftProjection.model_validate(value).channel == "weapp"
    with pytest.raises(ValidationError, match="content_draft"):
        ContentDraftProjection.model_validate(
            {**value, "artifactRef": artifact("generic_text", "draft-1")}
        )


def test_media_job_state_combinations_fail_closed() -> None:
    common = {
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "jobId": "media-job-1",
        "requestHash": HASH,
        "taskRunRef": resource("TaskRun", "run-1"),
        "stepRunRef": resource("StepRun", "step-1"),
        "jobKind": "video_render",
        "attempt": 1,
        "latestSequence": 1,
        "createdAt": NOW,
        "updatedAt": NOW,
    }
    with pytest.raises(ValidationError, match="running media job requires"):
        MediaJobSnapshot.model_validate({**common, "status": "running"})
    with pytest.raises(ValidationError, match="succeeded media job requires"):
        MediaJobSnapshot.model_validate({**common, "status": "succeeded"})
    succeeded = MediaJobSnapshot.model_validate(
        {
            **common,
            "status": "succeeded",
            "outputArtifactRefs": [artifact("video", "video-1")],
            "completionReceiptRef": exact("MediaJobReceipt", "receipt-1"),
            "finishedAt": NOW,
        }
    )
    assert succeeded.status == "succeeded"


def test_avatar_live_requires_human_heartbeat_budget_binding_and_kill_policy() -> None:
    common = {
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "sessionId": "avatar-session-1",
        "requestHash": HASH,
        "taskRunRef": resource("TaskRun", "run-1"),
        "stepRunRef": resource("StepRun", "step-1"),
        "capabilityBindingRef": mutable("CapabilityBinding", "avatar-binding-1"),
        "budgetRef": exact("BudgetRevision", "budget-1"),
        "killPolicyRef": exact("KillPolicyRevision", "kill-1"),
        "maxDurationSeconds": 300,
        "latestSequence": 1,
        "createdAt": NOW,
        "updatedAt": NOW,
    }
    with pytest.raises(ValidationError, match="human heartbeat"):
        AvatarSessionSnapshot.model_validate({**common, "status": "live"})
    live = AvatarSessionSnapshot.model_validate(
        {
            **common,
            "status": "live",
            "humanHeartbeatAt": NOW,
            "humanHeartbeatExpiresAt": NOW + timedelta(seconds=30),
            "engineSessionRef": exact("OpaqueAvatarEngineSessionRef", "engine-session-1"),
        }
    )
    assert live.status == "live"


def test_publish_proposal_payload_cannot_claim_execution_or_platform_receipt() -> None:
    value = {
        "actionType": "publish_content",
        "contentDraftRef": artifact("content_draft", "draft-1"),
        "channel": "weapp",
        "accountRef": mutable("PlatformAccountBinding", "account-1"),
        "harnessRevisionRef": exact("PlatformHarnessRevision", "weapp-harness"),
        "impactPreviewRef": exact("ImpactPreviewRevision", "preview-1"),
        "evidenceBundleRef": exact("EvidenceBundleRevision", "evidence-1"),
        "requestedMode": "proposal_only",
    }
    assert PublishProposalPayload.model_validate(value).requested_mode == "proposal_only"
    with pytest.raises(ValidationError):
        PublishProposalPayload.model_validate({**value, "published": True})
    with pytest.raises(ValidationError):
        PublishProposalPayload.model_validate({**value, "platformReceipt": "fake"})


def test_solution_pack_schemas_are_strict_draft_2020_12_contracts() -> None:
    schema_dir = (
        Path(__file__).resolve().parents[4]
        / "bundles/solutions/ecommerce-growth/content/schemas"
    )
    files = {
        "content-brief.schema.json",
        "content-pipeline.schema.json",
        "content-draft.schema.json",
        "publish-proposal.schema.json",
    }
    for name in files:
        schema = json.loads((schema_dir / name).read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["type"] == "object"
        assert isinstance(schema["properties"], dict)
        assert schema["additionalProperties"] is False
        assert schema["required"]
        assert set(schema["required"]).issubset(schema["properties"])
