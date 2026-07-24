"""
W5 — Gotham 集成
Tests: GothamIntegrationEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oe_gotham_integration import GothamIntegration, GothamIntegrationEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    GothamIntegrationEngine().reset()
    yield
    GothamIntegrationEngine().reset()


class TestGothamIntegrationEngine:
    def test_register(self):
        item = GothamIntegration(name="test-item")
        result = GothamIntegrationEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = GothamIntegration(name="get-test")
        GothamIntegrationEngine().register(item)
        found = GothamIntegrationEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert GothamIntegrationEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            GothamIntegrationEngine().register(GothamIntegration(name=f"list-{i}"))
        items = GothamIntegrationEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = GothamIntegration(name="original")
        GothamIntegrationEngine().register(item)
        updated = GothamIntegrationEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert GothamIntegrationEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = GothamIntegration(name="delete-me")
        GothamIntegrationEngine().register(item)
        assert GothamIntegrationEngine().delete(item.id) is True
        assert GothamIntegrationEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            GothamIntegrationEngine().register(GothamIntegration(name=f"cap-{i}"))
        assert len(GothamIntegrationEngine().list()) == 100

    def test_singleton(self):
        e1 = GothamIntegrationEngine()
        e2 = GothamIntegrationEngine()
        assert e1 is e2
