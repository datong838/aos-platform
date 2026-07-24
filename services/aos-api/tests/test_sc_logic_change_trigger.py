"""
W5 — 逻辑变更触发
Tests: LogicChangeTriggerEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.sc_logic_change_trigger import LogicChangeTrigger, LogicChangeTriggerEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    LogicChangeTriggerEngine().reset()
    yield
    LogicChangeTriggerEngine().reset()


class TestLogicChangeTriggerEngine:
    def test_register(self):
        item = LogicChangeTrigger(name="test-item")
        result = LogicChangeTriggerEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = LogicChangeTrigger(name="get-test")
        LogicChangeTriggerEngine().register(item)
        found = LogicChangeTriggerEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert LogicChangeTriggerEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            LogicChangeTriggerEngine().register(LogicChangeTrigger(name=f"list-{i}"))
        items = LogicChangeTriggerEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = LogicChangeTrigger(name="original")
        LogicChangeTriggerEngine().register(item)
        updated = LogicChangeTriggerEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert LogicChangeTriggerEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = LogicChangeTrigger(name="delete-me")
        LogicChangeTriggerEngine().register(item)
        assert LogicChangeTriggerEngine().delete(item.id) is True
        assert LogicChangeTriggerEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            LogicChangeTriggerEngine().register(LogicChangeTrigger(name=f"cap-{i}"))
        assert len(LogicChangeTriggerEngine().list()) == 100

    def test_singleton(self):
        e1 = LogicChangeTriggerEngine()
        e2 = LogicChangeTriggerEngine()
        assert e1 is e2
