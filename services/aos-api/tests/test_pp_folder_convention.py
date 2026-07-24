"""
W5 — 文件夹规范
Tests: FolderConventionEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_folder_convention import FolderConvention, FolderConventionEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    FolderConventionEngine().reset()
    yield
    FolderConventionEngine().reset()


class TestFolderConventionEngine:
    def test_register(self):
        item = FolderConvention(name="test-item")
        result = FolderConventionEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = FolderConvention(name="get-test")
        FolderConventionEngine().register(item)
        found = FolderConventionEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert FolderConventionEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            FolderConventionEngine().register(FolderConvention(name=f"list-{i}"))
        items = FolderConventionEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = FolderConvention(name="original")
        FolderConventionEngine().register(item)
        updated = FolderConventionEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert FolderConventionEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = FolderConvention(name="delete-me")
        FolderConventionEngine().register(item)
        assert FolderConventionEngine().delete(item.id) is True
        assert FolderConventionEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            FolderConventionEngine().register(FolderConvention(name=f"cap-{i}"))
        assert len(FolderConventionEngine().list()) == 100

    def test_singleton(self):
        e1 = FolderConventionEngine()
        e2 = FolderConventionEngine()
        assert e1 is e2
