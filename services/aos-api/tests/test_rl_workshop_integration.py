"""
W5 — Workshop 应用集成
Tests: WorkshopIntegrationEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.rl_workshop_integration import WorkshopIntegration, WorkshopIntegrationEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    WorkshopIntegrationEngine().reset()
    yield
    WorkshopIntegrationEngine().reset()


class TestWorkshopIntegrationEngine:
    def test_register(self):
        item = WorkshopIntegration(name="test-item")
        result = WorkshopIntegrationEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = WorkshopIntegration(name="get-test")
        WorkshopIntegrationEngine().register(item)
        found = WorkshopIntegrationEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert WorkshopIntegrationEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            WorkshopIntegrationEngine().register(WorkshopIntegration(name=f"list-{i}"))
        items = WorkshopIntegrationEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = WorkshopIntegration(name="original")
        WorkshopIntegrationEngine().register(item)
        updated = WorkshopIntegrationEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert WorkshopIntegrationEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = WorkshopIntegration(name="delete-me")
        WorkshopIntegrationEngine().register(item)
        assert WorkshopIntegrationEngine().delete(item.id) is True
        assert WorkshopIntegrationEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            WorkshopIntegrationEngine().register(WorkshopIntegration(name=f"cap-{i}"))
        assert len(WorkshopIntegrationEngine().list()) == 100

    def test_singleton(self):
        e1 = WorkshopIntegrationEngine()
        e2 = WorkshopIntegrationEngine()
        assert e1 is e2
