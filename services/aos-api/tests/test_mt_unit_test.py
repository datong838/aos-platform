"""
W6 — 单元测试
Tests: MtUnitTestEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.mt_unit_test import MtUnitTest, MtUnitTestEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    MtUnitTestEngine().reset()
    yield
    MtUnitTestEngine().reset()


class TestMtUnitTestEngine:
    def test_register(self):
        item = MtUnitTest(name="test-item")
        result = MtUnitTestEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = MtUnitTest(name="get-test")
        MtUnitTestEngine().register(item)
        found = MtUnitTestEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert MtUnitTestEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            MtUnitTestEngine().register(MtUnitTest(name=f"list-{i}"))
        items = MtUnitTestEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = MtUnitTest(name="original")
        MtUnitTestEngine().register(item)
        updated = MtUnitTestEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert MtUnitTestEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = MtUnitTest(name="delete-me")
        MtUnitTestEngine().register(item)
        assert MtUnitTestEngine().delete(item.id) is True
        assert MtUnitTestEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            MtUnitTestEngine().register(MtUnitTest(name=f"cap-{i}"))
        assert len(MtUnitTestEngine().list()) == 100

    def test_singleton(self):
        e1 = MtUnitTestEngine()
        e2 = MtUnitTestEngine()
        assert e1 is e2
