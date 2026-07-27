"""Phase 2 · Model Management API tests — 10 endpoints.

Each router group has ≥3 tests (list, detail, CRUD).
Seed data is populated via the seed orchestrator (in setup_module).
"""
from __future__ import annotations

import pytest

_SEEDED = False


def setup_module(_mod):
    global _SEEDED
    if not _SEEDED:
        from aos_api.demo.seed_capacity_usage import seed_capacity_usage
        from aos_api.demo.seed_model_catalog import seed_model_catalog
        from aos_api.demo.seed_model_routes import seed_model_routes
        from aos_api.demo.seed_providers import seed_providers
        from aos_api.demo.seed_registered_models import seed_registered_models

        seed_model_catalog()
        seed_registered_models()
        seed_providers()
        seed_model_routes()
        seed_capacity_usage()
        _SEEDED = True


# ── GET /v1/aip/model-catalog ──


class TestModelCatalog:
    def test_list_returns_12(self, client, auth_headers):
        r = client.get("/v1/aip/model-catalog", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 12
        ids = {m["id"] for m in body["items"]}
        assert "mc-gpt-4o" in ids
        assert "mc-glm-4-plus" in ids
        assert "mc-palm-2" in ids

    def test_list_filter_by_provider(self, client, auth_headers):
        r = client.get("/v1/aip/model-catalog?provider=deepseek", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(m["provider"] == "deepseek" for m in items)
        assert len(items) >= 2

    def test_list_filter_by_capability(self, client, auth_headers):
        r = client.get("/v1/aip/model-catalog?capability=vision", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert all("vision" in m["capabilities"] for m in items)
        assert len(items) >= 2  # gpt-4o, claude-3.5-sonnet

    def test_get_detail(self, client, auth_headers):
        r = client.get("/v1/aip/model-catalog/mc-gpt-4o", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["model"] == "gpt-4o"
        assert body["contextWindow"] == 128000
        assert "vision" in body["capabilities"]

    def test_get_detail_not_found(self, client, auth_headers):
        r = client.get("/v1/aip/model-catalog/no-such", headers=auth_headers)
        assert r.status_code == 404


# ── POST /v1/aip/model-catalog/:id/register + registered-models ──


class TestRegisteredModels:
    def test_register_creates_record(self, client, auth_headers):
        r = client.post(
            "/v1/aip/model-catalog/mc-claude-3-haiku/register",
            headers=auth_headers,
            json={
                "alias": "haiku-fast",
                "quota": {"rpm": 100, "tpm": 100000},
                "status": "enabled",
            },
        )
        assert r.status_code == 200
        item = r.json()["item"]
        assert item["modelId"] == "mc-claude-3-haiku"
        assert item["alias"] == "haiku-fast"
        assert item["quota"]["rpm"] == 100
        assert item["status"] == "enabled"

    def test_register_unknown_model_404(self, client, auth_headers):
        r = client.post(
            "/v1/aip/model-catalog/mc-no-such/register",
            headers=auth_headers,
            json={"alias": "x"},
        )
        assert r.status_code == 404

    def test_list_registered(self, client, auth_headers):
        r = client.get("/v1/aip/registered-models", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 4
        ids = {m["modelId"] for m in body["items"]}
        assert "mc-gpt-4o" in ids

    def test_list_registered_filter_status(self, client, auth_headers):
        r = client.get("/v1/aip/registered-models?status=disabled", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(i["status"] == "disabled" for i in items)
        assert any(i["modelId"] == "mc-glm-4-plus" for i in items)

    def test_get_registered_detail(self, client, auth_headers):
        r = client.get("/v1/aip/registered-models/rm-gpt-4o", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["alias"] == "gpt-4o-primary"
        assert body["quota"]["rpm"] == 600

    def test_get_registered_not_found(self, client, auth_headers):
        r = client.get("/v1/aip/registered-models/no-such", headers=auth_headers)
        assert r.status_code == 404


# ── GET /v1/aip/model-admin/providers + /providers/:id/health ──


class TestProviders:
    def test_list_providers(self, client, auth_headers):
        r = client.get("/v1/aip/model-admin/providers", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 4
        names = {p["name"] for p in body["items"]}
        assert "深度求索" in names
        assert "Anthropic" in names

    def test_provider_has_masked_key(self, client, auth_headers):
        r = client.get("/v1/aip/model-admin/providers/prov-deepseek", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "prov-deepseek"
        assert "***" in body["apiKeyMasked"]
        assert body["baseUrl"].startswith("https://")

    def test_provider_not_found(self, client, auth_headers):
        r = client.get("/v1/aip/model-admin/providers/no-such", headers=auth_headers)
        assert r.status_code == 404

    def test_provider_health(self, client, auth_headers):
        r = client.get("/v1/aip/model-admin/providers/prov-azure-openai/health", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["providerId"] == "prov-azure-openai"
        assert body["p50LatencyMs"] > 0
        assert 0 <= body["availabilityPct"] <= 100
        assert body["status"] in ("normal", "warming", "disabled")

    def test_provider_health_not_found(self, client, auth_headers):
        r = client.get("/v1/aip/model-admin/providers/no-such/health", headers=auth_headers)
        assert r.status_code == 404

    def test_list_providers_filter_status(self, client, auth_headers):
        r = client.get("/v1/aip/model-admin/providers?status=warming", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(p["status"] == "warming" for p in items)
        assert len(items) >= 1


# ── GET /v1/aip/model-admin/models (unified) ──


class TestModelsUnified:
    def test_list_models_has_registration(self, client, auth_headers):
        r = client.get("/v1/aip/model-admin/models", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        # gpt-4o is registered
        gpt4o = next(m for m in items if m["id"] == "mc-gpt-4o")
        assert gpt4o["registered"] is True
        assert gpt4o["registration"] is not None
        assert gpt4o["registration"]["alias"] == "gpt-4o-primary"

    def test_list_models_unregistered_marked(self, client, auth_headers):
        r = client.get("/v1/aip/model-admin/models", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        # palm-2 not registered
        palm = next(m for m in items if m["id"] == "mc-palm-2")
        assert palm["registered"] is False
        assert palm["registration"] is None

    def test_list_models_filter_provider(self, client, auth_headers):
        r = client.get("/v1/aip/model-admin/models?provider=anthropic", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(m["provider"] == "anthropic" for m in items)
        assert len(items) >= 2


# ── GET/PUT /v1/aip/model-admin/routes ──


class TestModelRoutes:
    def test_list_routes(self, client, auth_headers):
        r = client.get("/v1/aip/model-admin/routes", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 4
        task_types = {rt["taskType"] for rt in body["items"]}
        assert "default" in task_types
        assert "code_generation" in task_types
        assert "vision" in task_types
        assert "fallback" in task_types

    def test_list_routes_filter_task_type(self, client, auth_headers):
        r = client.get("/v1/aip/model-admin/routes?taskType=default", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(rt["taskType"] == "default" for rt in items)
        assert len(items) == 1

    def test_put_routes_replaces(self, client, auth_headers):
        # First fetch existing
        existing = client.get("/v1/aip/model-admin/routes", headers=auth_headers).json()["items"]
        # Modify: disable the default route
        new_routes = [
            {"taskType": rt["taskType"], "primaryModel": rt["primaryModel"],
             "fallbackModel": rt["fallbackModel"], "outboundPolicy": rt["outboundPolicy"],
             "priority": rt["priority"], "enabled": False}
            for rt in existing
        ]
        r = client.put("/v1/aip/model-admin/routes", headers=auth_headers, json={"routes": new_routes})
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(rt["enabled"] is False for rt in items)
        # restore
        restore = [
            {**rt, "enabled": True} for rt in new_routes
        ]
        client.put("/v1/aip/model-admin/routes", headers=auth_headers, json={"routes": restore})

    def test_put_routes_can_add_new(self, client, auth_headers):
        existing = client.get("/v1/aip/model-admin/routes", headers=auth_headers).json()["items"]
        new_set = [
            {"taskType": rt["taskType"], "primaryModel": rt["primaryModel"],
             "fallbackModel": rt["fallbackModel"], "outboundPolicy": rt["outboundPolicy"],
             "priority": rt["priority"], "enabled": rt["enabled"]}
            for rt in existing
        ] + [
            {"taskType": "rag", "primaryModel": "rm-glm-4-plus",
             "fallbackModel": "", "outboundPolicy": "deny_public",
             "priority": 70, "enabled": True}
        ]
        r = client.put("/v1/aip/model-admin/routes", headers=auth_headers, json={"routes": new_set})
        assert r.status_code == 200
        assert r.json()["count"] == len(new_set)
        # Verify it's there
        rag = client.get("/v1/aip/model-admin/routes?taskType=rag", headers=auth_headers)
        assert rag.json()["count"] == 1


# ── GET/PUT /v1/aip/capacity/project-limits + user-limits ──


class TestCapacityLimits:
    def test_get_project_limits_default(self, client, auth_headers):
        r = client.get("/v1/aip/capacity/project-limits", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == "project"
        assert body["rpmLimit"] >= 1
        assert body["tpmLimit"] >= 1

    def test_put_project_limits(self, client, auth_headers):
        r = client.put(
            "/v1/aip/capacity/project-limits",
            headers=auth_headers,
            json={"rpmLimit": 999, "tpmLimit": 999000},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["rpmLimit"] == 999
        assert body["tpmLimit"] == 999000
        # Read back
        r2 = client.get("/v1/aip/capacity/project-limits", headers=auth_headers)
        assert r2.json()["rpmLimit"] == 999

    def test_put_project_limits_with_project_id(self, client, auth_headers):
        r = client.put(
            "/v1/aip/capacity/project-limits?projectId=prj-special",
            headers=auth_headers,
            json={"rpmLimit": 500, "tpmLimit": 500000},
        )
        assert r.status_code == 200
        assert r.json()["scopeKey"] == "prj-special"

    def test_get_user_limits(self, client, auth_headers):
        r = client.get(
            "/v1/aip/capacity/user-limits?userId=alice",
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == "user"
        assert body["scopeKey"] == "alice"

    def test_put_user_limits(self, client, auth_headers):
        r = client.put(
            "/v1/aip/capacity/user-limits?userId=bob",
            headers=auth_headers,
            json={"rpmLimit": 50, "tpmLimit": 50000},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["rpmLimit"] == 50
        # read back
        r2 = client.get("/v1/aip/capacity/user-limits?userId=bob", headers=auth_headers)
        assert r2.json()["rpmLimit"] == 50


# ── GET /v1/aip/capacity/usage ──


class TestCapacityUsage:
    def test_list_usage_returns_30_days(self, client, auth_headers):
        r = client.get("/v1/aip/capacity/usage", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 30
        # all items have required fields
        for it in body["items"]:
            assert "day" in it
            assert "totalRequests" in it
            assert "totalTokens" in it
            assert "cost" in it
            assert "peakRpm" in it

    def test_usage_summary(self, client, auth_headers):
        r = client.get("/v1/aip/capacity/usage", headers=auth_headers)
        assert r.status_code == 200
        summary = r.json()["summary"]
        assert summary["totalRequests"] > 0
        assert summary["totalTokens"] > 0
        assert summary["totalCost"] > 0
        assert summary["peakRpm"] > 0

    def test_usage_filter_by_date(self, client, auth_headers):
        # First fetch all to find a date range
        all_items = client.get("/v1/aip/capacity/usage", headers=auth_headers).json()["items"]
        days = sorted(it["day"] for it in all_items)
        start = days[0]
        end = days[5]
        r = client.get(
            f"/v1/aip/capacity/usage?startDate={start}&endDate={end}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        items = r.json()["items"]
        # inclusive
        assert len(items) == 6

    def test_usage_limit_param(self, client, auth_headers):
        r = client.get("/v1/aip/capacity/usage?limit=7", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["count"] <= 7
