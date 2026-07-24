"""
W6 — R 变换
Tests: RTransformEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.mt_r_transform import RTransform, RTransformEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    RTransformEngine().reset()
    yield
    RTransformEngine().reset()


class TestRTransformEngine:
    def test_register(self):
        item = RTransform(name="test-item")
        result = RTransformEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = RTransform(name="get-test")
        RTransformEngine().register(item)
        found = RTransformEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert RTransformEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            RTransformEngine().register(RTransform(name=f"list-{i}"))
        items = RTransformEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = RTransform(name="original")
        RTransformEngine().register(item)
        updated = RTransformEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert RTransformEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = RTransform(name="delete-me")
        RTransformEngine().register(item)
        assert RTransformEngine().delete(item.id) is True
        assert RTransformEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            RTransformEngine().register(RTransform(name=f"cap-{i}"))
        assert len(RTransformEngine().list()) == 100

    def test_singleton(self):
        e1 = RTransformEngine()
        e2 = RTransformEngine()
        assert e1 is e2
