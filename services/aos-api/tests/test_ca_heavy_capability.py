"""
W5 — 重能力接入页
Tests: HeavyCapabilityEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ca_heavy_capability import HeavyCapability, HeavyCapabilityEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    HeavyCapabilityEngine().reset()
    yield
    HeavyCapabilityEngine().reset()


class TestHeavyCapabilityEngine:
    def test_register(self):
        item = HeavyCapability(name="test-item")
        result = HeavyCapabilityEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = HeavyCapability(name="get-test")
        HeavyCapabilityEngine().register(item)
        found = HeavyCapabilityEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert HeavyCapabilityEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            HeavyCapabilityEngine().register(HeavyCapability(name=f"list-{i}"))
        items = HeavyCapabilityEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = HeavyCapability(name="original")
        HeavyCapabilityEngine().register(item)
        updated = HeavyCapabilityEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert HeavyCapabilityEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = HeavyCapability(name="delete-me")
        HeavyCapabilityEngine().register(item)
        assert HeavyCapabilityEngine().delete(item.id) is True
        assert HeavyCapabilityEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            HeavyCapabilityEngine().register(HeavyCapability(name=f"cap-{i}"))
        assert len(HeavyCapabilityEngine().list()) == 100

    def test_singleton(self):
        e1 = HeavyCapabilityEngine()
        e2 = HeavyCapabilityEngine()
        assert e1 is e2
