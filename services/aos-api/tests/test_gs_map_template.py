"""
W6 — Map 模板
Tests: MapTemplateEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.gs_map_template import MapTemplate, MapTemplateEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    MapTemplateEngine().reset()
    yield
    MapTemplateEngine().reset()


class TestMapTemplateEngine:
    def test_register(self):
        item = MapTemplate(name="test-item")
        result = MapTemplateEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = MapTemplate(name="get-test")
        MapTemplateEngine().register(item)
        found = MapTemplateEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert MapTemplateEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            MapTemplateEngine().register(MapTemplate(name=f"list-{i}"))
        items = MapTemplateEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = MapTemplate(name="original")
        MapTemplateEngine().register(item)
        updated = MapTemplateEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert MapTemplateEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = MapTemplate(name="delete-me")
        MapTemplateEngine().register(item)
        assert MapTemplateEngine().delete(item.id) is True
        assert MapTemplateEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            MapTemplateEngine().register(MapTemplate(name=f"cap-{i}"))
        assert len(MapTemplateEngine().list()) == 100

    def test_singleton(self):
        e1 = MapTemplateEngine()
        e2 = MapTemplateEngine()
        assert e1 is e2
