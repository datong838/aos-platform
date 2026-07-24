"""
W5 — 批量全量重索引
Tests: BatchReindexEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ob_batch_reindex import BatchReindex, BatchReindexEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    BatchReindexEngine().reset()
    yield
    BatchReindexEngine().reset()


class TestBatchReindexEngine:
    def test_register(self):
        item = BatchReindex(name="test-item")
        result = BatchReindexEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = BatchReindex(name="get-test")
        BatchReindexEngine().register(item)
        found = BatchReindexEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert BatchReindexEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            BatchReindexEngine().register(BatchReindex(name=f"list-{i}"))
        items = BatchReindexEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = BatchReindex(name="original")
        BatchReindexEngine().register(item)
        updated = BatchReindexEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert BatchReindexEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = BatchReindex(name="delete-me")
        BatchReindexEngine().register(item)
        assert BatchReindexEngine().delete(item.id) is True
        assert BatchReindexEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            BatchReindexEngine().register(BatchReindex(name=f"cap-{i}"))
        assert len(BatchReindexEngine().list()) == 100

    def test_singleton(self):
        e1 = BatchReindexEngine()
        e2 = BatchReindexEngine()
        assert e1 is e2
