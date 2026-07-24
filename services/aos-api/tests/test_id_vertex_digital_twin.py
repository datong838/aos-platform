"""
W6 — Vertex 数字孪生
Tests: VertexDigitalTwinEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.id_vertex_digital_twin import VertexDigitalTwin, VertexDigitalTwinEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    VertexDigitalTwinEngine().reset()
    yield
    VertexDigitalTwinEngine().reset()


class TestVertexDigitalTwinEngine:
    def test_register(self):
        item = VertexDigitalTwin(name="test-item")
        result = VertexDigitalTwinEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = VertexDigitalTwin(name="get-test")
        VertexDigitalTwinEngine().register(item)
        found = VertexDigitalTwinEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert VertexDigitalTwinEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            VertexDigitalTwinEngine().register(VertexDigitalTwin(name=f"list-{i}"))
        items = VertexDigitalTwinEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = VertexDigitalTwin(name="original")
        VertexDigitalTwinEngine().register(item)
        updated = VertexDigitalTwinEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert VertexDigitalTwinEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = VertexDigitalTwin(name="delete-me")
        VertexDigitalTwinEngine().register(item)
        assert VertexDigitalTwinEngine().delete(item.id) is True
        assert VertexDigitalTwinEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            VertexDigitalTwinEngine().register(VertexDigitalTwin(name=f"cap-{i}"))
        assert len(VertexDigitalTwinEngine().list()) == 100

    def test_singleton(self):
        e1 = VertexDigitalTwinEngine()
        e2 = VertexDigitalTwinEngine()
        assert e1 is e2
