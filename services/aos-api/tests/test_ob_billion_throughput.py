"""
W5 — 数十亿级吞吐量
Tests: BillionThroughputEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ob_billion_throughput import BillionThroughput, BillionThroughputEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    BillionThroughputEngine().reset()
    yield
    BillionThroughputEngine().reset()


class TestBillionThroughputEngine:
    def test_register(self):
        item = BillionThroughput(name="test-item")
        result = BillionThroughputEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = BillionThroughput(name="get-test")
        BillionThroughputEngine().register(item)
        found = BillionThroughputEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert BillionThroughputEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            BillionThroughputEngine().register(BillionThroughput(name=f"list-{i}"))
        items = BillionThroughputEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = BillionThroughput(name="original")
        BillionThroughputEngine().register(item)
        updated = BillionThroughputEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert BillionThroughputEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = BillionThroughput(name="delete-me")
        BillionThroughputEngine().register(item)
        assert BillionThroughputEngine().delete(item.id) is True
        assert BillionThroughputEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            BillionThroughputEngine().register(BillionThroughput(name=f"cap-{i}"))
        assert len(BillionThroughputEngine().list()) == 100

    def test_singleton(self):
        e1 = BillionThroughputEngine()
        e2 = BillionThroughputEngine()
        assert e1 is e2
