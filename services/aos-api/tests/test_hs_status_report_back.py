"""
W6 — 状态回传
Tests: StatusReportBackEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.hs_status_report_back import StatusReportBack, StatusReportBackEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    StatusReportBackEngine().reset()
    yield
    StatusReportBackEngine().reset()


class TestStatusReportBackEngine:
    def test_register(self):
        item = StatusReportBack(name="test-item")
        result = StatusReportBackEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = StatusReportBack(name="get-test")
        StatusReportBackEngine().register(item)
        found = StatusReportBackEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert StatusReportBackEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            StatusReportBackEngine().register(StatusReportBack(name=f"list-{i}"))
        items = StatusReportBackEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = StatusReportBack(name="original")
        StatusReportBackEngine().register(item)
        updated = StatusReportBackEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert StatusReportBackEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = StatusReportBack(name="delete-me")
        StatusReportBackEngine().register(item)
        assert StatusReportBackEngine().delete(item.id) is True
        assert StatusReportBackEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            StatusReportBackEngine().register(StatusReportBack(name=f"cap-{i}"))
        assert len(StatusReportBackEngine().list()) == 100

    def test_singleton(self):
        e1 = StatusReportBackEngine()
        e2 = StatusReportBackEngine()
        assert e1 is e2
