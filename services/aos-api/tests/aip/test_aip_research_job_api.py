from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_research_job import (
    ResearchArtifactReceipt,
    ResearchDeliveryReceipt,
    ResearchJobSnapshot,
    ResearchJobStatus,
    ResearchProviderRevision,
    ResearchProviderStatus,
    ResearchSubmissionReceipt,
)
from aos_api.aip_research_job_store import (
    AipResearchJobConflict,
    AipResearchJobPersistenceError,
)
from aos_api.auth import Principal, require_principal
from aos_api.routers.aip_research_jobs import (
    get_aip_research_job_service,
    router,
)
from aos_api.tenant_scope import TenantScope

HASH = "a" * 64
NOW = datetime(2026, 8, 12, 1, tzinfo=UTC)


@pytest.fixture()
def research_api(client):
    client.app.include_router(router)
    tenant = TenantContext(org_id="dev-org", project_id="dev-project")
    capability = ResourceRef(
        resource_type="capability",
        resource_id="research.deep",
        revision="7",
        authority="aos.plan",
    )
    provider = ResearchProviderRevision(
        tenant=tenant,
        provider_id="deerflow",
        revision=1,
        adapter_kind="deerflow",
        capability_ref=capability,
        contract_hash=HASH,
        callback_secret_ref_hash=HASH,
        status=ResearchProviderStatus.ENABLED,
        source_hash=HASH,
        created_by="user:dev",
        created_at=NOW,
    )
    job = ResearchJobSnapshot(
        tenant=tenant,
        job_id="research-job-1",
        run_id="run-1",
        plan_revision_id="plan-1",
        step_key="deep-research",
        provider_id="deerflow",
        provider_revision=1,
        capability_ref=capability,
        lineage_ref=ResourceRef(
            resource_type="aip.lineage",
            resource_id="lineage-1",
            revision="1",
            authority="aos.lineage",
        ),
        manifest_hash=HASH,
        output_schema_hash=HASH,
        status=ResearchJobStatus.RUNNING,
        provider_execution_id="provider-run-1",
        last_sequence=1,
        created_at=NOW,
    )
    submission = ResearchSubmissionReceipt(
        tenant=tenant,
        submission_receipt_id="submission-1",
        job_id=job.job_id,
        provider_execution_id="provider-run-1",
        provider_version="1",
        accepted_manifest_hash=HASH,
        source_hash=HASH,
        observed_at=NOW,
        created_at=NOW,
    )
    artifact = ResearchArtifactReceipt(
        tenant=tenant,
        artifact_receipt_id="artifact-receipt-1",
        artifact=ArtifactRef(
            artifact_id="artifact-1",
            artifact_type="research.report",
            content_hash=HASH,
        ),
        job_id=job.job_id,
        provider_execution_id="provider-run-1",
        content_ref="aos://research/report.json",
        media_type="application/json",
        source_hash=HASH,
        observed_at=NOW,
        created_at=NOW,
    )
    delivery = ResearchDeliveryReceipt(
        tenant=tenant,
        receipt_id="delivery-1",
        job_id=job.job_id,
        receipt_kind="delivery",
        status="succeeded",
        artifact_ids=["artifact-1"],
        source_hash=HASH,
        observed_at=NOW,
        created_at=NOW,
    )

    class FakeService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, TenantScope]] = []
            self.error: Exception | None = None

        def _call(self, kind, scope, value):
            self.calls.append((kind, scope))
            if self.error:
                raise self.error
            return value

        def register_provider(self, scope, body, actor):
            return self._call("provider", scope, provider)

        def create_job(self, scope, body, actor):
            return self._call("create", scope, job)

        def get_job(self, scope, job_id):
            return self._call("get", scope, job)

        def record_submission(self, scope, body):
            return self._call("submission", scope, submission)

        def record_event(self, scope, job_id, body):
            return self._call("event", scope, job)

        def verify_callback(self, scope, **kwargs):
            return self._call("callback", scope, HASH)

        def record_artifact(self, scope, body, actor):
            return self._call("artifact", scope, artifact)

        def record_delivery(self, scope, body):
            return self._call("delivery", scope, delivery)

        def reconcile(self, scope, body):
            return self._call(
                "reconcile",
                scope,
                delivery.model_copy(
                    update={"receipt_kind": "reconcile", "reason_code": "confirmed"}
                ),
            )

    service = FakeService()
    client.app.dependency_overrides[get_aip_research_job_service] = lambda: service
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    yield client, service, headers
    client.app.dependency_overrides.pop(get_aip_research_job_service, None)
    client.app.dependency_overrides.pop(require_principal, None)


def test_research_api_uses_authenticated_scope_for_read_and_write(research_api) -> None:
    client, service, headers = research_api
    provider_body = {
        "providerId": "deerflow",
        "revision": 1,
        "adapterKind": "deerflow",
        "capabilityRef": {
            "resourceType": "capability",
            "resourceId": "research.deep",
            "revision": "7",
            "authority": "aos.plan",
        },
        "contractHash": HASH,
        "callbackSecretRefHash": HASH,
    }
    assert (
        client.post(
            "/v1/aip/research-authority/providers/revisions",
            headers=headers,
            json=provider_body,
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/v1/aip/research-authority/jobs/research-job-1", headers=headers
        ).status_code
        == 200
    )
    assert service.calls == [
        ("provider", TenantScope("dev-org", "dev-project")),
        ("get", TenantScope("dev-org", "dev-project")),
    ]


def test_research_api_rejects_path_body_drift_and_untrusted_role(research_api) -> None:
    client, _service, headers = research_api
    submission = {
        "jobId": "other-job",
        "providerExecutionId": "provider-run-1",
        "providerVersion": "1",
        "acceptedManifestHash": HASH,
        "sourceHash": HASH,
        "observedAt": NOW.isoformat(),
    }
    response = client.post(
        "/v1/aip/research-authority/jobs/research-job-1/submission-receipts",
        headers=headers,
        json=submission,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "AIP_INVALID_ARGUMENT"
    client.app.dependency_overrides[require_principal] = lambda: Principal(
        subject="reader",
        org_id="dev-org",
        project_id="dev-project",
        roles=["developer"],
        markings=["public"],
    )
    denied = client.post(
        "/v1/aip/research-authority/jobs/research-job-1/submission-receipts",
        headers=headers,
        json={**submission, "jobId": "research-job-1"},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "AIP_SCOPE_FORBIDDEN"


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (AipResearchJobConflict("drift"), 409, "AIP_RESEARCH_JOB_CONFLICT"),
        (
            AipResearchJobPersistenceError("db"),
            503,
            "AIP_RESEARCH_JOB_PERSISTENCE_ERROR",
        ),
    ],
)
def test_research_api_errors_fail_closed(research_api, error, status, code) -> None:
    client, service, headers = research_api
    service.error = error
    response = client.get(
        "/v1/aip/research-authority/jobs/research-job-1", headers=headers
    )
    assert response.status_code == status
    assert response.json()["code"] == code
    assert client.get("/v1/aip/research-authority/jobs/research-job-1").status_code in {
        401,
        403,
    }
