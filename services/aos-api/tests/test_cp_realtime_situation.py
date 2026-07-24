"""
W6 — 实时态势
Tests: CpRealtimeSituationEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cp_realtime_situation import CpRealtimeSituation, CpRealtimeSituationEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    CpRealtimeSituationEngine().reset()
    yield
    CpRealtimeSituationEngine().reset()


class TestCpRealtimeSituationEngine:
    def test_register(self):
        item = CpRealtimeSituation(name="test-item")
        result = CpRealtimeSituationEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = CpRealtimeSituation(name="get-test")
        CpRealtimeSituationEngine().register(item)
        found = CpRealtimeSituationEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert CpRealtimeSituationEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            CpRealtimeSituationEngine().register(CpRealtimeSituation(name=f"list-{i}"))
        items = CpRealtimeSituationEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = CpRealtimeSituation(name="original")
        CpRealtimeSituationEngine().register(item)
        updated = CpRealtimeSituationEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert CpRealtimeSituationEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = CpRealtimeSituation(name="delete-me")
        CpRealtimeSituationEngine().register(item)
        assert CpRealtimeSituationEngine().delete(item.id) is True
        assert CpRealtimeSituationEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            CpRealtimeSituationEngine().register(CpRealtimeSituation(name=f"cap-{i}"))
        assert len(CpRealtimeSituationEngine().list()) == 100

    def test_singleton(self):
        e1 = CpRealtimeSituationEngine()
        e2 = CpRealtimeSituationEngine()
        assert e1 is e2
