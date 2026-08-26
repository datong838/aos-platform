"""BI-W5-05 canonical EvidenceBundle BuildJob adapter tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_business_investigation_evidence import (
    BusinessInvestigationEvidenceBlocked,
    BusinessInvestigationEvidenceBuildRequest,
    BusinessInvestigationEvidenceBuilder,
)
from aos_api.aip_business_investigation_runtime import (
    BusinessInvestigationRuntimeBinding,
    CanonicalCheckpointRef,
    CanonicalRuntimeRef,
)
from aos_api.aip_contracts import TaskRunStatus, TenantContext
from aos_api.aip_production_contracts import (
    BriefLifecycle,
    Coverage,
    EvidenceBundleRevision,
    ExactRevisionRef,
    Freshness,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def exact(kind: str, identity: str, fill: str) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=kind,
        resource_id=identity,
        revision=1,
        content_hash=fill * 64,
    )


def runtime(*, checkpoint: bool = True) -> BusinessInvestigationRuntimeBinding:
    return BusinessInvestigationRuntimeBinding(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        case_ref=exact("BusinessInvestigationCaseRevision", "case-1", "1"),
        business_investigation_run_ref=exact(
            "BusinessInvestigationRun", "investigation-run-1", "2"
        ),
        compilation_hash="3" * 64,
        task_ref=CanonicalRuntimeRef(
            resource_type="Task", resource_id="task-1", version=2
        ),
        plan_ref=exact("PlanRevision", "plan-1", "4"),
        task_run_ref=CanonicalRuntimeRef(
            resource_type="TaskRun", resource_id="task-run-1", version=3
        ),
        checkpoint_ref=(
            CanonicalCheckpointRef(
                resource_id="checkpoint-1", sequence=1, state_hash="5" * 64
            )
            if checkpoint
            else None
        ),
        task_run_status=TaskRunStatus.PAUSED,
        plan_step_count=3,
        binding_hash="6" * 64,
        start_authorized=False,
    )


def request(**changes) -> BusinessInvestigationEvidenceBuildRequest:
    value = {
        "idempotencyKey": "evidence-build-1",
        "briefRef": exact("TaskBriefRevision", "brief-1", "a"),
        "requiredFactIds": ["Order.daily_amount", "Customer.repeat_rate"],
        "supportingEvidenceRefs": [exact("Evidence", "evidence-support", "b")],
        "counterEvidenceRefs": [exact("Evidence", "evidence-counter", "c")],
        "cutoffAt": NOW,
        "marking": ["INTERNAL"],
    }
    value.update(changes)
    return BusinessInvestigationEvidenceBuildRequest.model_validate(value)


def bundle(
    req: BusinessInvestigationEvidenceBuildRequest,
    *,
    coverage: Coverage = Coverage.PARTIAL,
    missing: list[dict] | None = None,
    conflicts: list[dict] | None = None,
    uncertainties: list[dict] | None = None,
) -> EvidenceBundleRevision:
    return EvidenceBundleRevision(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        bundle_id="bundle-1",
        revision=1,
        brief_ref=req.brief_ref,
        subject_refs=req.subject_refs,
        cutoff_at=req.cutoff_at,
        item_refs=req.evidence_refs,
        coverage=coverage,
        missing=(
            [{"factId": "Customer.repeat_rate"}] if missing is None else missing
        ),
        conflicts=(
            [
                {
                    "factId": "Order.daily_amount",
                    "evidenceIds": ["evidence-support", "evidence-counter"],
                    "code": "FACT_MULTI_SOURCE",
                }
            ]
            if conflicts is None
            else conflicts
        ),
        uncertainties=(
            [{"factId": "Customer.repeat_rate", "code": "SOURCE_UNKNOWN"}]
            if uncertainties is None
            else uncertainties
        ),
        freshness=Freshness.STALE,
        marking=req.marking,
        license_summary={
            "status": "pending-policy-review",
            "authority": "business-investigation-evidence-adapter",
        },
        content_hash="d" * 64,
        lifecycle=BriefLifecycle.FROZEN,
        created_by="aip:investigation",
        created_at=NOW,
    )


class FixedBuilder:
    def __init__(self) -> None:
        self.calls = []
        self.result = None

    def build_evidence_bundle(self, scope, actor, key, body):
        self.calls.append((scope, actor, key, body))
        return self.result or bundle(request())


def test_build_delegates_once_and_preserves_unknown_conflict_and_counter() -> None:
    authority = FixedBuilder()
    req = request()
    authority.result = bundle(req)
    result = BusinessInvestigationEvidenceBuilder(authority).build(
        SCOPE, runtime(), req, "aip:investigation", created_at=NOW
    )

    assert len(authority.calls) == 1
    scope, actor, key, body = authority.calls[0]
    assert (scope, actor, key) == (SCOPE, "aip:investigation", "evidence-build-1")
    assert body.item_refs == req.evidence_refs
    assert body.required_fact_ids == req.required_fact_ids
    assert result.assessment.covered_fact_ids == ["Order.daily_amount"]
    assert result.assessment.missing_fact_ids == ["Customer.repeat_rate"]
    assert result.assessment.coverage is Coverage.PARTIAL
    assert result.assessment.freshness is Freshness.STALE
    assert result.assessment.conflicts == authority.result.conflicts
    assert result.assessment.uncertainties == authority.result.uncertainties
    assert result.assessment.counter_evidence_refs == req.counter_evidence_refs
    assert set(result.receipt.side_effects.model_dump().values()) == {0}


def test_complete_and_blocked_coverage_are_server_owned_and_conserved() -> None:
    authority = FixedBuilder()
    req = request()
    authority.result = bundle(
        req,
        coverage=Coverage.COMPLETE,
        missing=[],
        conflicts=[],
        uncertainties=[],
    )
    complete = BusinessInvestigationEvidenceBuilder(authority).build(
        SCOPE, runtime(), req, "owner", created_at=NOW
    )
    assert complete.assessment.covered_count == 2
    assert complete.assessment.missing_count == 0

    authority.result = bundle(
        req,
        coverage=Coverage.BLOCKED,
        missing=[{"factId": item} for item in req.required_fact_ids],
        conflicts=[],
    )
    blocked = BusinessInvestigationEvidenceBuilder(authority).build(
        SCOPE, runtime(), req, "owner", created_at=NOW
    )
    assert blocked.assessment.covered_count == 0
    assert blocked.assessment.missing_count == 2


def test_runtime_or_returned_bundle_drift_fails_closed() -> None:
    authority = FixedBuilder()
    req = request()
    builder = BusinessInvestigationEvidenceBuilder(authority)
    with pytest.raises(BusinessInvestigationEvidenceBlocked, match="CHECKPOINT_REQUIRED"):
        builder.build(SCOPE, runtime(checkpoint=False), req, "owner", created_at=NOW)
    with pytest.raises(
        BusinessInvestigationEvidenceBlocked, match="RUNTIME_TENANT_MISMATCH"
    ):
        builder.build(OTHER_SCOPE, runtime(), req, "owner", created_at=NOW)
    with pytest.raises(
        BusinessInvestigationEvidenceBlocked, match="CUTOFF_AFTER_CREATED_AT"
    ):
        builder.build(
            SCOPE,
            runtime(),
            request(cutoffAt=NOW + timedelta(minutes=1)),
            "owner",
            created_at=NOW,
        )

    authority.result = bundle(req).model_copy(
        update={
            "tenant": TenantContext(org_id="dev-org", project_id="dev-project")
        }
    )
    with pytest.raises(BusinessInvestigationEvidenceBlocked, match="BUNDLE_TENANT"):
        builder.build(SCOPE, runtime(), req, "owner", created_at=NOW)

    authority.result = bundle(req).model_copy(update={"marking": ["PUBLIC"]})
    with pytest.raises(BusinessInvestigationEvidenceBlocked, match="BUNDLE_MARKING"):
        builder.build(SCOPE, runtime(), req, "owner", created_at=NOW)


def test_forged_server_coverage_or_fact_drift_is_rejected() -> None:
    authority = FixedBuilder()
    req = request()
    builder = BusinessInvestigationEvidenceBuilder(authority)
    authority.result = bundle(req, coverage=Coverage.COMPLETE)
    with pytest.raises(BusinessInvestigationEvidenceBlocked, match="COVERAGE_DRIFTED"):
        builder.build(SCOPE, runtime(), req, "owner", created_at=NOW)

    authority.result = bundle(req, missing=[{"factId": "Unknown.injected"}])
    with pytest.raises(
        BusinessInvestigationEvidenceBlocked, match="MISSING_FACT_DRIFTED"
    ):
        builder.build(SCOPE, runtime(), req, "owner", created_at=NOW)


def test_request_rejects_non_exact_or_overlapping_evidence_and_payload_fields() -> None:
    shared = exact("Evidence", "evidence-shared", "e")
    with pytest.raises(ValidationError, match="must not overlap"):
        request(
            supportingEvidenceRefs=[shared],
            counterEvidenceRefs=[shared.model_copy(update={"content_hash": "f" * 64})],
        )
    with pytest.raises(ValidationError, match="must reference Evidence"):
        request(
            supportingEvidenceRefs=[exact("DataProductRevision", "data-1", "a")],
            counterEvidenceRefs=[],
        )
    with pytest.raises(ValidationError, match="bounded fact identifiers"):
        request(requiredFactIds=["SELECT * FROM evidence"])
    with pytest.raises(ValidationError, match="extra_forbidden"):
        BusinessInvestigationEvidenceBuildRequest.model_validate(
            {
                **request().model_dump(mode="json", by_alias=True),
                "coverage": "complete",
                "rawEvidence": {"rows": [1, 2, 3]},
            }
        )
