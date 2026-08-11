from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_research_job import (
    CreateResearchJobRequest,
    ReconcileResearchJobRequest,
    RecordResearchArtifactRequest,
    RecordResearchDeliveryRequest,
    RecordResearchSubmissionRequest,
    RegisterResearchProviderRequest,
    ResearchDeliveryStatus,
    ResearchJobEvent,
    ResearchJobManifest,
    ResearchJobStatus,
    ResearchProviderStatus,
    canonical_research_manifest_hash,
)
from aos_api.aip_research_job_service import AipResearchJobService
from aos_api.aip_research_job_store import (
    AipResearchJobBlocked,
    AipResearchJobConflict,
    AipResearchJobNotFound,
    AipResearchJobStore,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("dev-org", "dev-project")
OTHER = TenantScope("org-org", "dev-project")
HASH = "a" * 64
H2 = "b" * 64
NOW = datetime(2026, 8, 12, 1, tzinfo=UTC)
SECRET = b"research-secret"


@pytest.fixture()
def authority_chain() -> dict[str, object]:
    suffix = uuid.uuid4().hex[:12]
    task_id = f"research-task-{suffix}"
    plan_id = f"research-plan-{suffix}"
    run_id = f"research-run-{suffix}"
    provider_id = f"research-provider-{suffix}"
    capability = ResourceRef(
        resource_type="capability",
        resource_id="research.deep",
        revision="7",
        authority="aos.plan",
    )
    step = {
        "stepKey": "deep-research",
        "title": "deep research",
        "capabilityRef": capability.model_dump(mode="json", by_alias=True),
        "inputRefs": [],
    }
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_task (
                 org_id,project_id,task_id,task_type,title,status,idempotency_key,
                 request_hash,current_plan_revision_id,created_by)
               VALUES (%s,%s,%s,'research','research','executing',%s,%s,%s,'tester')""",
            (*SCOPE.key, task_id, f"research-task-{suffix}", HASH, plan_id),
        )
        conn.execute(
            """INSERT INTO aip_plan_revision (
                 org_id,project_id,plan_revision_id,task_id,revision,content_hash,
                 steps,approval_status,idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,%s,1,%s,%s::jsonb,'approved',%s,%s,'tester')""",
            (
                *SCOPE.key,
                plan_id,
                task_id,
                HASH,
                json.dumps([step]),
                f"research-plan-{suffix}",
                HASH,
            ),
        )
        conn.execute(
            """INSERT INTO aip_task_run (
                 org_id,project_id,run_id,task_id,plan_revision_id,status,
                 idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,%s,%s,'running',%s,%s,'tester')""",
            (
                *SCOPE.key,
                run_id,
                task_id,
                plan_id,
                f"research-run-{suffix}",
                HASH,
            ),
        )
        conn.commit()
    service = AipResearchJobService(
        AipResearchJobStore(),
        secret_resolver=lambda *_args: SECRET,
        artifact_hash_resolver=lambda _scope, _ref: HASH,
    )
    provider_request = RegisterResearchProviderRequest(
        provider_id=provider_id,
        revision=1,
        adapter_kind="deerflow",
        capability_ref=capability,
        contract_hash=HASH,
        callback_secret_ref_hash=H2,
    )
    provider = service.register_provider(SCOPE, provider_request, "tester", now=NOW)
    manifest = ResearchJobManifest(
        task_run_ref=ResourceRef(
            resource_type="aos.task_run",
            resource_id=run_id,
            revision="1",
            authority="aos.task",
        ),
        provider=provider_id,
        binding_revision="1",
        manifest_hash="0" * 64,
        idempotency_key=f"research-job-{suffix}",
        budget={"maxTokens": 2000},
        output_schema_hash=HASH,
        traceparent=f"00-{suffix:0<32}-{'1' * 16}-01",
        deadline=NOW + timedelta(hours=1),
    )
    manifest = manifest.model_copy(
        update={"manifest_hash": canonical_research_manifest_hash(manifest)}
    )
    create_request = CreateResearchJobRequest(
        run_id=run_id,
        step_key="deep-research",
        provider_id=provider_id,
        provider_revision=1,
        manifest=manifest,
    )
    job = service.create_job(SCOPE, create_request, "tester", now=NOW)
    return {
        "service": service,
        "provider_request": provider_request,
        "provider": provider,
        "create_request": create_request,
        "job": job,
        "run_id": run_id,
        "provider_id": provider_id,
    }


def _submission(job_id: str, execution_id: str) -> RecordResearchSubmissionRequest:
    return RecordResearchSubmissionRequest(
        job_id=job_id,
        provider_execution_id=execution_id,
        provider_version="1",
        accepted_manifest_hash=authority_hash(job_id),
        source_hash=HASH,
        observed_at=NOW,
    )


def authority_hash(job_id: str) -> str:
    with connect(SCOPE) as conn:
        row = conn.execute(
            """SELECT manifest_hash FROM aip_research_job_manifest
               WHERE org_id=%s AND project_id=%s AND job_id=%s""",
            (*SCOPE.key, job_id),
        ).fetchone()
    return str(row["manifest_hash"])


def _event(
    execution_id: str, sequence: int, status: ResearchJobStatus
) -> ResearchJobEvent:
    payload = {"sequence": sequence, "status": status.value}
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return ResearchJobEvent(
        provider_execution_id=execution_id,
        sequence=sequence,
        event_id=f"event-{sequence}",
        status=status,
        payload_hash=payload_hash,
        observed_at=NOW + timedelta(minutes=sequence),
        payload=payload,
    )


def _artifact(job_id: str, execution_id: str) -> RecordResearchArtifactRequest:
    return RecordResearchArtifactRequest(
        job_id=job_id,
        provider_execution_id=execution_id,
        artifact_type="research.report",
        content_ref=f"aos://research/{job_id}/report.json",
        media_type="application/json",
        content_hash=HASH,
        schema_ref="aos://schemas/research-report/v1",
        source_hash=H2,
        observed_at=NOW + timedelta(minutes=5),
    )


def test_provider_job_and_submission_are_exactly_idempotent(authority_chain) -> None:
    service = authority_chain["service"]
    provider_request = authority_chain["provider_request"]
    create_request = authority_chain["create_request"]
    job = authority_chain["job"]
    assert (
        service.register_provider(SCOPE, provider_request, "tester", now=NOW)
        == authority_chain["provider"]
    )
    assert service.create_job(SCOPE, create_request, "tester", now=NOW) == job
    submission = _submission(job.job_id, f"execution-{uuid.uuid4().hex}")
    first = service.record_submission(SCOPE, submission, now=NOW)
    assert service.record_submission(SCOPE, submission, now=NOW) == first
    with pytest.raises(AipResearchJobConflict, match="payload drifted"):
        service.record_submission(
            SCOPE,
            submission.model_copy(update={"source_hash": H2}),
            now=NOW,
        )
    with pytest.raises(AipResearchJobNotFound):
        service.get_job(OTHER, job.job_id)


def test_events_persist_gaps_then_converge_and_delivery_validates_artifact(
    authority_chain,
) -> None:
    service = authority_chain["service"]
    job = authority_chain["job"]
    execution_id = f"execution-{uuid.uuid4().hex}"
    service.record_submission(SCOPE, _submission(job.job_id, execution_id), now=NOW)
    gap = service.record_event(
        SCOPE, job.job_id, _event(execution_id, 2, ResearchJobStatus.SUCCEEDED), now=NOW
    )
    assert gap.has_gap is True
    assert gap.status is ResearchJobStatus.QUEUED
    running = service.record_event(
        SCOPE, job.job_id, _event(execution_id, 1, ResearchJobStatus.RUNNING), now=NOW
    )
    assert running.has_gap is False
    assert running.status is ResearchJobStatus.SUCCEEDED
    artifact_request = _artifact(job.job_id, execution_id)
    artifact = service.record_artifact(SCOPE, artifact_request, "tester", now=NOW)
    assert (
        service.record_artifact(SCOPE, artifact_request, "tester", now=NOW) == artifact
    )
    delivery_request = RecordResearchDeliveryRequest(
        job_id=job.job_id,
        provider_execution_id=execution_id,
        status=ResearchDeliveryStatus.SUCCEEDED,
        artifact_ids=[artifact.artifact.artifact_id],
        source_hash=HASH,
        observed_at=NOW + timedelta(minutes=6),
    )
    delivery = service.record_delivery(SCOPE, delivery_request, now=NOW)
    assert delivery.status == "succeeded"
    assert service.record_delivery(SCOPE, delivery_request, now=NOW) == delivery
    with pytest.raises(AipResearchJobConflict, match="payload drifted"):
        service.record_delivery(
            SCOPE,
            delivery_request.model_copy(
                update={"observed_at": NOW + timedelta(minutes=7)}
            ),
            now=NOW,
        )


def test_unknown_can_bind_verified_artifact_then_reconcile(authority_chain) -> None:
    service = authority_chain["service"]
    job = authority_chain["job"]
    execution_id = f"execution-{uuid.uuid4().hex}"
    service.record_submission(SCOPE, _submission(job.job_id, execution_id), now=NOW)
    snapshot = service.record_event(
        SCOPE, job.job_id, _event(execution_id, 1, ResearchJobStatus.UNKNOWN), now=NOW
    )
    assert snapshot.status is ResearchJobStatus.UNKNOWN
    artifact = service.record_artifact(
        SCOPE, _artifact(job.job_id, execution_id), "tester", now=NOW
    )
    receipt = service.reconcile(
        SCOPE,
        ReconcileResearchJobRequest(
            job_id=job.job_id,
            final_status=ResearchJobStatus.SUCCEEDED,
            reason_code="provider_pull_confirmed",
            source_hash=HASH,
            observed_at=NOW + timedelta(minutes=7),
        ),
        now=NOW,
    )
    assert receipt.status == "succeeded"
    assert receipt.artifact_ids == [artifact.artifact.artifact_id]
    assert service.get_job(SCOPE, job.job_id).status is ResearchJobStatus.SUCCEEDED


def test_callback_nonce_is_persistent_and_disabled_provider_fails_closed(
    authority_chain,
) -> None:
    service = authority_chain["service"]
    provider_id = authority_chain["provider_id"]
    body = b'{"event":"ready"}'
    nonce = f"nonce-{uuid.uuid4().hex}"
    timestamp = int(NOW.timestamp())
    body_hash = hashlib.sha256(body).hexdigest()
    signature = hmac.new(
        SECRET,
        f"{timestamp}.{nonce}.{body_hash}".encode(),
        hashlib.sha256,
    ).hexdigest()
    assert (
        service.verify_callback(
            SCOPE,
            provider_id=provider_id,
            provider_revision=1,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
            signature=signature,
            observed_at=NOW,
        )
        == body_hash
    )
    restarted = AipResearchJobService(
        AipResearchJobStore(),
        secret_resolver=lambda *_args: SECRET,
        artifact_hash_resolver=lambda _scope, _ref: HASH,
    )
    with pytest.raises(AipResearchJobConflict, match="replayed"):
        restarted.verify_callback(
            SCOPE,
            provider_id=provider_id,
            provider_revision=1,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
            signature=signature,
            observed_at=NOW,
        )
    disabled = authority_chain["provider_request"].model_copy(
        update={"revision": 2, "status": ResearchProviderStatus.DISABLED}
    )
    service.register_provider(SCOPE, disabled, "tester", now=NOW)
    with pytest.raises(AipResearchJobBlocked, match="disabled"):
        service.verify_callback(
            SCOPE,
            provider_id=provider_id,
            provider_revision=2,
            timestamp=timestamp,
            nonce=f"nonce-{uuid.uuid4().hex}",
            body=body,
            signature=signature,
            observed_at=NOW,
        )
