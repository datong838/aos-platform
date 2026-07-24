"""
W5 — 编辑计数警告
Tests: EditCountWarnEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.at_edit_count_warn import EditCountWarn, EditCountWarnEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    EditCountWarnEngine().reset()
    yield
    EditCountWarnEngine().reset()


class TestEditCountWarnEngine:
    def test_register(self):
        item = EditCountWarn(name="test-item")
        result = EditCountWarnEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = EditCountWarn(name="get-test")
        EditCountWarnEngine().register(item)
        found = EditCountWarnEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert EditCountWarnEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            EditCountWarnEngine().register(EditCountWarn(name=f"list-{i}"))
        items = EditCountWarnEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = EditCountWarn(name="original")
        EditCountWarnEngine().register(item)
        updated = EditCountWarnEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert EditCountWarnEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = EditCountWarn(name="delete-me")
        EditCountWarnEngine().register(item)
        assert EditCountWarnEngine().delete(item.id) is True
        assert EditCountWarnEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            EditCountWarnEngine().register(EditCountWarn(name=f"cap-{i}"))
        assert len(EditCountWarnEngine().list()) == 100

    def test_singleton(self):
        e1 = EditCountWarnEngine()
        e2 = EditCountWarnEngine()
        assert e1 is e2
