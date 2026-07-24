"""
W6 — 告警
Tests: CpAlertEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cp_alert import CpAlert, CpAlertEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    CpAlertEngine().reset()
    yield
    CpAlertEngine().reset()


class TestCpAlertEngine:
    def test_register(self):
        item = CpAlert(name="test-item")
        result = CpAlertEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = CpAlert(name="get-test")
        CpAlertEngine().register(item)
        found = CpAlertEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert CpAlertEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            CpAlertEngine().register(CpAlert(name=f"list-{i}"))
        items = CpAlertEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = CpAlert(name="original")
        CpAlertEngine().register(item)
        updated = CpAlertEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert CpAlertEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = CpAlert(name="delete-me")
        CpAlertEngine().register(item)
        assert CpAlertEngine().delete(item.id) is True
        assert CpAlertEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            CpAlertEngine().register(CpAlert(name=f"cap-{i}"))
        assert len(CpAlertEngine().list()) == 100

    def test_singleton(self):
        e1 = CpAlertEngine()
        e2 = CpAlertEngine()
        assert e1 is e2
