"""
W5 — 实时评估
Tests: RealtimeEvalEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ob_realtime_eval import RealtimeEval, RealtimeEvalEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    RealtimeEvalEngine().reset()
    yield
    RealtimeEvalEngine().reset()


class TestRealtimeEvalEngine:
    def test_register(self):
        item = RealtimeEval(name="test-item")
        result = RealtimeEvalEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = RealtimeEval(name="get-test")
        RealtimeEvalEngine().register(item)
        found = RealtimeEvalEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert RealtimeEvalEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            RealtimeEvalEngine().register(RealtimeEval(name=f"list-{i}"))
        items = RealtimeEvalEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = RealtimeEval(name="original")
        RealtimeEvalEngine().register(item)
        updated = RealtimeEvalEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert RealtimeEvalEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = RealtimeEval(name="delete-me")
        RealtimeEvalEngine().register(item)
        assert RealtimeEvalEngine().delete(item.id) is True
        assert RealtimeEvalEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            RealtimeEvalEngine().register(RealtimeEval(name=f"cap-{i}"))
        assert len(RealtimeEvalEngine().list()) == 100

    def test_singleton(self):
        e1 = RealtimeEvalEngine()
        e2 = RealtimeEvalEngine()
        assert e1 is e2
