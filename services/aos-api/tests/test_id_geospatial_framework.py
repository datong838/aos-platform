"""
W6 — 地理空间数据框架
Tests: IdGeospatialFrameworkEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.id_geospatial_framework import IdGeospatialFramework, IdGeospatialFrameworkEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    IdGeospatialFrameworkEngine().reset()
    yield
    IdGeospatialFrameworkEngine().reset()


class TestIdGeospatialFrameworkEngine:
    def test_register(self):
        item = IdGeospatialFramework(name="test-item")
        result = IdGeospatialFrameworkEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = IdGeospatialFramework(name="get-test")
        IdGeospatialFrameworkEngine().register(item)
        found = IdGeospatialFrameworkEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert IdGeospatialFrameworkEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            IdGeospatialFrameworkEngine().register(IdGeospatialFramework(name=f"list-{i}"))
        items = IdGeospatialFrameworkEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = IdGeospatialFramework(name="original")
        IdGeospatialFrameworkEngine().register(item)
        updated = IdGeospatialFrameworkEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert IdGeospatialFrameworkEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = IdGeospatialFramework(name="delete-me")
        IdGeospatialFrameworkEngine().register(item)
        assert IdGeospatialFrameworkEngine().delete(item.id) is True
        assert IdGeospatialFrameworkEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            IdGeospatialFrameworkEngine().register(IdGeospatialFramework(name=f"cap-{i}"))
        assert len(IdGeospatialFrameworkEngine().list()) == 100

    def test_singleton(self):
        e1 = IdGeospatialFrameworkEngine()
        e2 = IdGeospatialFrameworkEngine()
        assert e1 is e2
