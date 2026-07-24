"""
W6 — 地理空间数据框架
Tests: GeospatialFrameworkEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.gs_geospatial_framework import GeospatialFramework, GeospatialFrameworkEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    GeospatialFrameworkEngine().reset()
    yield
    GeospatialFrameworkEngine().reset()


class TestGeospatialFrameworkEngine:
    def test_register(self):
        item = GeospatialFramework(name="test-item")
        result = GeospatialFrameworkEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = GeospatialFramework(name="get-test")
        GeospatialFrameworkEngine().register(item)
        found = GeospatialFrameworkEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert GeospatialFrameworkEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            GeospatialFrameworkEngine().register(GeospatialFramework(name=f"list-{i}"))
        items = GeospatialFrameworkEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = GeospatialFramework(name="original")
        GeospatialFrameworkEngine().register(item)
        updated = GeospatialFrameworkEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert GeospatialFrameworkEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = GeospatialFramework(name="delete-me")
        GeospatialFrameworkEngine().register(item)
        assert GeospatialFrameworkEngine().delete(item.id) is True
        assert GeospatialFrameworkEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            GeospatialFrameworkEngine().register(GeospatialFramework(name=f"cap-{i}"))
        assert len(GeospatialFrameworkEngine().list()) == 100

    def test_singleton(self):
        e1 = GeospatialFrameworkEngine()
        e2 = GeospatialFrameworkEngine()
        assert e1 is e2
