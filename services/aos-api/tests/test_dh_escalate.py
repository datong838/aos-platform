"""
W6 — 连续失败提升严重性
Tests: EscalateRuleEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.dh_escalate import EscalateRule, EscalateRuleEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    EscalateRuleEngine().reset()
    yield
    EscalateRuleEngine().reset()


class TestEscalateRuleEngine:
    def test_register(self):
        item = EscalateRule(name="test-item")
        result = EscalateRuleEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = EscalateRule(name="get-test")
        EscalateRuleEngine().register(item)
        found = EscalateRuleEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert EscalateRuleEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            EscalateRuleEngine().register(EscalateRule(name=f"list-{i}"))
        items = EscalateRuleEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = EscalateRule(name="original")
        EscalateRuleEngine().register(item)
        updated = EscalateRuleEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert EscalateRuleEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = EscalateRule(name="delete-me")
        EscalateRuleEngine().register(item)
        assert EscalateRuleEngine().delete(item.id) is True
        assert EscalateRuleEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            EscalateRuleEngine().register(EscalateRule(name=f"cap-{i}"))
        assert len(EscalateRuleEngine().list()) == 100

    def test_singleton(self):
        e1 = EscalateRuleEngine()
        e2 = EscalateRuleEngine()
        assert e1 is e2
