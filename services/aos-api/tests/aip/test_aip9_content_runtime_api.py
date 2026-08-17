from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.aip_content_contracts import (
    AvatarSessionSnapshot,
    AvatarSessionStatus,
    MediaJobSnapshot,
    MediaJobStatus,
)
from aos_api.aip_contracts import ArtifactRef, ResourceRef
from aos_api.aip_production_contracts import ExactRevisionRef, MutableAuthorityRef
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.routers import aip_content_runtime as api
from aos_api.tenant_scope import TenantScope

HASH = "a" * 64
PRIMARY = Principal(
    subject="content-executor", org_id="org-org", project_id="dev-project",
    roles=["executor"], markings=["public"],
)
CANARY = Principal(
    subject="canary-reader", org_id="dev-org", project_id="dev-project",
    roles=["viewer"], markings=["public"],
)


def resource(kind: str, value: str) -> ResourceRef:
    return ResourceRef(resourceType=kind, resourceId=value, revision="1", authority="pytest")


def exact(kind: str, value: str) -> ExactRevisionRef:
    return ExactRevisionRef(resourceType=kind, resourceId=value, revision=1, contentHash=HASH)


def media_snapshot(scope: TenantScope | None = None) -> MediaJobSnapshot:
    scope = scope or TenantScope(PRIMARY.org_id, PRIMARY.project_id)
    now = datetime.now(UTC)
    return MediaJobSnapshot(
        tenant={"orgId": scope.org_id, "projectId": scope.project_id},
        jobId="media-job-1", requestHash=HASH,
        taskRunRef=resource("TaskRun", "run-1"),
        stepRunRef=resource("StepRun", "step-1"),
        jobKind="video_render", attempt=1, status=MediaJobStatus.QUEUED,
        latestSequence=1, createdAt=now, updatedAt=now,
    )


def avatar_snapshot(scope: TenantScope | None = None) -> AvatarSessionSnapshot:
    scope = scope or TenantScope(PRIMARY.org_id, PRIMARY.project_id)
    now = datetime.now(UTC)
    return AvatarSessionSnapshot(
        tenant={"orgId": scope.org_id, "projectId": scope.project_id},
        sessionId="avatar-session-1", requestHash=HASH,
        taskRunRef=resource("TaskRun", "run-1"),
        stepRunRef=resource("StepRun", "step-1"),
        capabilityBindingRef=MutableAuthorityRef(
            resourceType="CapabilityBinding", resourceId="binding-1", version=1,
        ),
        budgetRef=exact("BudgetRevision", "budget-1"),
        killPolicyRef=exact("KillPolicyRevision", "kill-1"),
        maxDurationSeconds=300, status=AvatarSessionStatus.OPENING,
        latestSequence=1, createdAt=now, updatedAt=now,
    )


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, TenantScope, dict]] = []

    def list_media_jobs(self, scope: TenantScope, *, limit: int):
        self.calls.append(("list_media", scope, {"limit": limit}))
        return [] if scope.org_id == "dev-org" else [media_snapshot(scope)]

    def get_media_job(self, scope: TenantScope, job_id: str):
        self.calls.append(("get_media", scope, {"job_id": job_id}))
        return media_snapshot(scope)

    def submit_media_job(self, scope: TenantScope, body, **kwargs):
        self.calls.append(("submit_media", scope, kwargs))
        return media_snapshot(scope)

    def command_media_job(self, scope: TenantScope, job_id: str, operation: str, **kwargs):
        self.calls.append((operation, scope, {"job_id": job_id, **kwargs}))
        return media_snapshot(scope)

    def list_avatar_sessions(self, scope: TenantScope, *, limit: int):
        self.calls.append(("list_avatar", scope, {"limit": limit}))
        return [] if scope.org_id == "dev-org" else [avatar_snapshot(scope)]

    def get_avatar_session(self, scope: TenantScope, session_id: str):
        self.calls.append(("get_avatar", scope, {"session_id": session_id}))
        return avatar_snapshot(scope)

    def open_avatar_session(self, scope: TenantScope, body, **kwargs):
        self.calls.append(("open_avatar", scope, kwargs))
        return avatar_snapshot(scope)

    def command_avatar_session(self, scope: TenantScope, session_id: str, operation: str, **kwargs):
        self.calls.append((operation, scope, {"session_id": session_id, **kwargs}))
        return avatar_snapshot(scope)


@pytest.fixture()
def local_api():
    app = FastAPI()
    app.include_router(api.router)
    fake = FakeStore()
    app.dependency_overrides[require_principal] = lambda: PRIMARY
    app.dependency_overrides[api.get_aip_content_runtime_store] = lambda: fake
    with TestClient(app) as client:
        yield client, app, fake


def test_router_freezes_24_operations_and_request_authority_excludes_tenant(local_api) -> None:
    client, app, _ = local_api
    operations = [
        route for route in api.router.routes
        for method in route.methods or set() if method in {"GET", "POST"}
    ]
    assert len(operations) == 24
    schema = app.openapi()
    assert len([method for path in schema["paths"].values() for method in path if method in {"get", "post"}]) == 24
    for name in (
        "MediaJobCreateRequest", "AvatarSessionOpenRequest", "MediaClaimCommand",
        "AvatarLiveCommand", "UnknownCommand", "MediaReconcileCommand",
        "AvatarReconcileCommand",
    ):
        properties = schema["components"]["schemas"][name].get("properties", {})
        assert "orgId" not in properties and "projectId" not in properties and "tenant" not in properties

    invalid = client.post(
        "/v1/aip/content/media-jobs/job-1/cancel",
        headers={"Idempotency-Key": "cancel-1"},
        json={"expectedVersion": 1, "reasonCode": "operator_cancel", "orgId": "dev-org"},
    )
    assert invalid.status_code == 422


def test_reads_bind_scope_from_principal_and_negative_canary_is_empty(local_api) -> None:
    client, app, fake = local_api
    response = client.get("/v1/aip/content/media-jobs?limit=7")
    assert response.status_code == 200
    assert response.json()[0]["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert fake.calls[-1][1].key == ("org-org", "dev-project")

    app.dependency_overrides[require_principal] = lambda: CANARY
    response = client.get("/v1/aip/content/media-jobs?limit=7")
    assert response.status_code == 200 and response.json() == []
    assert fake.calls[-1][1].key == ("dev-org", "dev-project")


def test_executor_command_mapping_is_server_scoped_and_operator_cannot_forge_observation() -> None:
    fake = FakeStore()
    completed = api._media_command(
        "job-1", "succeed",
        api.MediaCompleteCommand(
            expectedVersion=3,
            outputArtifactRefs=[ArtifactRef(
                artifactId="video-1", artifactType="video", revision="1", contentHash=HASH,
            )],
        ),
        "complete-1", PRIMARY, fake,
    )
    assert completed.status is MediaJobStatus.QUEUED
    operation, scope, values = fake.calls[-1]
    assert operation == "succeed" and scope.key == ("org-org", "dev-project")
    assert values["expected_version"] == 3
    assert values["idempotency_key"] == "complete-1"
    assert values["actor"] == "content-executor"
    assert "occurred_at" not in values

    operator = Principal(
        subject="content-operator", org_id="org-org", project_id="dev-project",
        roles=["operator"], markings=["public"],
    )
    with pytest.raises(ApiError) as denied:
        api._avatar_command(
            "session-1", "ready", api.ExpectedVersionCommand(expectedVersion=1),
            "ready-1", operator, fake,
        )
    assert denied.value.status_code == 403
    assert denied.value.code == "CONTENT_RUNTIME_ROLE_REQUIRED"


def test_operator_control_is_allowed_but_unprivileged_submit_is_denied(local_api) -> None:
    _, app, fake = local_api
    operator = Principal(
        subject="operator", org_id="org-org", project_id="dev-project",
        roles=["operator"], markings=["public"],
    )
    result = api._avatar_command(
        "session-1", "pause", api.ExpectedVersionCommand(expectedVersion=2),
        "pause-1", operator, fake,
    )
    assert result.status is AvatarSessionStatus.OPENING

    viewer = Principal(
        subject="viewer", org_id="org-org", project_id="dev-project",
        roles=["viewer"], markings=["public"],
    )
    with pytest.raises(ApiError) as denied:
        api._require_role(viewer, api._OPERATOR_ROLES)
    assert denied.value.code == "CONTENT_RUNTIME_ROLE_REQUIRED"
    app.dependency_overrides[require_principal] = lambda: viewer


def test_limit_and_required_idempotency_key_are_contract_gates(local_api) -> None:
    client, _, _ = local_api
    assert client.get("/v1/aip/content/avatar-sessions?limit=0").status_code == 422
    assert client.post(
        "/v1/aip/content/avatar-sessions/session-1/close",
        json={"expectedVersion": 1},
    ).status_code == 422
