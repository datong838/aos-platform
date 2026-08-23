from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aos_api.aip_contracts import TenantContext
from aos_api.aip_fde_assets import FdeAdapterPackInspector
from aos_api.aip_fde_contracts import FdeIntakeRequest, FdeStepStatus
from aos_api.aip_fde_orchestrator import FdeS1S3Orchestrator
from aos_api.source_readiness_contracts import (
    CANONICAL_QYH_SOURCES,
    ExactResourceRef,
    LatestRunObservation,
    ObservationStatus,
    PolicyCheckStatus,
    PolicyObservation,
    SourceCounts,
    SourceReadinessEnvelope,
    SourceReadinessItem,
    SourceReadinessStatus,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def _intake(**overrides: object) -> FdeIntakeRequest:
    payload: dict[str, object] = {
        "requirement": "接入微商城订单与商品，形成六步受控计划",
        "platform": "niushop",
        "dataTypes": ["orders", "products"],
        "syncFrequency": "hourly",
        "secretRef": "keychain://aos/agnes-api-key",
        "secretVersion": "1",
    }
    payload.update(overrides)
    return FdeIntakeRequest.model_validate(payload)


def _ref(resource_type: str, resource_id: str) -> ExactResourceRef:
    return ExactResourceRef(
        resourceType=resource_type,
        resourceId=resource_id,
        revision="1",
        contentHash="a" * 64,
        authority="pytest canonical authority",
    )


def _ready_envelope(org_id: str = "org-org", *, mismatched_cutoff: bool = False) -> SourceReadinessEnvelope:
    checked = datetime(2026, 8, 22, 8, 0, tzinfo=timezone.utc)
    cutoff = checked - timedelta(minutes=10)
    tenant = TenantContext(orgId=org_id, projectId="dev-project")
    items = []
    for source in CANONICAL_QYH_SOURCES:
        refs = {
            name: _ref(name, f"{source.pipeline_id}:{name}")
            for name in (
                "SourceConfig",
                "Mapping",
                "Schema",
                "MaskingPolicy",
                "FreshnessPolicy",
                "QualityPolicy",
                "ReconciliationPolicy",
                "QueryCapability",
            )
        }
        items.append(
            SourceReadinessItem(
                tenant=tenant,
                sourceId=source.pipeline_id,
                pipelineId=source.pipeline_id,
                objectType=source.object_type,
                status=SourceReadinessStatus.READY,
                checkedAt=checked,
                dataCutoff=cutoff + timedelta(seconds=1) if mismatched_cutoff and source.pipeline_id == "P12-payment-qyh" else cutoff,
                freshnessExpiresAt=checked + timedelta(hours=1),
                sourceConfigRef=refs["SourceConfig"],
                mappingRef=refs["Mapping"],
                schemaRef=refs["Schema"],
                maskingPolicyRef=refs["MaskingPolicy"],
                freshnessPolicyRef=refs["FreshnessPolicy"],
                qualityPolicyRef=refs["QualityPolicy"],
                reconciliationPolicyRef=refs["ReconciliationPolicy"],
                queryCapabilityRef=refs["QueryCapability"],
                latestRun=LatestRunObservation(runId=f"run-{source.pipeline_id}", status=ObservationStatus.SUCCEEDED, rowsWritten=1),
                counts=SourceCounts(sourceTotal=1, projectionTotal=1, unexplainedDelta=0),
                quality=PolicyObservation(status=PolicyCheckStatus.PASS, ruleRef=refs["QualityPolicy"]),
                reconciliation=PolicyObservation(status=PolicyCheckStatus.PASS, ruleRef=refs["ReconciliationPolicy"]),
            )
        )
    return SourceReadinessEnvelope(
        tenant=tenant,
        checkedAt=checked,
        cutoffAt=cutoff,
        status=SourceReadinessStatus.READY,
        sources=items,
        receiptRef=_ref("EvidencePack", "same-cutoff-p01-p12"),
    )


def test_s4_normalizes_real_bundle_mappings_without_expression_execution() -> None:
    proposal = FdeAdapterPackInspector().mapping_proposal(
        "platform.ecommerce.niushop@1.0.0",
        ["orders", "products"],
    )

    assert proposal["mappingStatus"] == "proposed"
    assert proposal["expressionExecution"] is False
    assert proposal["blockers"] == []
    assert {row["pipelineId"] for row in proposal["mappings"]} == {"P02", "P05"}
    assert all(row["primaryTarget"] == "id" for row in proposal["mappings"])
    assert all(len(row["contentHash"]) == 64 for row in proposal["mappings"])


def test_s5_is_plan_only_and_browser_access_fails_closed() -> None:
    api = FdeS1S3Orchestrator().preview(SCOPE, _intake())
    browser = FdeS1S3Orchestrator().preview(SCOPE, _intake(accessMode="browser"))

    s5 = api.steps[4]
    assert s5.status is FdeStepStatus.EXTERNAL_REQUIRED
    assert s5.facts["pipelineExecuted"] is False
    assert s5.facts["databaseWrite"] is False
    assert s5.facts["automaticRetry"] is False
    assert {row["pipelineId"] for row in s5.facts["pipelinePlans"]} == {
        "P02-product-qyh",
        "P05-order-qyh",
    }
    assert "FDE_SIDE_EFFECT_AUTHORITY_REQUIRED" in s5.blocker_codes
    assert browser.steps[4].status is FdeStepStatus.BLOCKED
    assert browser.executable is False


def test_s6_accepts_only_same_tenant_canonical_ready_envelope() -> None:
    ready = FdeS1S3Orchestrator(readiness=_ready_envelope()).preview(SCOPE, _intake())
    mismatch = FdeS1S3Orchestrator(readiness=_ready_envelope("dev-org")).preview(SCOPE, _intake())
    cutoff_mismatch = FdeS1S3Orchestrator(readiness=_ready_envelope(mismatched_cutoff=True)).preview(SCOPE, _intake())

    assert ready.steps[5].status is FdeStepStatus.READY
    assert ready.steps[5].facts["sourceCount"] == 12
    assert ready.steps[5].facts["businessDataDelete"] is False
    assert mismatch.steps[5].status is FdeStepStatus.BLOCKED
    assert mismatch.steps[5].blocker_codes == ["FDE_SOURCE_READINESS_TENANT_MISMATCH"]
    assert cutoff_mismatch.steps[5].status is FdeStepStatus.BLOCKED
    assert "FDE_SOURCE_READINESS_CUTOFF_MISMATCH" in cutoff_mismatch.steps[5].blocker_codes
