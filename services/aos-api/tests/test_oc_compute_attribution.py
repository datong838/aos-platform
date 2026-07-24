"""
W5 — 计算归因
Tests: ComputeAttributionEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oc_compute_attribution import ComputeAttribution, ComputeAttributionEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ComputeAttributionEngine().reset()
    yield
    ComputeAttributionEngine().reset()


class TestComputeAttributionEngine:
    def test_register(self):
        item = ComputeAttribution(name="test-item")
        result = ComputeAttributionEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ComputeAttribution(name="get-test")
        ComputeAttributionEngine().register(item)
        found = ComputeAttributionEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ComputeAttributionEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ComputeAttributionEngine().register(ComputeAttribution(name=f"list-{i}"))
        items = ComputeAttributionEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ComputeAttribution(name="original")
        ComputeAttributionEngine().register(item)
        updated = ComputeAttributionEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ComputeAttributionEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ComputeAttribution(name="delete-me")
        ComputeAttributionEngine().register(item)
        assert ComputeAttributionEngine().delete(item.id) is True
        assert ComputeAttributionEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ComputeAttributionEngine().register(ComputeAttribution(name=f"cap-{i}"))
        assert len(ComputeAttributionEngine().list()) == 100

    def test_singleton(self):
        e1 = ComputeAttributionEngine()
        e2 = ComputeAttributionEngine()
        assert e1 is e2
