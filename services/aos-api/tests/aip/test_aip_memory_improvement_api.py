from __future__ import annotations

from aos_api.aip_memory_improvement import AipMemoryImprovementNotFound
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
        "/v1/aip/memory-authority/improvement-observations",
        "/v1/aip/memory-authority/improvement-observations/{observation_id}",
    }
    assert expected <= set(paths)
