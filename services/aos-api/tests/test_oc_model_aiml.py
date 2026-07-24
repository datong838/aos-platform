"""
W5 — 模型 AI/ML 集成
Tests: ModelAiMlEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oc_model_aiml import ModelAiMl, ModelAiMlEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ModelAiMlEngine().reset()
    yield
    ModelAiMlEngine().reset()


class TestModelAiMlEngine:
    def test_register(self):
        item = ModelAiMl(name="test-item")
        result = ModelAiMlEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ModelAiMl(name="get-test")
        ModelAiMlEngine().register(item)
        found = ModelAiMlEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ModelAiMlEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ModelAiMlEngine().register(ModelAiMl(name=f"list-{i}"))
        items = ModelAiMlEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ModelAiMl(name="original")
        ModelAiMlEngine().register(item)
        updated = ModelAiMlEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ModelAiMlEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ModelAiMl(name="delete-me")
        ModelAiMlEngine().register(item)
        assert ModelAiMlEngine().delete(item.id) is True
        assert ModelAiMlEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ModelAiMlEngine().register(ModelAiMl(name=f"cap-{i}"))
        assert len(ModelAiMlEngine().list()) == 100

    def test_singleton(self):
        e1 = ModelAiMlEngine()
        e2 = ModelAiMlEngine()
        assert e1 is e2
