"""
W5 — 选择 backing datasets
Tests: BackingDatasetEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.di_backing_ds import BackingDataset, BackingDatasetEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    BackingDatasetEngine().reset()
    yield
    BackingDatasetEngine().reset()


class TestBackingDatasetEngine:
    def test_register(self):
        item = BackingDataset(name="test-item")
        result = BackingDatasetEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = BackingDataset(name="get-test")
        BackingDatasetEngine().register(item)
        found = BackingDatasetEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert BackingDatasetEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            BackingDatasetEngine().register(BackingDataset(name=f"list-{i}"))
        items = BackingDatasetEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = BackingDataset(name="original")
        BackingDatasetEngine().register(item)
        updated = BackingDatasetEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert BackingDatasetEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = BackingDataset(name="delete-me")
        BackingDatasetEngine().register(item)
        assert BackingDatasetEngine().delete(item.id) is True
        assert BackingDatasetEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            BackingDatasetEngine().register(BackingDataset(name=f"cap-{i}"))
        assert len(BackingDatasetEngine().list()) == 100

    def test_singleton(self):
        e1 = BackingDatasetEngine()
        e2 = BackingDatasetEngine()
        assert e1 is e2
