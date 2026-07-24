"""
W5 — 同名更新追加逻辑
Tests: SameNameLogicEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ds_same_name_logic import SameNameLogic, SameNameLogicEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    SameNameLogicEngine().reset()
    yield
    SameNameLogicEngine().reset()


class TestSameNameLogicEngine:
    def test_register(self):
        item = SameNameLogic(name="test-item")
        result = SameNameLogicEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = SameNameLogic(name="get-test")
        SameNameLogicEngine().register(item)
        found = SameNameLogicEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert SameNameLogicEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            SameNameLogicEngine().register(SameNameLogic(name=f"list-{i}"))
        items = SameNameLogicEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = SameNameLogic(name="original")
        SameNameLogicEngine().register(item)
        updated = SameNameLogicEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert SameNameLogicEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = SameNameLogic(name="delete-me")
        SameNameLogicEngine().register(item)
        assert SameNameLogicEngine().delete(item.id) is True
        assert SameNameLogicEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            SameNameLogicEngine().register(SameNameLogic(name=f"cap-{i}"))
        assert len(SameNameLogicEngine().list()) == 100

    def test_singleton(self):
        e1 = SameNameLogicEngine()
        e2 = SameNameLogicEngine()
        assert e1 is e2
