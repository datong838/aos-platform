from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_memory_pipeline_contracts import (
    CompleteKnowledgePipelineRunRequest,
    CreateKnowledgePipelineScheduleRequest,
    KnowledgePipelineKind,
    KnowledgePipelineReceipt,
    KnowledgePipelineRunStatus,
    KnowledgePipelineScheduleStatus,
    KnowledgePipelineTrigger,
    StartKnowledgePipelineRunRequest,
    TransitionKnowledgePipelineScheduleRequest,
)

NOW = datetime(2026, 8, 12, 14, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64


def artifact(identifier: str = "config-1", content_hash: str = HASH_A) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=identifier,
        artifact_type="knowledge_pipeline_config",
        revision="1",
        content_hash=content_hash,
    )


def resource(kind: str, identifier: str) -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=identifier,
        revision="1",
        authority="postgresql",
    )


def test_e5a_freezes_exactly_seven_pipeline_kinds_and_triggers() -> None:
    assert {item.value for item in KnowledgePipelineKind} == {
        "seed_import",
        "operational_learning",
        "network_learning",
        "competitor_analysis",
        "professional_database",
        "customer_feedback",
        "human_experience",
    }
    assert {item.value for item in KnowledgePipelineTrigger} == {
        "manual",
        "task_event",
        "scheduled",
        "version_event",
        "domain_event",
    }


def test_schedule_write_contract_rejects_tenant_credentials_and_loose_config() -> None:
    request = CreateKnowledgePipelineScheduleRequest(
        schedule_id="schedule-seed",
        pipeline_kind="seed_import",
        trigger="manual",
        config=artifact(),
        initial_status="paused",
        idempotency_key="schedule-seed",
        request_hash=HASH_A,
    )
    assert request.initial_status is KnowledgePipelineScheduleStatus.PAUSED
    assert "org_id" not in CreateKnowledgePipelineScheduleRequest.model_fields
    assert "project_id" not in CreateKnowledgePipelineScheduleRequest.model_fields
    assert "credential_ref" not in CreateKnowledgePipelineScheduleRequest.model_fields
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CreateKnowledgePipelineScheduleRequest(
            **request.model_dump(),
            org_id="dev-org",
            project_id="dev-project",
        )
    with pytest.raises(ValidationError, match="revision/hash"):
        CreateKnowledgePipelineScheduleRequest(
            schedule_id="schedule-bad",
            pipeline_kind="seed_import",
            trigger="manual",
            config=ArtifactRef(
                artifact_id="config-bad",
                artifact_type="knowledge_pipeline_config",
            ),
            initial_status="paused",
            idempotency_key="schedule-bad",
            request_hash=HASH_A,
        )
    with pytest.raises(ValidationError, match="cannot start active"):
        CreateKnowledgePipelineScheduleRequest(
            schedule_id="schedule-active",
            pipeline_kind="seed_import",
            trigger="manual",
            config=artifact(),
            initial_status="active",
            idempotency_key="schedule-active",
            request_hash=HASH_A,
        )


def test_disabled_schedule_requires_review_before_returning_to_paused() -> None:
    with pytest.raises(ValidationError, match="dependency review"):
        TransitionKnowledgePipelineScheduleRequest(
            expected_version=3,
            from_status="disabled",
            to_status="paused",
        )
    transition = TransitionKnowledgePipelineScheduleRequest(
        expected_version=3,
        from_status="disabled",
        to_status="paused",
        dependency_review=resource("aip.eval_report", "dependency-review-1"),
    )
    assert transition.to_status is KnowledgePipelineScheduleStatus.PAUSED


def test_run_start_binds_existing_task_run_and_checkpoint_cas() -> None:
    request = StartKnowledgePipelineRunRequest(
        pipeline_run_id="pipeline-run-1",
        schedule_id="schedule-seed",
        task_id="task-1",
        run_id="run-1",
        trigger="manual",
        expected_checkpoint_version=0,
        idempotency_key="pipeline-run-1",
        request_hash=HASH_A,
        scheduled_for=NOW,
    )
    assert request.expected_checkpoint_version == 0
    assert "tenant" not in StartKnowledgePipelineRunRequest.model_fields
    with pytest.raises(ValidationError):
        StartKnowledgePipelineRunRequest(
            **{**request.model_dump(), "request_hash": "not-a-hash"}
        )


def test_terminal_completion_requires_exact_evidence_and_candidate_refs() -> None:
    with pytest.raises(ValidationError, match="terminal"):
        CompleteKnowledgePipelineRunRequest(
            expected_run_version=2,
            status="running",
            input_hash=HASH_A,
            output_hash=HASH_B,
            candidate_refs=[],
            checkpoint=None,
            produced_count=0,
            failed_count=0,
            error_codes=[],
        )
    with pytest.raises(ValidationError, match="candidate refs"):
        CompleteKnowledgePipelineRunRequest(
            expected_run_version=2,
            status="succeeded",
            input_hash=HASH_A,
            output_hash=HASH_B,
            candidate_refs=[],
            checkpoint=artifact("checkpoint-1", HASH_B),
            produced_count=1,
            failed_count=0,
            error_codes=[],
        )
    completion = CompleteKnowledgePipelineRunRequest(
        expected_run_version=2,
        status="partial",
        input_hash=HASH_A,
        output_hash=HASH_B,
        candidate_refs=[resource("aip.memory_candidate", "candidate-1")],
        checkpoint=artifact("checkpoint-1", HASH_B),
        produced_count=1,
        failed_count=1,
        error_codes=["source_blocked"],
    )
    assert completion.status is KnowledgePipelineRunStatus.PARTIAL
    with pytest.raises(ValidationError, match="PostgreSQL memory candidates"):
        CompleteKnowledgePipelineRunRequest(
            expected_run_version=2,
            status="succeeded",
            input_hash=HASH_A,
            output_hash=HASH_B,
            candidate_refs=[resource("artifact", "candidate-1")],
            checkpoint=None,
            produced_count=1,
            failed_count=0,
            error_codes=[],
        )


def test_receipt_is_tenant_scoped_and_hash_bound() -> None:
    receipt = KnowledgePipelineReceipt(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        receipt_id="receipt-1",
        pipeline_run_id="pipeline-run-1",
        status="succeeded",
        input_hash=HASH_A,
        output_hash=HASH_B,
        candidate_refs=[resource("aip.memory_candidate", "candidate-1")],
        checkpoint_before_version=0,
        checkpoint_after_version=1,
        produced_count=1,
        failed_count=0,
        error_codes=[],
        receipt_hash="c" * 64,
        created_at=NOW,
    )
    assert receipt.checkpoint_after_version == 1
    with pytest.raises(ValidationError, match="checkpoint"):
        KnowledgePipelineReceipt(
            **{
                **receipt.model_dump(),
                "checkpoint_before_version": 2,
                "checkpoint_after_version": 1,
            }
        )
