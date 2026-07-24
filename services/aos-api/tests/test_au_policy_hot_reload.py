"""
W5 — 策略热更新
Tests: PolicyHotReloadEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.au_policy_hot_reload import PolicyHotReload, PolicyHotReloadEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    PolicyHotReloadEngine().reset()
    yield
    PolicyHotReloadEngine().reset()


class TestPolicyHotReloadEngine:
    def test_register(self):
        item = PolicyHotReload(name="test-item")
        result = PolicyHotReloadEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = PolicyHotReload(name="get-test")
        PolicyHotReloadEngine().register(item)
        found = PolicyHotReloadEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert PolicyHotReloadEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            PolicyHotReloadEngine().register(PolicyHotReload(name=f"list-{i}"))
        items = PolicyHotReloadEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = PolicyHotReload(name="original")
        PolicyHotReloadEngine().register(item)
        updated = PolicyHotReloadEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert PolicyHotReloadEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = PolicyHotReload(name="delete-me")
        PolicyHotReloadEngine().register(item)
        assert PolicyHotReloadEngine().delete(item.id) is True
        assert PolicyHotReloadEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            PolicyHotReloadEngine().register(PolicyHotReload(name=f"cap-{i}"))
        assert len(PolicyHotReloadEngine().list()) == 100

    def test_singleton(self):
        e1 = PolicyHotReloadEngine()
        e2 = PolicyHotReloadEngine()
        assert e1 is e2
