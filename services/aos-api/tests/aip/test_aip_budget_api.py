from datetime import UTC, datetime, timedelta

from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_store import BudgetNotFound
from aos_api.routers import aip_budgets


NOW = datetime(2026, 8, 17, tzinfo=UTC)


def headers(org_id: str = "org-org", **extra: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": org_id,
        "X-Project-Id": "dev-project",
        **extra,
    }


def body() -> dict:
    return {
        "budgetId": "budget-qyh-content-dev",
        "revision": 1,
        "environment": "development",
        "currency": "CNY",
        "dailyLimitMinor": 500,
        "monthlyLimitMinor": 5000,
        "alertThresholdPct": 80,
        "hardStop": True,
        "unknownUsageBehavior": "block",
        "effectiveFrom": NOW.isoformat(),
        "effectiveUntil": (NOW + timedelta(days=60)).isoformat(),
        "owner": "杜大同",
        "overBudgetApprover": "杜大同",
        "lifecycle": "active",
    }


class CaptureStore:
    call = None

    def publish(self, scope, actor, key, item: BudgetRevisionCreate, *, expected_version=0):
        self.call = (scope.key, actor, key, expected_version, item)
        from aos_api.aip_budget_store import materialize_revision

        return materialize_revision(scope, actor, item, created_at=NOW)

    def get(self, scope, budget_id, revision=None):
        self.call = (scope.key, budget_id, revision)
        raise BudgetNotFound("budget not found")


def test_budget_api_uses_principal_scope_cas_and_exact_read(client) -> None:
    store = CaptureStore()
    client.app.dependency_overrides[aip_budgets.get_store] = lambda: store
    try:
        response = client.post(
            "/v1/aip/budgets",
            headers=headers(**{"Idempotency-Key": "budget-v1", "If-Match": "0"}),
            json={**body(), "lifecycle": "draft"},
        )
        assert response.status_code == 201, response.text
        assert store.call[:4] == (("org-org", "dev-project"), "user:dev", "budget-v1", 0)
        assert response.json()["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}

        missing = client.get(
            "/v1/aip/budgets/missing?revision=2",
            headers=headers("dev-org"),
        )
        assert missing.status_code == 404
        assert store.call == (("dev-org", "dev-project"), "missing", 2)
    finally:
        client.app.dependency_overrides.pop(aip_budgets.get_store, None)


def test_budget_api_fails_closed_before_store_for_active_without_formal_approval(client) -> None:
    store = CaptureStore()
    client.app.dependency_overrides[aip_budgets.get_store] = lambda: store
    try:
        response = client.post(
            "/v1/aip/budgets",
            headers=headers(**{"Idempotency-Key": "budget-active-v1", "If-Match": "0"}),
            json=body(),
        )
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "AIP_BUDGET_ACTIVE_APPROVAL_REQUIRED"
        assert store.call is None

        draft = {**body(), "lifecycle": "draft"}
        response = client.post(
            "/v1/aip/budgets",
            headers=headers(**{"Idempotency-Key": "budget-draft-v1", "If-Match": "0"}),
            json=draft,
        )
        assert response.status_code == 201, response.text
        assert store.call[:4] == (("org-org", "dev-project"), "user:dev", "budget-draft-v1", 0)
        assert response.json()["lifecycle"] == "draft"
    finally:
        client.app.dependency_overrides.pop(aip_budgets.get_store, None)


def test_budget_api_rejects_authority_injection_and_missing_write_headers(client) -> None:
    injected = body()
    injected["tenant"] = {"orgId": "dev-org", "projectId": "dev-project"}
    response = client.post(
        "/v1/aip/budgets",
        headers=headers(**{"Idempotency-Key": "budget-v1", "If-Match": "0"}),
        json=injected,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"

    response = client.post("/v1/aip/budgets", headers=headers(), json=body())
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
