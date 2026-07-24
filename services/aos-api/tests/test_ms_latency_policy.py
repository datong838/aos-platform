"""
W5 — 延迟策略
Tests: LatencyPolicyEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_latency_policy import LatencyPolicy, LatencyPolicyEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    LatencyPolicyEngine().reset()
    yield
    LatencyPolicyEngine().reset()


class TestLatencyPolicyEngine:
    def test_register(self):
        item = LatencyPolicy(name="test-item")
        result = LatencyPolicyEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = LatencyPolicy(name="get-test")
        LatencyPolicyEngine().register(item)
        found = LatencyPolicyEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert LatencyPolicyEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            LatencyPolicyEngine().register(LatencyPolicy(name=f"list-{i}"))
        items = LatencyPolicyEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = LatencyPolicy(name="original")
        LatencyPolicyEngine().register(item)
        updated = LatencyPolicyEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert LatencyPolicyEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = LatencyPolicy(name="delete-me")
        LatencyPolicyEngine().register(item)
        assert LatencyPolicyEngine().delete(item.id) is True
        assert LatencyPolicyEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            LatencyPolicyEngine().register(LatencyPolicy(name=f"cap-{i}"))
        assert len(LatencyPolicyEngine().list()) == 100

    def test_singleton(self):
        e1 = LatencyPolicyEngine()
        e2 = LatencyPolicyEngine()
        assert e1 is e2
