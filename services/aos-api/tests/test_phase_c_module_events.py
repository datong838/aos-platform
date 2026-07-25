"""Phase C · 222plan — Module Events CRUD tests.

Tests:
  - Event create + get (2 cases)
  - Event list + seed (1 case)
  - Event update (1 case)
  - Event delete (1 case)
  - Triggers catalog (1 case)
  - Actions catalog (1 case)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestModuleEventsCRUD:
    """Test event binding CRUD operations."""

    def test_create_event(self, client):
        """Create a new event binding."""
        resp = client.post(
            "/v1/modules/mod-canvas-draft/events",
            json={
                "name": "测试点击事件",
                "trigger": {"type": "on_click", "widgetId": "btn-submit"},
                "action": {"type": "query", "target": "object_table"},
                "enabled": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        item = data["item"]
        assert item["name"] == "测试点击事件"
        assert item["trigger"]["type"] == "on_click"
        assert item["action"]["target"] == "object_table"
        assert item["enabled"] is True

    def test_list_events_with_seed(self, client):
        """List events for a module should seed defaults if empty."""
        resp = client.get("/v1/modules/mod-canvas-draft/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["moduleId"] == "mod-canvas-draft"
        assert data["count"] >= 2  # at least the default seed events
        # Check structure of first event
        first = data["items"][0]
        assert "id" in first
        assert "name" in first
        assert "trigger" in first
        assert "action" in first
        assert "enabled" in first

    def test_get_single_event(self, client):
        """Get a single event by ID."""
        # First create
        create = client.post(
            "/v1/modules/mod-canvas-draft/events",
            json={
                "name": "单查事件",
                "trigger": {"type": "on_load"},
                "action": {"type": "navigate", "target": "/dashboard"},
            },
        )
        eid = create.json()["item"]["id"]

        # Then get
        resp = client.get(f"/v1/modules/mod-canvas-draft/events/{eid}")
        assert resp.status_code == 200
        item = resp.json()["item"]
        assert item["id"] == eid
        assert item["name"] == "单查事件"

    def test_update_event(self, client):
        """Update an event binding."""
        # Create
        create = client.post(
            "/v1/modules/mod-canvas-draft/events",
            json={
                "name": "原名",
                "trigger": {"type": "on_click"},
                "action": {"type": "query"},
            },
        )
        eid = create.json()["item"]["id"]

        # Update
        resp = client.put(
            f"/v1/modules/mod-canvas-draft/events/{eid}",
            json={
                "name": "新名",
                "enabled": False,
                "trigger": {"type": "interval", "value": 60},
            },
        )
        assert resp.status_code == 200
        item = resp.json()["item"]
        assert item["name"] == "新名"
        assert item["enabled"] is False
        assert item["trigger"]["value"] == 60

    def test_delete_event(self, client):
        """Delete an event binding."""
        # Create
        create = client.post(
            "/v1/modules/mod-canvas-draft/events",
            json={"name": "待删", "trigger": {}, "action": {}},
        )
        eid = create.json()["item"]["id"]

        # Delete
        resp = client.delete(f"/v1/modules/mod-canvas-draft/events/{eid}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify gone
        get_resp = client.get(f"/v1/modules/mod-canvas-draft/events/{eid}")
        assert get_resp.status_code == 404

    def test_triggers_catalog(self, client):
        """Get the catalog of available trigger types."""
        resp = client.get("/v1/modules/mod-canvas-draft/events/triggers/catalog")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 6
        types = [t["type"] for t in items]
        assert "on_click" in types
        assert "interval" in types
        assert "custom" in types

    def test_actions_catalog(self, client):
        """Get the catalog of available action types."""
        resp = client.get("/v1/modules/mod-canvas-draft/events/actions/catalog")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 6
        types = [a["type"] for a in items]
        assert "query" in types
        assert "set_variable" in types
        assert "navigate" in types
