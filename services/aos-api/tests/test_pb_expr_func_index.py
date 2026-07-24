"""
W6 — 表达式函数索引
Tests: ExprFuncIndexEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pb_expr_func_index import ExprFuncIndex, ExprFuncIndexEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ExprFuncIndexEngine().reset()
    yield
    ExprFuncIndexEngine().reset()


class TestExprFuncIndexEngine:
    def test_register(self):
        item = ExprFuncIndex(name="test-item")
        result = ExprFuncIndexEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ExprFuncIndex(name="get-test")
        ExprFuncIndexEngine().register(item)
        found = ExprFuncIndexEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ExprFuncIndexEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ExprFuncIndexEngine().register(ExprFuncIndex(name=f"list-{i}"))
        items = ExprFuncIndexEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ExprFuncIndex(name="original")
        ExprFuncIndexEngine().register(item)
        updated = ExprFuncIndexEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ExprFuncIndexEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ExprFuncIndex(name="delete-me")
        ExprFuncIndexEngine().register(item)
        assert ExprFuncIndexEngine().delete(item.id) is True
        assert ExprFuncIndexEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ExprFuncIndexEngine().register(ExprFuncIndex(name=f"cap-{i}"))
        assert len(ExprFuncIndexEngine().list()) == 100

    def test_singleton(self):
        e1 = ExprFuncIndexEngine()
        e2 = ExprFuncIndexEngine()
        assert e1 is e2
