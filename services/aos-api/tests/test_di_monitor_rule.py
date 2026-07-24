"""
W5 — 监控规则管理
Tests: MonitorRuleEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.di_monitor_rule import MonitorRule, MonitorRuleEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    MonitorRuleEngine().reset()
    yield
    MonitorRuleEngine().reset()


class TestMonitorRuleEngine:
    def test_register(self):
        item = MonitorRule(name="test-item")
        result = MonitorRuleEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = MonitorRule(name="get-test")
        MonitorRuleEngine().register(item)
        found = MonitorRuleEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert MonitorRuleEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            MonitorRuleEngine().register(MonitorRule(name=f"list-{i}"))
        items = MonitorRuleEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = MonitorRule(name="original")
        MonitorRuleEngine().register(item)
        updated = MonitorRuleEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert MonitorRuleEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = MonitorRule(name="delete-me")
        MonitorRuleEngine().register(item)
        assert MonitorRuleEngine().delete(item.id) is True
        assert MonitorRuleEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            MonitorRuleEngine().register(MonitorRule(name=f"cap-{i}"))
        assert len(MonitorRuleEngine().list()) == 100

    def test_singleton(self):
        e1 = MonitorRuleEngine()
        e2 = MonitorRuleEngine()
        assert e1 is e2
