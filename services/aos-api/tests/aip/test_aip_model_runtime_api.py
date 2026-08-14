from __future__ import annotations

from aos_api.aip_model_runtime_store import ModelRuntimeNotFound
from aos_api.routers import aip_model_runtime


def headers(org_id: str = "org-org", **extra: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": org_id,
        "X-Project-Id": "dev-project",
        **extra,
    }


class CapturingStore:
    def __init__(self) -> None:
        self.scope = None

    def get_route(self, scope, route_id, revision=None):
        self.scope = scope
        raise ModelRuntimeNotFound("model_route not found")


def test_canonical_route_read_uses_principal_scope_and_never_cross_tenant(client) -> None:
    store = CapturingStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    try:
        response = client.get("/v1/aip/model-runtime/routes/missing", headers=headers())
        assert response.status_code == 404
        assert response.json()["code"] == "AIP_RESOURCE_NOT_FOUND"
        assert store.scope.key == ("org-org", "dev-project")
        response = client.get("/v1/aip/model-runtime/routes/missing", headers=headers("dev-org"))
        assert response.status_code == 404
        assert store.scope.key == ("dev-org", "dev-project")
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)


def test_canonical_write_requires_idempotency_and_if_match(client) -> None:
    response = client.post("/v1/aip/model-runtime/routes", headers=headers(), json={})
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"


def test_all_legacy_route_writes_fail_closed_but_reads_remain(client) -> None:
    read = client.get("/v1/aip/model-admin/routes", headers=headers())
    assert read.status_code == 200
    for method, path, body in (
        ("put", "/v1/aip/model-admin/routes", {"routes": []}),
        ("post", "/api/models/router", {"id": "legacy", "task": "copy.generate"}),
        ("put", "/api/models/router/legacy", {"enabled": False}),
        ("delete", "/api/models/router/legacy", None),
        ("put", "/api/models/router/circuit-config", {"failure_threshold": 3}),
    ):
        response = client.request(method.upper(), path, headers=headers(), json=body)
        assert response.status_code == 410, (method, path, response.text)
        assert response.json()["code"] == "AIP_MODEL_LEGACY_WRITE_DISABLED"


def test_openapi_registers_canonical_model_runtime_paths(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/aip/model-runtime/providers" in paths
    assert "/v1/aip/model-runtime/models" in paths
    assert "/v1/aip/model-runtime/policies" in paths
    assert "/v1/aip/model-runtime/routes/{route_id}/resolution" in paths
    assert "/v1/aip/model-runtime/overview" in paths


class EmptyOverviewStore:
    scopes = []

    def list_current_assets(self, scope, kind):
        self.scopes.append((scope.key, kind))
        return []

    def list_eval_gates(self, scope, refs):
        assert refs == []
        return []

    def list_capacity_pools(self, scope):
        return []


def test_overview_is_secret_free_empty_and_tenant_scoped(client) -> None:
    store = EmptyOverviewStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    try:
        response = client.get("/v1/aip/model-runtime/overview", headers=headers())
        assert response.status_code == 200
        payload = response.json()
        assert payload["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
        assert payload["providers"] == payload["models"] == payload["routes"] == []
        assert payload["capacityPools"] == payload["resolutions"] == []
        assert "secret" not in response.text.lower()
        assert {scope for scope, _ in store.scopes} == {("org-org", "dev-project")}
        assert {kind for _, kind in store.scopes} == {
            "provider_instance", "registered_model", "runtime_policy", "model_route", "model_price_snapshot",
        }
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)
