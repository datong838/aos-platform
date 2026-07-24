"""
W6 — 多工作表多输出
Tests: MultiSheetOutputEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_multi_sheet_output import MultiSheetOutput, MultiSheetOutputEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    MultiSheetOutputEngine().reset()
    yield
    MultiSheetOutputEngine().reset()


class TestMultiSheetOutputEngine:
    def test_register(self):
        item = MultiSheetOutput(name="test-item")
        result = MultiSheetOutputEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = MultiSheetOutput(name="get-test")
        MultiSheetOutputEngine().register(item)
        found = MultiSheetOutputEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert MultiSheetOutputEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            MultiSheetOutputEngine().register(MultiSheetOutput(name=f"list-{i}"))
        items = MultiSheetOutputEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = MultiSheetOutput(name="original")
        MultiSheetOutputEngine().register(item)
        updated = MultiSheetOutputEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert MultiSheetOutputEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = MultiSheetOutput(name="delete-me")
        MultiSheetOutputEngine().register(item)
        assert MultiSheetOutputEngine().delete(item.id) is True
        assert MultiSheetOutputEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            MultiSheetOutputEngine().register(MultiSheetOutput(name=f"cap-{i}"))
        assert len(MultiSheetOutputEngine().list()) == 100

    def test_singleton(self):
        e1 = MultiSheetOutputEngine()
        e2 = MultiSheetOutputEngine()
        assert e1 is e2
