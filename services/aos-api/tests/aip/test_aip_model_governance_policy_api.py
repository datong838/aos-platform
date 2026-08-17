from datetime import UTC, datetime, timedelta

from aos_api.aip_model_governance_policy_store import ModelGovernancePolicyNotFound, materialize_policy
from aos_api.routers import aip_model_governance_policies

NOW = datetime(2026, 8, 17, tzinfo=UTC)


def headers(org="org-org", **extra):
    return {"Authorization": "Bearer dev", "X-Org-Id": org, "X-Project-Id": "dev-project", **extra}


def body():
    return {"policyId": "quota-dev", "revision": 1, "environment": "development",
        "effectiveFrom": NOW.isoformat(), "effectiveUntil": (NOW + timedelta(days=30)).isoformat(),
        "owner": "杜大同", "approvalRef": "approval:r1-07", "lifecycle": "active",
        "maxConcurrency": 2, "maxInputTokens": 8000, "maxOutputTokens": 2000,
        "hourlyRequestLimit": 50, "dailyRequestLimit": 200, "reservationLeaseSeconds": 60,
        "overflowBehavior": "queue", "allowPublicProviderFallback": False, "allowAutoScale": False}


class CaptureStore:
    call = None
    def publish_quota(self, scope, actor, key, item, *, expected_version=0):
        self.call = (scope.key, actor, key, expected_version)
        return materialize_policy(scope, actor, item, created_at=NOW)
    def get_quota(self, scope, policy_id, revision=None):
        self.call = (scope.key, policy_id, revision)
        raise ModelGovernancePolicyNotFound("not found")


def test_api_uses_principal_scope_cas_and_exact_read(client) -> None:
    store = CaptureStore(); client.app.dependency_overrides[aip_model_governance_policies.get_store] = lambda: store
    try:
        response = client.post("/v1/aip/model-governance-policies/quotas",
            headers=headers(**{"Idempotency-Key": "quota-v1", "If-Match": "0"}), json=body())
        assert response.status_code == 201, response.text
        assert store.call == (("org-org", "dev-project"), "user:dev", "quota-v1", 0)
        missing = client.get("/v1/aip/model-governance-policies/quotas/missing?revision=2", headers=headers("dev-org"))
        assert missing.status_code == 404 and store.call == (("dev-org", "dev-project"), "missing", 2)
    finally:
        client.app.dependency_overrides.pop(aip_model_governance_policies.get_store, None)


def test_api_rejects_tenant_injection_and_missing_cas_headers(client) -> None:
    injected = body(); injected["tenant"] = {"orgId": "dev-org", "projectId": "dev-project"}
    assert client.post("/v1/aip/model-governance-policies/quotas",
        headers=headers(**{"Idempotency-Key": "x", "If-Match": "0"}), json=injected).status_code == 400
    assert client.post("/v1/aip/model-governance-policies/quotas", headers=headers(), json=body()).status_code == 400
