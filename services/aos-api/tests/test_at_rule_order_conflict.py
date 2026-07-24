"""
W5 — 规则顺序冲突检测
Tests: RuleOrderConflictEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.at_rule_order_conflict import RuleOrderConflict, RuleOrderConflictEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    RuleOrderConflictEngine().reset()
    yield
    RuleOrderConflictEngine().reset()


class TestRuleOrderConflictEngine:
    def test_register(self):
        item = RuleOrderConflict(name="test-item")
        result = RuleOrderConflictEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = RuleOrderConflict(name="get-test")
        RuleOrderConflictEngine().register(item)
        found = RuleOrderConflictEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert RuleOrderConflictEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            RuleOrderConflictEngine().register(RuleOrderConflict(name=f"list-{i}"))
        items = RuleOrderConflictEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = RuleOrderConflict(name="original")
        RuleOrderConflictEngine().register(item)
        updated = RuleOrderConflictEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert RuleOrderConflictEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = RuleOrderConflict(name="delete-me")
        RuleOrderConflictEngine().register(item)
        assert RuleOrderConflictEngine().delete(item.id) is True
        assert RuleOrderConflictEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            RuleOrderConflictEngine().register(RuleOrderConflict(name=f"cap-{i}"))
        assert len(RuleOrderConflictEngine().list()) == 100

    def test_singleton(self):
        e1 = RuleOrderConflictEngine()
        e2 = RuleOrderConflictEngine()
        assert e1 is e2
