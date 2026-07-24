"""
W5 — 共享移动重命名
Tests: ShareMoveRenameEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ds_share_move_rename import ShareMoveRename, ShareMoveRenameEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ShareMoveRenameEngine().reset()
    yield
    ShareMoveRenameEngine().reset()


class TestShareMoveRenameEngine:
    def test_register(self):
        item = ShareMoveRename(name="test-item")
        result = ShareMoveRenameEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ShareMoveRename(name="get-test")
        ShareMoveRenameEngine().register(item)
        found = ShareMoveRenameEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ShareMoveRenameEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ShareMoveRenameEngine().register(ShareMoveRename(name=f"list-{i}"))
        items = ShareMoveRenameEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ShareMoveRename(name="original")
        ShareMoveRenameEngine().register(item)
        updated = ShareMoveRenameEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ShareMoveRenameEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ShareMoveRename(name="delete-me")
        ShareMoveRenameEngine().register(item)
        assert ShareMoveRenameEngine().delete(item.id) is True
        assert ShareMoveRenameEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ShareMoveRenameEngine().register(ShareMoveRename(name=f"cap-{i}"))
        assert len(ShareMoveRenameEngine().list()) == 100

    def test_singleton(self):
        e1 = ShareMoveRenameEngine()
        e2 = ShareMoveRenameEngine()
        assert e1 is e2
