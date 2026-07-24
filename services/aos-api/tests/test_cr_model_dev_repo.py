"""
W5 — 模型开发仓库
Tests: ModelDevRepoEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_model_dev_repo import ModelDevRepo, ModelDevRepoEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ModelDevRepoEngine().reset()
    yield
    ModelDevRepoEngine().reset()


class TestModelDevRepoEngine:
    def test_register(self):
        item = ModelDevRepo(name="test-item")
        result = ModelDevRepoEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ModelDevRepo(name="get-test")
        ModelDevRepoEngine().register(item)
        found = ModelDevRepoEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ModelDevRepoEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ModelDevRepoEngine().register(ModelDevRepo(name=f"list-{i}"))
        items = ModelDevRepoEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ModelDevRepo(name="original")
        ModelDevRepoEngine().register(item)
        updated = ModelDevRepoEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ModelDevRepoEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ModelDevRepo(name="delete-me")
        ModelDevRepoEngine().register(item)
        assert ModelDevRepoEngine().delete(item.id) is True
        assert ModelDevRepoEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ModelDevRepoEngine().register(ModelDevRepo(name=f"cap-{i}"))
        assert len(ModelDevRepoEngine().list()) == 100

    def test_singleton(self):
        e1 = ModelDevRepoEngine()
        e2 = ModelDevRepoEngine()
        assert e1 is e2
