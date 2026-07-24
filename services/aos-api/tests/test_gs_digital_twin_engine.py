"""
W6 — 数字孪生引擎
Tests: DigitalTwinEngineEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.gs_digital_twin_engine import DigitalTwinEngine, DigitalTwinEngineEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    DigitalTwinEngineEngine().reset()
    yield
    DigitalTwinEngineEngine().reset()


class TestDigitalTwinEngineEngine:
    def test_register(self):
        item = DigitalTwinEngine(name="test-item")
        result = DigitalTwinEngineEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = DigitalTwinEngine(name="get-test")
        DigitalTwinEngineEngine().register(item)
        found = DigitalTwinEngineEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert DigitalTwinEngineEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            DigitalTwinEngineEngine().register(DigitalTwinEngine(name=f"list-{i}"))
        items = DigitalTwinEngineEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = DigitalTwinEngine(name="original")
        DigitalTwinEngineEngine().register(item)
        updated = DigitalTwinEngineEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert DigitalTwinEngineEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = DigitalTwinEngine(name="delete-me")
        DigitalTwinEngineEngine().register(item)
        assert DigitalTwinEngineEngine().delete(item.id) is True
        assert DigitalTwinEngineEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            DigitalTwinEngineEngine().register(DigitalTwinEngine(name=f"cap-{i}"))
        assert len(DigitalTwinEngineEngine().list()) == 100

    def test_singleton(self):
        e1 = DigitalTwinEngineEngine()
        e2 = DigitalTwinEngineEngine()
        assert e1 is e2
