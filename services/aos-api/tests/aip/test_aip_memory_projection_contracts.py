from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_eval_contracts import EvidenceQuality
from aos_api.aip_memory_projection_contracts import (
    CreateMemoryProjectionRequest,
    ImprovementConclusion,
    ImprovementMetric,
    ImprovementObservation,
    MemoryDisclosureMode,
    MemoryExposure,
    MemoryProjectionKind,
    MemoryRevisionExactRef,
)

NOW = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def asset(kind: str, identifier: str, digest: str = HASH_A) -> VersionedAssetRef:
    return VersionedAssetRef(
        assetType=kind,
        assetId=identifier,
        revision=1,
        contentHash=digest,
    )


def resource(kind: str, identifier: str) -> ResourceRef:
    return ResourceRef(
        resourceType=kind,
        resourceId=identifier,
        revision="1",
        authority="postgresql",
    )


def request(kind: str = "personal", recipients=None) -> CreateMemoryProjectionRequest:
    return CreateMemoryProjectionRequest(
        projectionId="projection-1",
        kind=kind,
        ownerInstanceRef=asset("AgentInstance", "agent-owner"),
        memoryRef=MemoryRevisionExactRef(
            memoryItemId="memory-1", revision=2, contentHash=HASH_B
        ),
        recipientInstanceRefs=recipients or [],
        allowedPurposes=["skill.content.plan"],
        allowedMarkings=["internal"],
        disclosure=MemoryDisclosureMode.CITATION_ONLY,
        effectiveAt=NOW,
        expiresAt=NOW + timedelta(days=30),
    )


def test_projection_contract_is_reference_only_and_camel_case() -> None:
    payload = request().model_dump(mode="json", by_alias=True)
    assert payload["ownerInstanceRef"]["assetType"] == "AgentInstance"
    assert payload["memoryRef"] == {
        "memoryItemId": "memory-1",
        "revision": 2,
        "contentHash": HASH_B,
    }
    assert "payload" not in payload and "roleKey" not in payload
    with pytest.raises(ValidationError, match="Extra inputs"):
        CreateMemoryProjectionRequest(**payload, payload={"customer": "secret"})
    with pytest.raises(ValidationError, match="Extra inputs"):
        CreateMemoryProjectionRequest(**payload, roleKey="content_officer")


def test_personal_and_shared_require_explicit_non_self_recipients() -> None:
    with pytest.raises(ValidationError, match="personal projection"):
        request(recipients=[asset("AgentInstance", "agent-reader")])
    with pytest.raises(ValidationError, match="explicit recipients"):
        request(kind="shared")
    with pytest.raises(ValidationError, match="owner cannot"):
        request(
            kind="shared",
            recipients=[asset("AgentInstance", "agent-owner")],
        )
    shared = request(
        kind="shared",
        recipients=[asset("AgentInstance", "agent-reader", HASH_C)],
    )
    assert shared.kind is MemoryProjectionKind.SHARED


def test_projection_rejects_role_or_template_refs_duplicate_and_bad_window() -> None:
    with pytest.raises(ValidationError, match="AgentInstance"):
        request(
            kind="shared",
            recipients=[asset("AgentTemplate", "content-officer")],
        )
    with pytest.raises(ValidationError, match="unique"):
        request(
            kind="shared",
            recipients=[
                asset("AgentInstance", "agent-reader", HASH_C),
                asset("AgentInstance", "agent-reader", HASH_C),
            ],
        )
    payload = request().model_dump()
    with pytest.raises(ValidationError, match="expires_at"):
        CreateMemoryProjectionRequest(
            **{**payload, "expires_at": NOW - timedelta(seconds=1)}
        )


def test_exposure_requires_exact_trusted_runtime_references() -> None:
    exposure = MemoryExposure(
        tenant=TenantContext(orgId="org-org", projectId="dev-project"),
        exposureId="exposure-1",
        agentRunRef=resource("AgentRun", "agent-run-1"),
        taskRunRef=resource("TaskRun", "task-run-1"),
        agentInstanceRef=asset("AgentInstance", "agent-owner"),
        skillRef=asset("SkillTemplate", "skill.content.plan"),
        logicRef=asset("LogicRevision", "logic.content.plan"),
        projectionRef={
            "projectionId": "projection-1",
            "version": 1,
            "contentHash": HASH_B,
        },
        memoryRef={
            "memoryItemId": "memory-1",
            "revision": 2,
            "contentHash": HASH_C,
        },
        evalContractRef=asset("EvalContract", "eval.content"),
        timeCutoff=NOW,
        acceptedAt=NOW + timedelta(seconds=1),
        exposureHash=HASH_A,
    )
    assert exposure.agent_instance_ref.asset_id == "agent-owner"
    with pytest.raises(ValidationError, match="exact AgentRun"):
        MemoryExposure(
            **{
                **exposure.model_dump(),
                "agent_run_ref": ResourceRef(
                    resourceType="AgentRun",
                    resourceId="agent-run-1",
                    authority="postgresql",
                ),
            }
        )


def observation(quality: EvidenceQuality) -> ImprovementObservation:
    measured = quality is not EvidenceQuality.UNKNOWN
    return ImprovementObservation(
        tenant=TenantContext(orgId="org-org", projectId="dev-project"),
        observationId="observation-1",
        agentInstanceRef=asset("AgentInstance", "agent-owner"),
        metricDefinitionRef=asset("MetricDefinition", "metric.task-success"),
        evalContractRef=asset("EvalContract", "eval.content"),
        evalReportRef=asset("EvalReport", "report-1") if measured else None,
        baselineCohortRef=(
            asset("CohortSnapshot", "cohort-baseline") if measured else None
        ),
        treatmentCohortRef=(
            asset("CohortSnapshot", "cohort-treatment") if measured else None
        ),
        exposureRefs=[asset("MemoryExposure", "exposure-1")] if measured else [],
        metrics=(
            [
                ImprovementMetric(
                    metricName="task_success_rate",
                    baselineValue=0.60,
                    treatmentValue=0.72,
                    baselineSampleSize=100,
                    treatmentSampleSize=100,
                    confidenceIntervalLower=0.03,
                    confidenceIntervalUpper=0.21,
                )
            ]
            if measured
            else []
        ),
        quality=quality,
        sourceRefs=[asset("EvalReport", "report-1")] if measured else [],
        cutoffAt=NOW,
        observedAt=NOW + timedelta(minutes=1),
        conclusion=(
            ImprovementConclusion.IMPROVED
            if measured
            else ImprovementConclusion.INSUFFICIENT_EVIDENCE
        ),
        limitations=[],
        observationHash=HASH_A,
    )


def test_unknown_improvement_cannot_invent_zero_or_claim_improved() -> None:
    unknown = observation(EvidenceQuality.UNKNOWN)
    assert unknown.metrics == []
    assert unknown.conclusion is ImprovementConclusion.INSUFFICIENT_EVIDENCE
    payload = unknown.model_dump()
    with pytest.raises(ValidationError, match="must not invent"):
        ImprovementObservation(
            **{
                **payload,
                "metrics": [
                    ImprovementMetric(
                        metricName="task_success_rate",
                        baselineValue=0,
                        treatmentValue=0,
                        baselineSampleSize=1,
                        treatmentSampleSize=1,
                    )
                ],
            }
        )
    with pytest.raises(ValidationError, match="insufficient_evidence"):
        ImprovementObservation(
            **{**payload, "conclusion": ImprovementConclusion.IMPROVED}
        )


@pytest.mark.parametrize("quality", [EvidenceQuality.MEASURED, EvidenceQuality.ESTIMATED])
def test_measured_or_estimated_improvement_requires_full_exact_evidence(
    quality: EvidenceQuality,
) -> None:
    valid = observation(quality)
    assert valid.metrics[0].treatment_value == 0.72
    with pytest.raises(ValidationError, match="metrics, sources and exposures"):
        ImprovementObservation(**{**valid.model_dump(), "source_refs": []})
    with pytest.raises(ValidationError, match="exact eval and cohort"):
        ImprovementObservation(**{**valid.model_dump(), "eval_report_ref": None})
    with pytest.raises(ValidationError, match="MemoryExposure"):
        ImprovementObservation(
            **{**valid.model_dump(), "exposure_refs": [asset("AgentRun", "run-1")]}
        )


def test_improvement_rejects_duplicate_metric_names() -> None:
    valid = observation(EvidenceQuality.MEASURED)
    with pytest.raises(ValidationError, match="metric names must be unique"):
        ImprovementObservation(
            **{**valid.model_dump(), "metrics": [valid.metrics[0], valid.metrics[0]]}
        )
