"""
W5 — 数据集别名
Tests: DatasetAliasEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_dataset_alias import DatasetAlias, DatasetAliasEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    DatasetAliasEngine().reset()
    yield
    DatasetAliasEngine().reset()


class TestDatasetAliasEngine:
    def test_register(self):
        item = DatasetAlias(name="test-item")
        result = DatasetAliasEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = DatasetAlias(name="get-test")
        DatasetAliasEngine().register(item)
        found = DatasetAliasEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert DatasetAliasEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            DatasetAliasEngine().register(DatasetAlias(name=f"list-{i}"))
        items = DatasetAliasEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = DatasetAlias(name="original")
        DatasetAliasEngine().register(item)
        updated = DatasetAliasEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert DatasetAliasEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = DatasetAlias(name="delete-me")
        DatasetAliasEngine().register(item)
        assert DatasetAliasEngine().delete(item.id) is True
        assert DatasetAliasEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            DatasetAliasEngine().register(DatasetAlias(name=f"cap-{i}"))
        assert len(DatasetAliasEngine().list()) == 100

    def test_singleton(self):
        e1 = DatasetAliasEngine()
        e2 = DatasetAliasEngine()
        assert e1 is e2
