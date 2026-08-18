from __future__ import annotations

from aos_api.aip_provider_plugin_authority import ProviderPluginAuthorityError
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


class ExactReadStore:
    def __init__(self) -> None:
        self.calls = []

    def _missing(self, kind, scope, asset_id, revision):
        self.calls.append((kind, scope.key, asset_id, revision))
        raise ModelRuntimeNotFound(f"{kind} not found")

    def get_provider(self, scope, asset_id, revision=None):
        return self._missing("provider", scope, asset_id, revision)

    def get_model(self, scope, asset_id, revision=None):
        return self._missing("model", scope, asset_id, revision)

    def get_policy(self, scope, asset_id, revision=None):
        return self._missing("policy", scope, asset_id, revision)

    def get_price_snapshot(self, scope, asset_id, revision=None):
        return self._missing("price_snapshot", scope, asset_id, revision)


class PricePublishStore:
    call = None

    def publish_price_snapshot(self, scope, actor, key, item, *, expected_version=0):
        self.call = (scope.key, actor, key, expected_version, item)
        return item


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


def test_exact_runtime_asset_reads_are_principal_scoped_and_revision_aware(client) -> None:
    store = ExactReadStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    try:
        paths = (
            ("provider", "/v1/aip/model-runtime/providers/provider-1?revision=2"),
            ("model", "/v1/aip/model-runtime/models/model-1?revision=2"),
            ("policy", "/v1/aip/model-runtime/policies/policy-1?revision=2"),
            ("price_snapshot", "/v1/aip/model-runtime/price-snapshots/price-1?revision=2"),
        )
        for kind, path in paths:
            response = client.get(path, headers=headers())
            assert response.status_code == 404
            assert response.json()["code"] == "AIP_RESOURCE_NOT_FOUND"
            assert store.calls[-1] == (kind, ("org-org", "dev-project"), path.split("/")[-1].split("?")[0], 2)
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)


def test_price_snapshot_publish_uses_principal_scope_cas_and_idempotency(client) -> None:
    store = PricePublishStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    try:
        response = client.post(
            "/v1/aip/model-runtime/price-snapshots",
            headers=headers(**{"Idempotency-Key": "price-1", "If-Match": "0"}),
            json={
                "tenant": {"orgId": "org-org", "projectId": "dev-project"},
                "priceSnapshotId": "price-1",
                "revision": 1,
                "contentHash": "a" * 64,
                "currency": "CNY",
                "inputTokenPrice": 0.001,
                "outputTokenPrice": 0.002,
                "cachedTokenPrice": None,
                "tokenUnit": 1000,
                "effectiveFrom": "2026-08-16T00:00:00Z",
                "effectiveUntil": None,
                "lifecycle": "draft",
                "createdBy": "caller-must-not-win",
                "createdAt": "2026-08-16T00:00:00Z",
            },
        )
        assert response.status_code == 201, response.text
        assert store.call[:4] == (("org-org", "dev-project"), "user:dev", "price-1", 0)
        assert store.call[4].created_by == "user:dev"
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)


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
    assert "/v1/aip/model-runtime/provider-plugins/{plugin_id}" in paths
    assert "/v1/aip/model-runtime/providers" in paths
    assert "/v1/aip/model-runtime/providers/{provider_id}" in paths
    assert "/v1/aip/model-runtime/models" in paths
    assert "/v1/aip/model-runtime/models/{model_id}" in paths
    assert "/v1/aip/model-runtime/policies" in paths
    assert "/v1/aip/model-runtime/policies/{policy_id}" in paths
    assert "/v1/aip/model-runtime/price-snapshots" in paths
    assert "/v1/aip/model-runtime/price-snapshots/{price_snapshot_id}" in paths
    assert "/v1/aip/model-runtime/routes/{route_id}/resolution" in paths
    assert "/v1/aip/model-runtime/overview" in paths


def test_approved_provider_plugin_exact_readback_is_principal_scoped(client) -> None:
    response = client.get(
        "/v1/aip/model-runtime/provider-plugins/agnes-text?revision=2",
        headers=headers(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["providerPluginId"] == "agnes-text"
    assert payload["revision"] == 2
    assert len(payload["contentHash"]) == 64
    assert payload["approvedCapabilities"] == ["llm", "chat", "structured_output"]
    assert "secret" not in response.text.lower()

    canary = client.get(
        "/v1/aip/model-runtime/provider-plugins/agnes-text?revision=2",
        headers=headers("dev-org"),
    )
    assert canary.status_code == 404
    assert canary.json()["code"] == "AIP_PROVIDER_PLUGIN_UNAVAILABLE"


class ProviderPublishStore:
    called = False

    def publish_provider(self, scope, actor, key, item, *, expected_version=0):
        self.called = True
        return item


class PluginAuthorityProbe:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def validate_ref(self, scope, ref):
        self.calls.append((scope.key, ref.asset_type, ref.asset_id, ref.revision, ref.content_hash))
        if self.fail:
            raise ProviderPluginAuthorityError("provider_plugin_ref_drifted")


def provider_body() -> dict:
    return {
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "providerInstanceId": "agnes-text-qyh-dev",
        "revision": 1,
        "contentHash": "a" * 64,
        "pluginRef": {
            "assetType": "ProviderPluginRevision",
            "assetId": "agnes-text",
            "revision": 1,
            "contentHash": "b" * 64,
        },
        "endpointProfile": {
            "baseUrl": "https://apihub.agnes-ai.com/v1",
            "region": "development-external-unspecified",
            "timeoutMs": 60000,
            "metadata": {},
        },
        "secretRef": "keychain://com.aos.llm/agnes-text/org-org/dev-project/agnes-text-qyh-dev#api-key",
        "secretVersion": "v1",
        "egressPolicyRef": {
            "assetType": "EgressPolicyRevision",
            "assetId": "egress-1",
            "revision": 1,
            "contentHash": "c" * 64,
        },
        "dataClassificationPolicyRef": {
            "assetType": "DataClassificationPolicyRevision",
            "assetId": "classification-1",
            "revision": 1,
            "contentHash": "d" * 64,
        },
        "lifecycle": "validated",
        "createdBy": "caller",
        "createdAt": "2026-08-16T00:00:00Z",
    }


def test_provider_publish_validates_exact_plugin_ref_before_store_write(client) -> None:
    store = ProviderPublishStore()
    authority = PluginAuthorityProbe()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    client.app.dependency_overrides[aip_model_runtime.get_plugin_authority] = lambda: authority
    try:
        response = client.post(
            "/v1/aip/model-runtime/providers",
            headers=headers(**{"Idempotency-Key": "provider-1", "If-Match": "0"}),
            json=provider_body(),
        )
        assert response.status_code == 201, response.text
        assert store.called is True
        assert authority.calls == [
            (("org-org", "dev-project"), "ProviderPluginRevision", "agnes-text", 1, "b" * 64)
        ]
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)
        client.app.dependency_overrides.pop(aip_model_runtime.get_plugin_authority, None)


def test_provider_publish_fails_before_store_when_plugin_ref_drifted(client) -> None:
    store = ProviderPublishStore()
    authority = PluginAuthorityProbe(fail=True)
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    client.app.dependency_overrides[aip_model_runtime.get_plugin_authority] = lambda: authority
    try:
        response = client.post(
            "/v1/aip/model-runtime/providers",
            headers=headers(**{"Idempotency-Key": "provider-2", "If-Match": "0"}),
            json=provider_body(),
        )
        assert response.status_code == 422
        assert response.json()["code"] == "AIP_PROVIDER_PLUGIN_REF_DRIFTED"
        assert store.called is False
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)
        client.app.dependency_overrides.pop(aip_model_runtime.get_plugin_authority, None)


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
