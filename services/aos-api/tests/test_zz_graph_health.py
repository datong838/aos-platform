"""
W6 — 图谱健康度
Tests: GraphHealthEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.zz_graph_health import GraphHealth, GraphHealthEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    GraphHealthEngine().reset()
    yield
    GraphHealthEngine().reset()


class TestGraphHealthEngine:
    def test_register(self):
        item = GraphHealth(name="test-item")
        result = GraphHealthEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = GraphHealth(name="get-test")
        GraphHealthEngine().register(item)
        found = GraphHealthEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert GraphHealthEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            GraphHealthEngine().register(GraphHealth(name=f"list-{i}"))
        items = GraphHealthEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = GraphHealth(name="original")
        GraphHealthEngine().register(item)
        updated = GraphHealthEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert GraphHealthEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = GraphHealth(name="delete-me")
        GraphHealthEngine().register(item)
        assert GraphHealthEngine().delete(item.id) is True
        assert GraphHealthEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            GraphHealthEngine().register(GraphHealth(name=f"cap-{i}"))
        assert len(GraphHealthEngine().list()) == 100

    def test_singleton(self):
        e1 = GraphHealthEngine()
        e2 = GraphHealthEngine()
        assert e1 is e2
