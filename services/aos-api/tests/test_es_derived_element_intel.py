"""
W6 — 派生元素智能
Tests: DerivedElementIntelEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.es_derived_element_intel import DerivedElementIntel, DerivedElementIntelEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    DerivedElementIntelEngine().reset()
    yield
    DerivedElementIntelEngine().reset()


class TestDerivedElementIntelEngine:
    def test_register(self):
        item = DerivedElementIntel(name="test-item")
        result = DerivedElementIntelEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = DerivedElementIntel(name="get-test")
        DerivedElementIntelEngine().register(item)
        found = DerivedElementIntelEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert DerivedElementIntelEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            DerivedElementIntelEngine().register(DerivedElementIntel(name=f"list-{i}"))
        items = DerivedElementIntelEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = DerivedElementIntel(name="original")
        DerivedElementIntelEngine().register(item)
        updated = DerivedElementIntelEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert DerivedElementIntelEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = DerivedElementIntel(name="delete-me")
        DerivedElementIntelEngine().register(item)
        assert DerivedElementIntelEngine().delete(item.id) is True
        assert DerivedElementIntelEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            DerivedElementIntelEngine().register(DerivedElementIntel(name=f"cap-{i}"))
        assert len(DerivedElementIntelEngine().list()) == 100

    def test_singleton(self):
        e1 = DerivedElementIntelEngine()
        e2 = DerivedElementIntelEngine()
        assert e1 is e2
