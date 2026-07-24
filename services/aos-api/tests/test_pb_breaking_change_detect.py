"""
W5 — 重大更改检测
Tests: BreakingChangeDetectEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pb_breaking_change_detect import BreakingChangeDetect, BreakingChangeDetectEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    BreakingChangeDetectEngine().reset()
    yield
    BreakingChangeDetectEngine().reset()


class TestBreakingChangeDetectEngine:
    def test_register(self):
        item = BreakingChangeDetect(name="test-item")
        result = BreakingChangeDetectEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = BreakingChangeDetect(name="get-test")
        BreakingChangeDetectEngine().register(item)
        found = BreakingChangeDetectEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert BreakingChangeDetectEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            BreakingChangeDetectEngine().register(BreakingChangeDetect(name=f"list-{i}"))
        items = BreakingChangeDetectEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = BreakingChangeDetect(name="original")
        BreakingChangeDetectEngine().register(item)
        updated = BreakingChangeDetectEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert BreakingChangeDetectEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = BreakingChangeDetect(name="delete-me")
        BreakingChangeDetectEngine().register(item)
        assert BreakingChangeDetectEngine().delete(item.id) is True
        assert BreakingChangeDetectEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            BreakingChangeDetectEngine().register(BreakingChangeDetect(name=f"cap-{i}"))
        assert len(BreakingChangeDetectEngine().list()) == 100

    def test_singleton(self):
        e1 = BreakingChangeDetectEngine()
        e2 = BreakingChangeDetectEngine()
        assert e1 is e2
