"""
W5 — 透视到链接对象
Tests: PivotLinkedEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oe_pivot_linked import PivotLinked, PivotLinkedEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    PivotLinkedEngine().reset()
    yield
    PivotLinkedEngine().reset()


class TestPivotLinkedEngine:
    def test_register(self):
        item = PivotLinked(name="test-item")
        result = PivotLinkedEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = PivotLinked(name="get-test")
        PivotLinkedEngine().register(item)
        found = PivotLinkedEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert PivotLinkedEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            PivotLinkedEngine().register(PivotLinked(name=f"list-{i}"))
        items = PivotLinkedEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = PivotLinked(name="original")
        PivotLinkedEngine().register(item)
        updated = PivotLinkedEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert PivotLinkedEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = PivotLinked(name="delete-me")
        PivotLinkedEngine().register(item)
        assert PivotLinkedEngine().delete(item.id) is True
        assert PivotLinkedEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            PivotLinkedEngine().register(PivotLinked(name=f"cap-{i}"))
        assert len(PivotLinkedEngine().list()) == 100

    def test_singleton(self):
        e1 = PivotLinkedEngine()
        e2 = PivotLinkedEngine()
        assert e1 is e2
