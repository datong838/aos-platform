"""
W5 — 主键设置
Tests: PrimaryKeyConfigEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_primary_key import PrimaryKeyConfig, PrimaryKeyConfigEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    PrimaryKeyConfigEngine().reset()
    yield
    PrimaryKeyConfigEngine().reset()


class TestPrimaryKeyConfigEngine:
    def test_register(self):
        item = PrimaryKeyConfig(name="test-item")
        result = PrimaryKeyConfigEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = PrimaryKeyConfig(name="get-test")
        PrimaryKeyConfigEngine().register(item)
        found = PrimaryKeyConfigEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert PrimaryKeyConfigEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            PrimaryKeyConfigEngine().register(PrimaryKeyConfig(name=f"list-{i}"))
        items = PrimaryKeyConfigEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = PrimaryKeyConfig(name="original")
        PrimaryKeyConfigEngine().register(item)
        updated = PrimaryKeyConfigEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert PrimaryKeyConfigEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = PrimaryKeyConfig(name="delete-me")
        PrimaryKeyConfigEngine().register(item)
        assert PrimaryKeyConfigEngine().delete(item.id) is True
        assert PrimaryKeyConfigEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            PrimaryKeyConfigEngine().register(PrimaryKeyConfig(name=f"cap-{i}"))
        assert len(PrimaryKeyConfigEngine().list()) == 100

    def test_singleton(self):
        e1 = PrimaryKeyConfigEngine()
        e2 = PrimaryKeyConfigEngine()
        assert e1 is e2
