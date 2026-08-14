from __future__ import annotations

from aos_api.aip_memory_improvement import AipMemoryImprovementNotFound
from aos_api.aip_memory_retrieval import AgentMemoryContextView
from aos_api.auth import Principal, require_principal
from aos_api.routers import aip_memory_improvement


def headers(org_id: str = "org-org", **extra: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": org_id,
        "X-Project-Id": "dev-project",
        **extra,
    }


class CapturingImprovement:
    def __init__(self):
        self.scope = None

    def get_observation(self, scope, observation_id):
        self.scope = scope
        raise AipMemoryImprovementNotFound("observation not found")


class CapturingMemoryReader:
    def __init__(self):
        self.scope = None
        self.request = None

    def query_context_view(self, scope, request):
        self.scope = scope
        self.request = request
        return AgentMemoryContextView(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            agentInstanceRef=request.agent_instance_ref,
            skillRef=request.skill_ref,
            logicRef=request.logic_ref,
            purposes=request.purposes,
            authorizedMarkings=request.authorized_markings,
            projectionRefs=[],
            memoryRefs=[],
            citations=[],
            status="blocked",
            blockedReasons=["projection_not_found"],
            assembledTokens=0,
            timeCutoff=request.time_cutoff,
        )

    def list_exposures(self, scope, **_filters):
        self.scope = scope
        return []


def test_canonical_observation_read_uses_principal_scope_and_never_cross_tenant(client) -> None:
    service = CapturingImprovement()
    client.app.dependency_overrides[aip_memory_improvement.get_improvement_service] = lambda: service
    try:
        response = client.get("/v1/aip/memory-authority/improvement-observations/missing", headers=headers())
        assert response.status_code == 404
        assert response.json()["code"] == "AIP_MEMORY_IMPROVEMENT_NOT_FOUND"
        assert service.scope.key == ("org-org", "dev-project")
        response = client.get(
            "/v1/aip/memory-authority/improvement-observations/missing", headers=headers("dev-org")
        )
        assert response.status_code == 404
        assert service.scope.key == ("dev-org", "dev-project")
    finally:
        client.app.dependency_overrides.pop(aip_memory_improvement.get_improvement_service, None)


def test_projection_write_requires_idempotency_header(client) -> None:
    response = client.post("/v1/aip/memory-authority/agent-projections", headers=headers(), json={})
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"


def test_untrusted_role_cannot_access_memory_governance(client) -> None:
    client.app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:viewer", org_id="org-org", project_id="dev-project", roles=["viewer"]
    )
    try:
        read = client.get("/v1/aip/memory-authority/agent-projections", headers=headers())
        assert read.status_code == 403
        assert read.json()["code"] == "AIP_SCOPE_FORBIDDEN"
    finally:
        client.app.dependency_overrides.pop(require_principal, None)


def test_canonical_api_has_no_public_observation_write_surface(client) -> None:
    response = client.post(
        "/v1/aip/memory-authority/improvement-observations", headers=headers(), json={}
    )
    assert response.status_code == 405


def test_context_and_exposure_reads_are_tenant_scoped_and_reference_only(client) -> None:
    reader = CapturingMemoryReader()
    client.app.dependency_overrides[aip_memory_improvement.get_memory_reader] = lambda: reader
    query = {
        "instanceRevision": 1,
        "instanceHash": "a" * 64,
        "skillId": "content-skill",
        "skillRevision": 1,
        "skillHash": "b" * 64,
        "logicId": "content.logic",
        "logicRevision": 1,
        "logicHash": "c" * 64,
        "purpose": "skill:content",
        "timeCutoff": "2026-08-15T00:00:00Z",
    }
    try:
        response = client.get(
            "/v1/aip/memory-authority/agent-instances/content-agent/memory-context",
            headers=headers(),
            params=query,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "blocked"
        assert "chunks" not in response.json()
        assert reader.scope.key == ("org-org", "dev-project")
        assert reader.request.authorized_markings == ["public", "restricted"]
        response = client.get(
            "/v1/aip/memory-authority/memory-exposures",
            headers=headers("dev-org"),
        )
        assert response.status_code == 200
        assert reader.scope.key == ("dev-org", "dev-project")
    finally:
        client.app.dependency_overrides.pop(
            aip_memory_improvement.get_memory_reader, None
        )


def test_openapi_registers_complete_e7_canonical_surface(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    expected = {
        "/v1/aip/memory-authority/agent-projections",
        "/v1/aip/memory-authority/agent-projections/{projection_id}",
        "/v1/aip/memory-authority/agent-projections/{projection_id}/suspend",
        "/v1/aip/memory-authority/agent-projections/{projection_id}/reactivate",
        "/v1/aip/memory-authority/agent-projections/{projection_id}/revoke",
        "/v1/aip/memory-authority/agent-projections/{projection_id}/events",
        "/v1/aip/memory-authority/agent-projections/{projection_id}/impact",
        "/v1/aip/memory-authority/agent-instances/{instance_id}/memory-context",
        "/v1/aip/memory-authority/memory-exposures",
        "/v1/aip/memory-authority/improvement-observations",
        "/v1/aip/memory-authority/improvement-observations/{observation_id}",
    }
    assert expected <= set(paths)
