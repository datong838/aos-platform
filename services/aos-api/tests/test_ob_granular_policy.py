"""
W5 — 细粒度三层策略
Tests: GranularPolicyEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ob_granular_policy import GranularPolicy, GranularPolicyEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    GranularPolicyEngine().reset()
    yield
    GranularPolicyEngine().reset()


class TestGranularPolicyEngine:
    def test_register(self):
        item = GranularPolicy(name="test-item")
        result = GranularPolicyEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = GranularPolicy(name="get-test")
        GranularPolicyEngine().register(item)
        found = GranularPolicyEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert GranularPolicyEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            GranularPolicyEngine().register(GranularPolicy(name=f"list-{i}"))
        items = GranularPolicyEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = GranularPolicy(name="original")
        GranularPolicyEngine().register(item)
        updated = GranularPolicyEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert GranularPolicyEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = GranularPolicy(name="delete-me")
        GranularPolicyEngine().register(item)
        assert GranularPolicyEngine().delete(item.id) is True
        assert GranularPolicyEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            GranularPolicyEngine().register(GranularPolicy(name=f"cap-{i}"))
        assert len(GranularPolicyEngine().list()) == 100

    def test_singleton(self):
        e1 = GranularPolicyEngine()
        e2 = GranularPolicyEngine()
        assert e1 is e2
