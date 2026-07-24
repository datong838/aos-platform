"""
W5 — 渲染提示
Tests: RenderHintEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oe_render_hint import RenderHint, RenderHintEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    RenderHintEngine().reset()
    yield
    RenderHintEngine().reset()


class TestRenderHintEngine:
    def test_register(self):
        item = RenderHint(name="test-item")
        result = RenderHintEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = RenderHint(name="get-test")
        RenderHintEngine().register(item)
        found = RenderHintEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert RenderHintEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            RenderHintEngine().register(RenderHint(name=f"list-{i}"))
        items = RenderHintEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = RenderHint(name="original")
        RenderHintEngine().register(item)
        updated = RenderHintEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert RenderHintEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = RenderHint(name="delete-me")
        RenderHintEngine().register(item)
        assert RenderHintEngine().delete(item.id) is True
        assert RenderHintEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            RenderHintEngine().register(RenderHint(name=f"cap-{i}"))
        assert len(RenderHintEngine().list()) == 100

    def test_singleton(self):
        e1 = RenderHintEngine()
        e2 = RenderHintEngine()
        assert e1 is e2
