"""
W6 — SAP 批量导入
Tests: SapBatchImportEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.es_sap_batch_import import SapBatchImport, SapBatchImportEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    SapBatchImportEngine().reset()
    yield
    SapBatchImportEngine().reset()


class TestSapBatchImportEngine:
    def test_register(self):
        item = SapBatchImport(name="test-item")
        result = SapBatchImportEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = SapBatchImport(name="get-test")
        SapBatchImportEngine().register(item)
        found = SapBatchImportEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert SapBatchImportEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            SapBatchImportEngine().register(SapBatchImport(name=f"list-{i}"))
        items = SapBatchImportEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = SapBatchImport(name="original")
        SapBatchImportEngine().register(item)
        updated = SapBatchImportEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert SapBatchImportEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = SapBatchImport(name="delete-me")
        SapBatchImportEngine().register(item)
        assert SapBatchImportEngine().delete(item.id) is True
        assert SapBatchImportEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            SapBatchImportEngine().register(SapBatchImport(name=f"cap-{i}"))
        assert len(SapBatchImportEngine().list()) == 100

    def test_singleton(self):
        e1 = SapBatchImportEngine()
        e2 = SapBatchImportEngine()
        assert e1 is e2
