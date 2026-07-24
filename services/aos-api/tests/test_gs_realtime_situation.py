"""
W6 — 实时态势监控
Tests: RealtimeSituationEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.gs_realtime_situation import RealtimeSituation, RealtimeSituationEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    RealtimeSituationEngine().reset()
    yield
    RealtimeSituationEngine().reset()


class TestRealtimeSituationEngine:
    def test_register(self):
        item = RealtimeSituation(name="test-item")
        result = RealtimeSituationEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = RealtimeSituation(name="get-test")
        RealtimeSituationEngine().register(item)
        found = RealtimeSituationEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert RealtimeSituationEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            RealtimeSituationEngine().register(RealtimeSituation(name=f"list-{i}"))
        items = RealtimeSituationEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = RealtimeSituation(name="original")
        RealtimeSituationEngine().register(item)
        updated = RealtimeSituationEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert RealtimeSituationEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = RealtimeSituation(name="delete-me")
        RealtimeSituationEngine().register(item)
        assert RealtimeSituationEngine().delete(item.id) is True
        assert RealtimeSituationEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            RealtimeSituationEngine().register(RealtimeSituation(name=f"cap-{i}"))
        assert len(RealtimeSituationEngine().list()) == 100

    def test_singleton(self):
        e1 = RealtimeSituationEngine()
        e2 = RealtimeSituationEngine()
        assert e1 is e2
