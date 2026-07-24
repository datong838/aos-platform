"""
W6 — 变换仓库
Tests: TransformRepoEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_transform_repo import TransformRepo, TransformRepoEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    TransformRepoEngine().reset()
    yield
    TransformRepoEngine().reset()


class TestTransformRepoEngine:
    def test_register(self):
        item = TransformRepo(name="test-item")
        result = TransformRepoEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = TransformRepo(name="get-test")
        TransformRepoEngine().register(item)
        found = TransformRepoEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert TransformRepoEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            TransformRepoEngine().register(TransformRepo(name=f"list-{i}"))
        items = TransformRepoEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = TransformRepo(name="original")
        TransformRepoEngine().register(item)
        updated = TransformRepoEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert TransformRepoEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = TransformRepo(name="delete-me")
        TransformRepoEngine().register(item)
        assert TransformRepoEngine().delete(item.id) is True
        assert TransformRepoEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            TransformRepoEngine().register(TransformRepo(name=f"cap-{i}"))
        assert len(TransformRepoEngine().list()) == 100

    def test_singleton(self):
        e1 = TransformRepoEngine()
        e2 = TransformRepoEngine()
        assert e1 is e2
