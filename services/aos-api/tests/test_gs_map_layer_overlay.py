"""
W6 — 地图图层叠加
Tests: MapLayerOverlayEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.gs_map_layer_overlay import MapLayerOverlay, MapLayerOverlayEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    MapLayerOverlayEngine().reset()
    yield
    MapLayerOverlayEngine().reset()


class TestMapLayerOverlayEngine:
    def test_register(self):
        item = MapLayerOverlay(name="test-item")
        result = MapLayerOverlayEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = MapLayerOverlay(name="get-test")
        MapLayerOverlayEngine().register(item)
        found = MapLayerOverlayEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert MapLayerOverlayEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            MapLayerOverlayEngine().register(MapLayerOverlay(name=f"list-{i}"))
        items = MapLayerOverlayEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = MapLayerOverlay(name="original")
        MapLayerOverlayEngine().register(item)
        updated = MapLayerOverlayEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert MapLayerOverlayEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = MapLayerOverlay(name="delete-me")
        MapLayerOverlayEngine().register(item)
        assert MapLayerOverlayEngine().delete(item.id) is True
        assert MapLayerOverlayEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            MapLayerOverlayEngine().register(MapLayerOverlay(name=f"cap-{i}"))
        assert len(MapLayerOverlayEngine().list()) == 100

    def test_singleton(self):
        e1 = MapLayerOverlayEngine()
        e2 = MapLayerOverlayEngine()
        assert e1 is e2
