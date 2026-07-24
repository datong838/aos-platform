"""
W6 — Python @transform_df 装饰器
Tests: PythonTransformDfEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.mt_python_transform_df import PythonTransformDf, PythonTransformDfEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    PythonTransformDfEngine().reset()
    yield
    PythonTransformDfEngine().reset()


class TestPythonTransformDfEngine:
    def test_register(self):
        item = PythonTransformDf(name="test-item")
        result = PythonTransformDfEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = PythonTransformDf(name="get-test")
        PythonTransformDfEngine().register(item)
        found = PythonTransformDfEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert PythonTransformDfEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            PythonTransformDfEngine().register(PythonTransformDf(name=f"list-{i}"))
        items = PythonTransformDfEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = PythonTransformDf(name="original")
        PythonTransformDfEngine().register(item)
        updated = PythonTransformDfEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert PythonTransformDfEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = PythonTransformDf(name="delete-me")
        PythonTransformDfEngine().register(item)
        assert PythonTransformDfEngine().delete(item.id) is True
        assert PythonTransformDfEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            PythonTransformDfEngine().register(PythonTransformDf(name=f"cap-{i}"))
        assert len(PythonTransformDfEngine().list()) == 100

    def test_singleton(self):
        e1 = PythonTransformDfEngine()
        e2 = PythonTransformDfEngine()
        assert e1 is e2
