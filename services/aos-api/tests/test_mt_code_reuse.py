"""
W5 — 变换代码复用
Tests: TransformCodeReuseEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.mt_code_reuse import TransformCodeReuse, TransformCodeReuseEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    TransformCodeReuseEngine().reset()
    yield
    TransformCodeReuseEngine().reset()


class TestTransformCodeReuseEngine:
    def test_register(self):
        item = TransformCodeReuse(name="test-item")
        result = TransformCodeReuseEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = TransformCodeReuse(name="get-test")
        TransformCodeReuseEngine().register(item)
        found = TransformCodeReuseEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert TransformCodeReuseEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            TransformCodeReuseEngine().register(TransformCodeReuse(name=f"list-{i}"))
        items = TransformCodeReuseEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = TransformCodeReuse(name="original")
        TransformCodeReuseEngine().register(item)
        updated = TransformCodeReuseEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert TransformCodeReuseEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = TransformCodeReuse(name="delete-me")
        TransformCodeReuseEngine().register(item)
        assert TransformCodeReuseEngine().delete(item.id) is True
        assert TransformCodeReuseEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            TransformCodeReuseEngine().register(TransformCodeReuse(name=f"cap-{i}"))
        assert len(TransformCodeReuseEngine().list()) == 100

    def test_singleton(self):
        e1 = TransformCodeReuseEngine()
        e2 = TransformCodeReuseEngine()
        assert e1 is e2
