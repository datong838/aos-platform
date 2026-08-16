from datetime import UTC, datetime, timedelta

from aos_api.aip_runtime_guard_policy_store import GuardPolicyNotFound
from aos_api.routers import aip_runtime_guard_policies


NOW = datetime(2026, 8, 17, tzinfo=UTC)


def headers(org: str = "org-org", **extra: str) -> dict[str, str]:
    return {"Authorization": "Bearer dev", "X-Org-Id": org, "X-Project-Id": "dev-project", **extra}


def egress_body() -> dict:
    return {
        "policyId": "agnes-egress-dev", "revision": 1, "environment": "development",
        "allowedSchemes": ["https"], "allowedHosts": ["apihub.agnes-ai.com"],
        "allowedPorts": [443], "allowPublicFallback": False,
        "unknownDestinationBehavior": "block", "regionState": "confirmed",
        "region": "cn-approved-development", "effectiveFrom": NOW.isoformat(),
        "effectiveUntil": (NOW + timedelta(days=30)).isoformat(), "owner": "杜大同",
        "approvalRef": "approval:r1-03", "lifecycle": "active",
    }


class CaptureStore:
    call = None

    def publish_egress(self, scope, actor, key, item, *, expected_version=0):
        self.call = (scope.key, actor, key, expected_version)
        from aos_api.aip_runtime_guard_policy_store import materialize_policy
        return materialize_policy(scope, actor, item, created_at=NOW)

    def get_egress(self, scope, policy_id, revision=None):
        self.call = (scope.key, policy_id, revision)
        raise GuardPolicyNotFound("not found")


def test_guard_policy_api_uses_principal_scope_and_exact_read(client) -> None:
    store = CaptureStore()
    client.app.dependency_overrides[aip_runtime_guard_policies.get_store] = lambda: store
    try:
        response = client.post(
            "/v1/aip/runtime-guard-policies/egress",
            headers=headers(**{"Idempotency-Key": "egress-v1", "If-Match": "0"}),
            json=egress_body(),
        )
        assert response.status_code == 201, response.text
        assert store.call == (("org-org", "dev-project"), "user:dev", "egress-v1", 0)
        missing = client.get(
            "/v1/aip/runtime-guard-policies/egress/missing?revision=2",
            headers=headers("dev-org"),
        )
        assert missing.status_code == 404
        assert store.call == (("dev-org", "dev-project"), "missing", 2)
    finally:
        client.app.dependency_overrides.pop(aip_runtime_guard_policies.get_store, None)


def test_guard_policy_api_rejects_tenant_injection_and_missing_cas_headers(client) -> None:
    body = egress_body()
    body["tenant"] = {"orgId": "dev-org", "projectId": "dev-project"}
    injected = client.post(
        "/v1/aip/runtime-guard-policies/egress",
        headers=headers(**{"Idempotency-Key": "x", "If-Match": "0"}), json=body,
    )
    assert injected.status_code == 400
    missing = client.post("/v1/aip/runtime-guard-policies/egress", headers=headers(), json=egress_body())
    assert missing.status_code == 400
