"""Workshop Phase 1 API tests — 16 endpoints.

Each router group has ≥3 tests (list, detail, CRUD).
Seed data is populated via the workshop seed orchestrator (in setup_module).
"""
from __future__ import annotations

import pytest

_SEEDED = False


def setup_module(_mod):
    global _SEEDED
    if not _SEEDED:
        from aos_api.demo.seed_workshop import seed_workshop

        seed_workshop()
        _SEEDED = True


# ── /v1/modules (existing, but verify new modules exist) ──


class TestModulesList:
    def test_list_includes_seeded_modules(self, client, auth_headers):
        r = client.get("/v1/modules", headers=auth_headers)
        assert r.status_code == 200
        ids = {m["id"] for m in r.json()["items"]}
        assert "dev-module-order" in ids
        assert "dev-module-risk" in ids

    def test_module_detail_has_category(self, client, auth_headers):
        r = client.get("/v1/modules/dev-module-order", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["category"] == "订单"

    def test_module_detail_not_found(self, client, auth_headers):
        r = client.get("/v1/modules/no-such-module", headers=auth_headers)
        assert r.status_code == 404


# ── /v1/modules/:id/config ──


class TestModuleConfig:
    def test_get_config_returns_canvas(self, client, auth_headers):
        r = client.get("/v1/modules/dev-module-order/config", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["moduleId"] == "dev-module-order"
        assert "layout" in body
        assert "components" in body

    def test_put_config_updates(self, client, auth_headers):
        new_layout = {"type": "page-layout", "children": ["a", "b"]}
        new_components = {"a": {"type": "stat-card"}}
        r = client.put(
            "/v1/modules/dev-module-order/config",
            headers=auth_headers,
            json={"layout": new_layout, "components": new_components},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["layout"]["children"] == ["a", "b"]
        assert body["version"] >= 1

    def test_get_config_empty_for_unknown(self, client, auth_headers):
        r = client.get("/v1/modules/no-such/config", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == 0


# ── /v1/modules/:id/widgets ──


class TestModuleWidgets:
    def test_list_widgets(self, client, auth_headers):
        r = client.get("/v1/modules/dev-module-order/widgets", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["moduleId"] == "dev-module-order"
        assert body["count"] >= 10

    def test_create_and_delete_widget(self, client, auth_headers):
        create = client.post(
            "/v1/modules/dev-module-order/widgets",
            headers=auth_headers,
            json={
                "widgetId": "w-stat-card",
                "type": "stat-card",
                "title": "测试卡片",
                "config": {"value": 42},
                "sortOrder": 99,
            },
        )
        assert create.status_code == 200
        item = create.json()["item"]
        assert item["title"] == "测试卡片"

        # Update
        upd = client.put(
            f"/v1/modules/dev-module-order/widgets/{item['id']}",
            headers=auth_headers,
            json={"title": "改名后"},
        )
        assert upd.status_code == 200
        assert upd.json()["item"]["title"] == "改名后"

        # Delete
        dele = client.delete(
            f"/v1/modules/dev-module-order/widgets/{item['id']}",
            headers=auth_headers,
        )
        assert dele.status_code == 200
        assert dele.json()["ok"] is True

    def test_update_widget_not_found(self, client, auth_headers):
        r = client.put(
            "/v1/modules/dev-module-order/widgets/no-such",
            headers=auth_headers,
            json={"title": "x"},
        )
        assert r.status_code == 404


# ── /v1/modules/:id/events (existing router, verify seed) ──


class TestModuleEvents:
    def test_list_events_seeded(self, client, auth_headers):
        r = client.get("/v1/modules/dev-module-order/events")
        assert r.status_code == 200
        body = r.json()
        assert body["moduleId"] == "dev-module-order"
        assert body["count"] >= 1

    def test_create_event(self, client, auth_headers):
        r = client.post(
            "/v1/modules/dev-module-order/events",
            json={"name": "测试事件", "trigger": {"type": "on_click"}, "action": {"type": "query"}},
        )
        assert r.status_code == 200
        assert r.json()["item"]["name"] == "测试事件"

    def test_triggers_catalog(self, client, auth_headers):
        r = client.get("/v1/modules/dev-module-order/events/triggers/catalog")
        assert r.status_code == 200
        assert len(r.json()["items"]) >= 6


# ── /v1/modules/:id/queries ──


class TestModuleQueries:
    def test_list_queries(self, client, auth_headers):
        r = client.get("/v1/modules/dev-module-order/queries", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["moduleId"] == "dev-module-order"
        assert body["count"] >= 2

    def test_queries_have_statements(self, client, auth_headers):
        r = client.get("/v1/modules/dev-module-order/queries", headers=auth_headers)
        items = r.json()["items"]
        assert all("statement" in q for q in items)

    def test_queries_for_risk_module(self, client, auth_headers):
        r = client.get("/v1/modules/dev-module-risk/queries", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["count"] >= 2


# ── /v1/modules/:id/variables ──


class TestModuleVariables:
    def test_list_variables(self, client, auth_headers):
        r = client.get("/v1/modules/dev-module-order/variables", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 1

    def test_create_update_delete_variable(self, client, auth_headers):
        create = client.post(
            "/v1/modules/dev-module-order/variables",
            headers=auth_headers,
            json={"name": "测试变量", "varType": "string", "initialValue": "hello"},
        )
        assert create.status_code == 200
        vid = create.json()["item"]["id"]

        upd = client.put(
            f"/v1/modules/dev-module-order/variables/{vid}",
            headers=auth_headers,
            json={"currentValue": "world"},
        )
        assert upd.status_code == 200
        assert upd.json()["item"]["currentValue"] == "world"

        dele = client.delete(
            f"/v1/modules/dev-module-order/variables/{vid}",
            headers=auth_headers,
        )
        assert dele.status_code == 200

    def test_variable_usage(self, client, auth_headers):
        r = client.get(
            "/v1/modules/dev-module-order/variables/var-dev-module-order-1/usage",
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["variableId"] == "var-dev-module-order-1"
        assert "usages" in body


# ── /v1/modules/:id/interface ──


class TestModuleInterface:
    def test_get_interface(self, client, auth_headers):
        r = client.get("/v1/modules/dev-module-order/interface", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["moduleId"] == "dev-module-order"
        assert body["name"] == "OrderAPI"

    def test_put_interface(self, client, auth_headers):
        r = client.put(
            "/v1/modules/dev-module-order/interface",
            headers=auth_headers,
            json={
                "name": "NewAPI",
                "description": "更新后",
                "entryParams": [{"key": "id", "type": "string"}],
                "expose": {"endpoint": "/api/new"},
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "NewAPI"
        assert body["expose"]["endpoint"] == "/api/new"

    def test_get_interface_empty_for_unknown(self, client, auth_headers):
        r = client.get("/v1/modules/no-such/interface", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["name"] == ""


# ── /v1/modules/:id/deployments + deploy + rollback ──


class TestModuleDeployments:
    def test_list_deployments(self, client, auth_headers):
        r = client.get("/v1/modules/dev-module-order/deployments", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 3  # dev/staging/prod

    def test_deploy_creates_record(self, client, auth_headers):
        r = client.post(
            "/v1/modules/dev-module-order/deploy",
            headers=auth_headers,
            json={"environment": "dev", "version": "2.0.0"},
        )
        assert r.status_code == 200
        item = r.json()["item"]
        assert item["environment"] == "dev"
        assert item["version"] == "2.0.0"

    def test_rollback(self, client, auth_headers):
        # List existing deployments
        deps = client.get(
            "/v1/modules/dev-module-order/deployments", headers=auth_headers
        ).json()["items"]
        target_id = deps[0]["id"]

        r = client.post(
            "/v1/modules/dev-module-order/rollback",
            headers=auth_headers,
            json={"targetDeploymentId": target_id},
        )
        assert r.status_code == 200
        assert r.json()["item"]["status"] == "rollback"

    def test_rollback_not_found(self, client, auth_headers):
        r = client.post(
            "/v1/modules/dev-module-order/rollback",
            headers=auth_headers,
            json={"targetDeploymentId": "no-such"},
        )
        assert r.status_code == 404


# ── /v1/widgets (registry/catalog) ──


class TestWidgetsRegistry:
    def test_list_widgets(self, client, auth_headers):
        r = client.get("/v1/widgets", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 16

    def test_list_widgets_filter_by_source(self, client, auth_headers):
        r = client.get("/v1/widgets?source=marketplace", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(w["source"] == "marketplace" for w in items)
        assert len(items) >= 3

    def test_get_widget_detail(self, client, auth_headers):
        r = client.get("/v1/widgets/w-stat-card", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["id"] == "w-stat-card"

    def test_create_widget(self, client, auth_headers):
        r = client.post(
            "/v1/widgets",
            headers=auth_headers,
            json={"name": "CustomWidget", "type": "custom-widget", "source": "custom"},
        )
        assert r.status_code == 200
        assert r.json()["item"]["name"] == "CustomWidget"


# ── /v1/themes ──


class TestThemes:
    def test_list_themes(self, client, auth_headers):
        r = client.get("/v1/themes", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 3
        ids = {t["id"] for t in body["items"]}
        assert "theme-light" in ids
        assert "theme-dark" in ids

    def test_get_theme_detail(self, client, auth_headers):
        r = client.get("/v1/themes/theme-light", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "浅色"
        assert body["isPreset"] is True
        assert "colorPrimary" in body["tokens"]

    def test_create_and_delete_theme(self, client, auth_headers):
        create = client.post(
            "/v1/themes",
            headers=auth_headers,
            json={
                "name": "我的主题",
                "mode": "light",
                "tokens": {"colorPrimary": "#ff0000"},
            },
        )
        assert create.status_code == 200
        tid = create.json()["item"]["id"]

        # Update
        upd = client.put(
            f"/v1/themes/{tid}",
            headers=auth_headers,
            json={"name": "改名主题"},
        )
        assert upd.status_code == 200
        assert upd.json()["name"] == "改名主题"

        # Delete
        dele = client.delete(f"/v1/themes/{tid}", headers=auth_headers)
        assert dele.status_code == 200

    def test_cannot_delete_preset(self, client, auth_headers):
        r = client.delete("/v1/themes/theme-light", headers=auth_headers)
        assert r.status_code == 404
