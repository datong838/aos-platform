from datetime import UTC, datetime, timedelta

from aos_api.aip_network_policy_activation_preview import preview_network_activation
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_network_policy_store import NetworkPolicyDependencyBlocked
from aos_api.routers import aip_runtime_guard_policies
from aos_api.tenant_scope import TenantScope


class _ReadOnlyConnection:
    def __init__(self, row=None):
        self.row = row
        self.calls = []

    def execute(self, sql, params):
        assert sql.lstrip().startswith("SELECT ")
        self.calls.append((sql, params))
        return self

    def fetchone(self):
        return self.row


class _ConnectionContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *_):
        return False


class _Store:
    def __init__(self, row=None, *, dependency_ok=True):
        self.conn = _ReadOnlyConnection(row)
        self.dependency_ok = dependency_ok
        self.scopes = []

    def _connect_factory(self, scope):
        self.scopes.append(scope)
        return _ConnectionContext(self.conn)

    def _require_egress(self, scope, candidate):
        if not self.dependency_ok:
            raise NetworkPolicyDependencyBlocked("no exact active egress")


def _candidate(**changes):
    now = datetime(2026, 9, 29, tzinfo=UTC)
    values = {
        "policyId": "network-1", "revision": 1,
        "allowedSchemes": ["https"], "allowedHosts": ["api.agnes-ai.cn"],
        "allowedPorts": [443], "tlsRequired": True, "publicFallbackAllowed": False,
        "egressPolicyRef": {"assetType": "EgressPolicyRevision", "assetId": "egress-1",
                            "revision": 1, "contentHash": "a" * 64},
        "effectiveFrom": now, "effectiveUntil": now + timedelta(days=1),
        "owner": "owner-1", "approvalRef": "text-is-not-approval", "lifecycle": "active",
    }
    values.update(changes)
    return NetworkPolicyRevisionCreate.model_validate(values)


def test_preview_binds_exact_target_and_never_grants_activation():
    scope = TenantScope("org-org", "dev-project")
    store = _Store()
    first = preview_network_activation(scope, _candidate(), expected_version=0, store=store)
    second = preview_network_activation(scope, _candidate(), expected_version=0, store=store)
    assert first == second
    assert first["headRevision"] == first["headVersion"] == 0
    assert len(first["targetContentHash"]) == len(first["bindingHash"]) == 64
    assert first["activationAllowed"] is False
    assert "FORMAL_PRODUCER_UNAVAILABLE" in first["blockers"]
    assert "ATOMIC_APPROVAL_CONSUMER_UNAVAILABLE" in first["blockers"]
    assert store.scopes == [scope, scope]
    assert all(params == (*scope.key, "network-1") for _, params in store.conn.calls)


def test_preview_explains_head_drift_and_missing_dependency_without_writes():
    store = _Store({"current_revision": 2, "version": 3}, dependency_ok=False)
    result = preview_network_activation(
        TenantScope("org-org", "dev-project"), _candidate(), expected_version=2, store=store,
    )
    assert result["activationAllowed"] is False
    assert result["headRevision"] == 2 and result["headVersion"] == 3
    assert result["targetContentHash"] is None and result["bindingHash"] is None
    assert "HEAD_VERSION_DRIFT" in result["blockers"]
    assert "CANDIDATE_REVISION_DRIFT" in result["blockers"]
    assert "EGRESS_DEPENDENCY_INVALID" in result["blockers"]


def test_preview_tenant_identity_changes_binding_hash():
    first = preview_network_activation(TenantScope("org-org", "dev-project"), _candidate(),
                                       expected_version=0, store=_Store())
    other = preview_network_activation(TenantScope("other-org", "dev-project"), _candidate(),
                                       expected_version=0, store=_Store())
    assert first["bindingHash"] != other["bindingHash"]


def test_preview_http_uses_principal_scope_and_requires_head_version(client):
    store = _Store()
    client.app.dependency_overrides[aip_runtime_guard_policies.get_network_store] = lambda: store
    try:
        headers = {"Authorization": "Bearer dev", "X-Org-Id": "org-org",
                   "X-Project-Id": "dev-project", "If-Match": "0"}
        response = client.post(
            "/v1/aip/runtime-guard-policies/networks/activation-preview",
            headers=headers, json=_candidate().model_dump(mode="json", by_alias=True),
        )
        assert response.status_code == 200, response.text
        assert response.json()["activationAllowed"] is False
        assert store.scopes == [TenantScope("org-org", "dev-project")]
        assert client.post(
            "/v1/aip/runtime-guard-policies/networks/activation-preview",
            headers={key: value for key, value in headers.items() if key != "If-Match"},
            json=_candidate().model_dump(mode="json", by_alias=True),
        ).status_code == 400
    finally:
        client.app.dependency_overrides.pop(aip_runtime_guard_policies.get_network_store, None)
