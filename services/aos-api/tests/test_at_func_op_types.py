"""
W5 — 函数支持的操作类型
Tests: FuncOpTypesEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.at_func_op_types import FuncOpTypes, FuncOpTypesEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    FuncOpTypesEngine().reset()
    yield
    FuncOpTypesEngine().reset()


class TestFuncOpTypesEngine:
    def test_register(self):
        item = FuncOpTypes(name="test-item")
        result = FuncOpTypesEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = FuncOpTypes(name="get-test")
        FuncOpTypesEngine().register(item)
        found = FuncOpTypesEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert FuncOpTypesEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            FuncOpTypesEngine().register(FuncOpTypes(name=f"list-{i}"))
        items = FuncOpTypesEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = FuncOpTypes(name="original")
        FuncOpTypesEngine().register(item)
        updated = FuncOpTypesEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert FuncOpTypesEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = FuncOpTypes(name="delete-me")
        FuncOpTypesEngine().register(item)
        assert FuncOpTypesEngine().delete(item.id) is True
        assert FuncOpTypesEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            FuncOpTypesEngine().register(FuncOpTypes(name=f"cap-{i}"))
        assert len(FuncOpTypesEngine().list()) == 100

    def test_singleton(self):
        e1 = FuncOpTypesEngine()
        e2 = FuncOpTypesEngine()
        assert e1 is e2
