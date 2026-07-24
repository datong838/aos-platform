"""
W6 — 错误数据帧
Tests: ErrorDataframeEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_error_dataframe import ErrorDataframe, ErrorDataframeEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ErrorDataframeEngine().reset()
    yield
    ErrorDataframeEngine().reset()


class TestErrorDataframeEngine:
    def test_register(self):
        item = ErrorDataframe(name="test-item")
        result = ErrorDataframeEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ErrorDataframe(name="get-test")
        ErrorDataframeEngine().register(item)
        found = ErrorDataframeEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ErrorDataframeEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ErrorDataframeEngine().register(ErrorDataframe(name=f"list-{i}"))
        items = ErrorDataframeEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ErrorDataframe(name="original")
        ErrorDataframeEngine().register(item)
        updated = ErrorDataframeEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ErrorDataframeEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ErrorDataframe(name="delete-me")
        ErrorDataframeEngine().register(item)
        assert ErrorDataframeEngine().delete(item.id) is True
        assert ErrorDataframeEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ErrorDataframeEngine().register(ErrorDataframe(name=f"cap-{i}"))
        assert len(ErrorDataframeEngine().list()) == 100

    def test_singleton(self):
        e1 = ErrorDataframeEngine()
        e2 = ErrorDataframeEngine()
        assert e1 is e2
