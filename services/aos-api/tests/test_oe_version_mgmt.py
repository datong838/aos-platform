"""
W5 — 版本管理
Tests: VersionMgmtEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oe_version_mgmt import VersionMgmt, VersionMgmtEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    VersionMgmtEngine().reset()
    yield
    VersionMgmtEngine().reset()


class TestVersionMgmtEngine:
    def test_register(self):
        item = VersionMgmt(name="test-item")
        result = VersionMgmtEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = VersionMgmt(name="get-test")
        VersionMgmtEngine().register(item)
        found = VersionMgmtEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert VersionMgmtEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            VersionMgmtEngine().register(VersionMgmt(name=f"list-{i}"))
        items = VersionMgmtEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = VersionMgmt(name="original")
        VersionMgmtEngine().register(item)
        updated = VersionMgmtEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert VersionMgmtEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = VersionMgmt(name="delete-me")
        VersionMgmtEngine().register(item)
        assert VersionMgmtEngine().delete(item.id) is True
        assert VersionMgmtEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            VersionMgmtEngine().register(VersionMgmt(name=f"cap-{i}"))
        assert len(VersionMgmtEngine().list()) == 100

    def test_singleton(self):
        e1 = VersionMgmtEngine()
        e2 = VersionMgmtEngine()
        assert e1 is e2
