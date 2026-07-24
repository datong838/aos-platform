"""
W5 — 历史详情
Tests: HistoryDetailEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.dl_history_detail import HistoryDetail, HistoryDetailEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    HistoryDetailEngine().reset()
    yield
    HistoryDetailEngine().reset()


class TestHistoryDetailEngine:
    def test_register(self):
        item = HistoryDetail(name="test-item")
        result = HistoryDetailEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = HistoryDetail(name="get-test")
        HistoryDetailEngine().register(item)
        found = HistoryDetailEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert HistoryDetailEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            HistoryDetailEngine().register(HistoryDetail(name=f"list-{i}"))
        items = HistoryDetailEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = HistoryDetail(name="original")
        HistoryDetailEngine().register(item)
        updated = HistoryDetailEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert HistoryDetailEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = HistoryDetail(name="delete-me")
        HistoryDetailEngine().register(item)
        assert HistoryDetailEngine().delete(item.id) is True
        assert HistoryDetailEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            HistoryDetailEngine().register(HistoryDetail(name=f"cap-{i}"))
        assert len(HistoryDetailEngine().list()) == 100

    def test_singleton(self):
        e1 = HistoryDetailEngine()
        e2 = HistoryDetailEngine()
        assert e1 is e2
