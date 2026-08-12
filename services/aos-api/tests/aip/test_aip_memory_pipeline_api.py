from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_memory_pipeline_contracts import (
    KnowledgePipelineAlert,
    KnowledgePipelineCheckpointRevision,
    KnowledgePipelineKind,
    KnowledgePipelinePolicy,
    KnowledgePipelineReceipt,
    KnowledgePipelineRun,
    KnowledgePipelineRunStatus,
    KnowledgePipelineSchedule,
    KnowledgePipelineScheduleStatus,
    KnowledgePipelineTrigger,
)
from aos_api.auth import Principal, require_principal
from aos_api.routers.aip_memory_authority import (
    get_aip_memory_pipeline_service,
    get_aip_memory_pipeline_store,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 13, 2, tzinfo=UTC)
HASH_A = "a" * 64


def artifact(identifier: str, artifact_type: str = "pipeline-config") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=identifier,
        artifact_type=artifact_type,
        revision="1",
        content_hash=HASH_A,
    )


def resource(kind: str, identifier: str) -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=identifier,
        revision="1",
        authority="postgresql",
    )


def schedule(
    status: KnowledgePipelineScheduleStatus = KnowledgePipelineScheduleStatus.PAUSED,
) -> KnowledgePipelineSchedule:
    return KnowledgePipelineSchedule(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        schedule_id="seed-1",
        pipeline_kind=KnowledgePipelineKind.SEED_IMPORT,
        trigger=KnowledgePipelineTrigger.MANUAL,
        config=artifact("config-1"),
        status=status,
        checkpoint_version=0,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def pipeline_run(
    status: KnowledgePipelineRunStatus = KnowledgePipelineRunStatus.QUEUED,
) -> KnowledgePipelineRun:
    return KnowledgePipelineRun(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        pipeline_run_id="pipeline-run-1",
        schedule_id="seed-1",
        task_id="task-1",
        run_id="run-1",
        trigger=KnowledgePipelineTrigger.MANUAL,
        status=status,
        attempt=1,
        expected_checkpoint_version=0,
        idempotency_key="run-key",
        request_hash=HASH_A,
        version=1,
        scheduled_for=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def receipt() -> KnowledgePipelineReceipt:
    return KnowledgePipelineReceipt(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        receipt_id="receipt-1",
        pipeline_run_id="pipeline-run-1",
        status=KnowledgePipelineRunStatus.SUCCEEDED,
        input_hash=HASH_A,
        output_hash=HASH_A,
        candidate_refs=[],
        checkpoint_before_version=0,
        checkpoint_after_version=0,
        produced_count=0,
        failed_count=0,
        error_codes=[],
        receipt_hash=HASH_A,
        created_at=NOW,
    )


def policy() -> KnowledgePipelinePolicy:
    return KnowledgePipelinePolicy(
        pipeline_kind=KnowledgePipelineKind.SEED_IMPORT,
        allowed_triggers=[KnowledgePipelineTrigger.MANUAL],
        default_status=KnowledgePipelineScheduleStatus.PAUSED,
        required_dependencies=["license"],
        allowed_receipt_types=["aip.artifact_receipt"],
        allowed_source_kinds=["authorized_document"],
    )


class FakeStore:
    def __init__(self) -> None:
        self.scopes: list[TenantScope] = []
        self.complete_call = None

    def _record(self, scope):
        self.scopes.append(scope)

    def list_schedules(self, scope, **_kwargs):
        self._record(scope)
        return [schedule()]

    def get_schedule(self, scope, _schedule_id):
        self._record(scope)
        return schedule()

    def list_schedule_events(self, scope, _schedule_id):
        self._record(scope)
        return []

    def get_checkpoint(self, scope, _schedule_id) -> KnowledgePipelineCheckpointRevision | None:
        self._record(scope)
        return None

    def list_runs(self, scope, **_kwargs):
        self._record(scope)
        return [pipeline_run()]

    def get_run(self, scope, _pipeline_run_id):
        self._record(scope)
        return pipeline_run()

    def list_run_events(self, scope, _pipeline_run_id):
        self._record(scope)
        return []

    def get_receipt_for_run(self, scope, _pipeline_run_id, **_kwargs):
        self._record(scope)
        return receipt()

    def list_alerts(self, scope, _pipeline_run_id) -> list[KnowledgePipelineAlert]:
        self._record(scope)
        return []

    def complete_run(self, scope, pipeline_run_id, body, **kwargs):
        self._record(scope)
        self.complete_call = (pipeline_run_id, body, kwargs)
        return receipt()


class FakeService:
    def __init__(self) -> None:
        self.create_call = None
        self.transition_call = None
        self.start_call = None

    @staticmethod
    def policy_kinds():
        return [KnowledgePipelineKind.SEED_IMPORT]

    @staticmethod
    def policy_for(_kind):
        return policy()

    def create_schedule(self, scope, body, **kwargs):
        self.create_call = (scope, body, kwargs)
        return schedule()

    def transition_schedule(self, scope, schedule_id, **kwargs):
        self.transition_call = (scope, schedule_id, kwargs)
        return schedule(KnowledgePipelineScheduleStatus.ACTIVE), object()

    def start_run(self, scope, body, **kwargs):
        self.start_call = (scope, body, kwargs)
        return pipeline_run()


@pytest.fixture()
def pipeline_api(client):
    store = FakeStore()
    service = FakeService()
    client.app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:qyh",
        org_id=SCOPE.org_id,
        project_id=SCOPE.project_id,
        roles=["admin", "developer"],
        markings=["internal"],
    )
    client.app.dependency_overrides[get_aip_memory_pipeline_store] = lambda: store
    client.app.dependency_overrides[get_aip_memory_pipeline_service] = lambda: service
    yield client, store, service
    for dependency in (
        require_principal,
        get_aip_memory_pipeline_store,
        get_aip_memory_pipeline_service,
    ):
        client.app.dependency_overrides.pop(dependency, None)


def schedule_body() -> dict:
    return {
        "scheduleId": "seed-1",
        "pipelineKind": "seed_import",
        "trigger": "manual",
        "config": artifact("config-1").model_dump(mode="json", by_alias=True),
        "initialStatus": "paused",
    }


def run_body() -> dict:
    return {
        "pipelineRunId": "pipeline-run-1",
        "scheduleId": "seed-1",
        "taskId": "task-1",
        "runId": "run-1",
        "trigger": "manual",
        "expectedCheckpointVersion": 0,
        "scheduledFor": NOW.isoformat(),
        "authorizedManual": True,
    }


def complete_body() -> dict:
    return {
        "expectedRunVersion": 2,
        "status": "succeeded",
        "inputHash": HASH_A,
        "outputHash": HASH_A,
        "candidateRefs": [],
        "checkpoint": None,
        "producedCount": 0,
        "failedCount": 0,
        "errorCodes": [],
    }


def test_read_endpoints_use_authenticated_tenant_and_return_strict_authority(pipeline_api) -> None:
    client, store, _service = pipeline_api

    assert client.get("/v1/aip/memory-authority/pipelines/policies").status_code == 200
    assert client.get("/v1/aip/memory-authority/pipelines/schedules").json()[0]["scheduleId"] == "seed-1"
    assert client.get("/v1/aip/memory-authority/pipelines/schedules/seed-1/events").json() == []
    assert client.get("/v1/aip/memory-authority/pipelines/schedules/seed-1/checkpoint").json() == {"checkpoint": None}
    assert client.get("/v1/aip/memory-authority/pipelines/runs").json()[0]["pipelineRunId"] == "pipeline-run-1"
    assert client.get("/v1/aip/memory-authority/pipelines/runs/pipeline-run-1/events").json() == []
    assert client.get("/v1/aip/memory-authority/pipelines/runs/pipeline-run-1/receipt").json()["receipt"]["receiptId"] == "receipt-1"
    assert client.get("/v1/aip/memory-authority/pipelines/runs/pipeline-run-1/alerts").json() == []
    assert store.scopes and all(scope == SCOPE for scope in store.scopes)


def test_schedule_create_requires_role_and_server_idempotency_header(pipeline_api) -> None:
    client, _store, service = pipeline_api
    response = client.post(
        "/v1/aip/memory-authority/pipelines/schedules",
        json=schedule_body(),
        headers={"X-Idempotency-Key": "schedule-key"},
    )
    assert response.status_code == 200
    assert service.create_call[0] == SCOPE
    assert service.create_call[2] == {
        "idempotency_key": "schedule-key",
        "actor": "user:qyh",
        "occurred_at": service.create_call[2]["occurred_at"],
    }

    client.app.dependency_overrides[require_principal] = lambda: Principal(
        subject="reader", org_id=SCOPE.org_id, project_id=SCOPE.project_id, roles=["developer"]
    )
    forbidden = client.post(
        "/v1/aip/memory-authority/pipelines/schedules",
        json=schedule_body(),
        headers={"X-Idempotency-Key": "other-key"},
    )
    assert forbidden.status_code == 403


def test_caller_cannot_inject_tenant_or_request_hash(pipeline_api) -> None:
    client, _store, _service = pipeline_api
    response = client.post(
        "/v1/aip/memory-authority/pipelines/schedules",
        json={**schedule_body(), "orgId": "dev-org", "requestHash": HASH_A},
        headers={"X-Idempotency-Key": "schedule-key"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"


def test_schedule_transition_uses_service_generated_dependency_review(pipeline_api) -> None:
    client, _store, service = pipeline_api
    response = client.post(
        "/v1/aip/memory-authority/pipelines/schedules/seed-1/transitions",
        json={
            "expectedVersion": 1,
            "fromStatus": "paused",
            "toStatus": "active",
            "reasonCode": "reviewed",
        },
    )
    assert response.status_code == 200
    assert service.transition_call[0:2] == (SCOPE, "seed-1")
    assert "dependency_review" not in service.transition_call[2]


def test_run_registration_forwards_manual_authorization_but_not_tenant(pipeline_api) -> None:
    client, _store, service = pipeline_api
    response = client.post(
        "/v1/aip/memory-authority/pipelines/runs",
        json=run_body(),
        headers={"X-Idempotency-Key": "run-key"},
    )
    assert response.status_code == 200
    assert service.start_call[0] == SCOPE
    assert service.start_call[1].task_id == "task-1"
    assert service.start_call[2]["authorized_manual"] is True


def test_complete_is_executor_only_and_uses_principal_as_lease_owner(pipeline_api) -> None:
    client, store, _service = pipeline_api
    forbidden = client.post(
        "/v1/aip/memory-authority/pipelines/runs/pipeline-run-1/complete",
        json=complete_body(),
    )
    assert forbidden.status_code == 403

    client.app.dependency_overrides[require_principal] = lambda: Principal(
        subject="worker-1",
        org_id=SCOPE.org_id,
        project_id=SCOPE.project_id,
        roles=["aip_executor"],
    )
    response = client.post(
        "/v1/aip/memory-authority/pipelines/runs/pipeline-run-1/complete",
        json=complete_body(),
    )
    assert response.status_code == 200
    assert store.complete_call[0] == "pipeline-run-1"
    assert store.complete_call[2]["actor"] == "worker-1"
