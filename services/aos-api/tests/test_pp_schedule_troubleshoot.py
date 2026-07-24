"""
W5 — 调度故障排查
Tests: ScheduleTroubleshootEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_schedule_troubleshoot import ScheduleTroubleshoot, ScheduleTroubleshootEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ScheduleTroubleshootEngine().reset()
    yield
    ScheduleTroubleshootEngine().reset()


class TestScheduleTroubleshootEngine:
    def test_register(self):
        item = ScheduleTroubleshoot(name="test-item")
        result = ScheduleTroubleshootEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ScheduleTroubleshoot(name="get-test")
        ScheduleTroubleshootEngine().register(item)
        found = ScheduleTroubleshootEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ScheduleTroubleshootEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ScheduleTroubleshootEngine().register(ScheduleTroubleshoot(name=f"list-{i}"))
        items = ScheduleTroubleshootEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ScheduleTroubleshoot(name="original")
        ScheduleTroubleshootEngine().register(item)
        updated = ScheduleTroubleshootEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ScheduleTroubleshootEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ScheduleTroubleshoot(name="delete-me")
        ScheduleTroubleshootEngine().register(item)
        assert ScheduleTroubleshootEngine().delete(item.id) is True
        assert ScheduleTroubleshootEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ScheduleTroubleshootEngine().register(ScheduleTroubleshoot(name=f"cap-{i}"))
        assert len(ScheduleTroubleshootEngine().list()) == 100

    def test_singleton(self):
        e1 = ScheduleTroubleshootEngine()
        e2 = ScheduleTroubleshootEngine()
        assert e1 is e2
