"""
W6 — 坐标系与投影
Tests: CoordProjectionEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.gs_coord_projection import CoordProjection, CoordProjectionEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    CoordProjectionEngine().reset()
    yield
    CoordProjectionEngine().reset()


class TestCoordProjectionEngine:
    def test_register(self):
        item = CoordProjection(name="test-item")
        result = CoordProjectionEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = CoordProjection(name="get-test")
        CoordProjectionEngine().register(item)
        found = CoordProjectionEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert CoordProjectionEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            CoordProjectionEngine().register(CoordProjection(name=f"list-{i}"))
        items = CoordProjectionEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = CoordProjection(name="original")
        CoordProjectionEngine().register(item)
        updated = CoordProjectionEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert CoordProjectionEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = CoordProjection(name="delete-me")
        CoordProjectionEngine().register(item)
        assert CoordProjectionEngine().delete(item.id) is True
        assert CoordProjectionEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            CoordProjectionEngine().register(CoordProjection(name=f"cap-{i}"))
        assert len(CoordProjectionEngine().list()) == 100

    def test_singleton(self):
        e1 = CoordProjectionEngine()
        e2 = CoordProjectionEngine()
        assert e1 is e2
