"""
W6 — 数据期望
Tests: DataExpectationEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.mt_data_expectations import DataExpectation, DataExpectationEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    DataExpectationEngine().reset()
    yield
    DataExpectationEngine().reset()


class TestDataExpectationEngine:
    def test_register(self):
        item = DataExpectation(name="test-item")
        result = DataExpectationEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = DataExpectation(name="get-test")
        DataExpectationEngine().register(item)
        found = DataExpectationEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert DataExpectationEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            DataExpectationEngine().register(DataExpectation(name=f"list-{i}"))
        items = DataExpectationEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = DataExpectation(name="original")
        DataExpectationEngine().register(item)
        updated = DataExpectationEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert DataExpectationEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = DataExpectation(name="delete-me")
        DataExpectationEngine().register(item)
        assert DataExpectationEngine().delete(item.id) is True
        assert DataExpectationEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            DataExpectationEngine().register(DataExpectation(name=f"cap-{i}"))
        assert len(DataExpectationEngine().list()) == 100

    def test_singleton(self):
        e1 = DataExpectationEngine()
        e2 = DataExpectationEngine()
        assert e1 is e2
