from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_memory_contracts import (
    GovernanceApprovalRef,
    KnowledgeQueryResult,
    KnowledgeScope,
    KnowledgeSourceRef,
    MemoryCandidate,
    MemoryCandidateStatus,
    RuntimeMemoryLayer,
    SubmitMemoryCandidateRequest,
)

NOW = datetime(2026, 8, 12, tzinfo=UTC)


def resource(kind: str, value: str) -> ResourceRef:
    return ResourceRef(resource_type=kind, resource_id=value, revision="1", authority="postgresql")


def source(**overrides: object) -> KnowledgeSourceRef:
    payload = {
        "source_kind": "authorized_document",
        "source_uri": "https://example.invalid/policy",
        "observed_at": NOW,
        "freshness_expires_at": NOW + timedelta(days=30),
        "license_id": "internal-authorized",
        "usage_policy": "summary-and-citation",
        "content_hash": "a" * 64,
        "provider": "manual-import",
        "provider_version": "1",
        "applicability": ["vertical:ecommerce"],
    }
    payload.update(overrides)
    return KnowledgeSourceRef(**payload)


def request(**overrides: object) -> SubmitMemoryCandidateRequest:
    payload = {
        "candidate_layer": "semantic",
        "task_id": "task-1",
        "run_id": "run-1",
        "subject": resource("KnowledgeSubject", "subject-1"),
        "payload": ArtifactRef(artifact_id="artifact-1", artifact_type="memory-candidate", revision="1", content_hash="b" * 64),
        "source": source(),
        "confidence": 0.8,
        "marking": ["internal"],
    }
    payload.update(overrides)
    return SubmitMemoryCandidateRequest(**payload)


def governance() -> GovernanceApprovalRef:
    return GovernanceApprovalRef(
        eval_report=ArtifactRef(artifact_id="report-1", artifact_type="eval_report", revision="1", content_hash="c" * 64),
        draft=resource("Draft", "draft-1"),
        approval_event=resource("ApprovalEvent", "approval-1"),
    )


def test_runtime_layers_exclude_procedural_and_shared_storage() -> None:
    assert {item.value for item in RuntimeMemoryLayer} == {"working", "episodic", "semantic"}
    with pytest.raises(ValidationError):
        request(candidate_layer="procedural")
    with pytest.raises(ValidationError):
        request(candidate_layer="shared")


def test_working_memory_cannot_enter_candidate_promotion_chain() -> None:
    with pytest.raises(ValidationError, match="Task/Checkpoint"):
        request(candidate_layer="working")


def test_submit_request_never_accepts_tenant_scope_from_payload() -> None:
    assert "org_id" not in SubmitMemoryCandidateRequest.model_fields
    assert "project_id" not in SubmitMemoryCandidateRequest.model_fields
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        request(org_id="dev-org", project_id="dev-project")


def test_source_requires_exactly_one_origin_and_complete_governance() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        source(source_uri=None)
    with pytest.raises(ValidationError, match="exactly one"):
        source(source_ref=resource("Artifact", "a1"))
    with pytest.raises(ValidationError, match="freshness"):
        source(freshness_expires_at=NOW)
    with pytest.raises(ValidationError):
        source(license_id=" ")


def test_approved_and_promoted_candidates_require_exact_eval_and_approval() -> None:
    base = {
        "tenant": TenantContext(org_id="org-org", project_id="dev-project"),
        "candidate_id": "candidate-1",
        "scope": KnowledgeScope.WORKSPACE,
        "request": request(),
        "version": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    with pytest.raises(ValidationError, match="governance"):
        MemoryCandidate(**base, status=MemoryCandidateStatus.APPROVED)
    approved = MemoryCandidate(**base, status=MemoryCandidateStatus.APPROVED, governance=governance())
    assert approved.governance is not None


def test_quarantine_and_blocked_results_keep_explicit_reasons() -> None:
    with pytest.raises(ValidationError, match="reasons"):
        MemoryCandidate(
            tenant=TenantContext(org_id="org-org", project_id="dev-project"),
            candidate_id="candidate-1", status="quarantined", scope="workspace",
            request=request(), version=1, created_at=NOW, updated_at=NOW,
        )
    with pytest.raises(ValidationError, match="blocked result"):
        KnowledgeQueryResult(citations=[], status="blocked", blocked_reasons=[], assembled_tokens=0)
    result = KnowledgeQueryResult(
        citations=[],
        status="blocked",
        blocked_reasons=["source_revoked"],
        assembled_tokens=0,
    )
    assert result.status == "blocked"
