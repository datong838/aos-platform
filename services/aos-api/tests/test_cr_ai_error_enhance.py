"""
W5 — AI 错误增强器
Tests: AiErrorEnhanceEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_ai_error_enhance import AiErrorEnhance, AiErrorEnhanceEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    AiErrorEnhanceEngine().reset()
    yield
    AiErrorEnhanceEngine().reset()


class TestAiErrorEnhanceEngine:
    def test_register(self):
        item = AiErrorEnhance(name="test-item")
        result = AiErrorEnhanceEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = AiErrorEnhance(name="get-test")
        AiErrorEnhanceEngine().register(item)
        found = AiErrorEnhanceEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert AiErrorEnhanceEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            AiErrorEnhanceEngine().register(AiErrorEnhance(name=f"list-{i}"))
        items = AiErrorEnhanceEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = AiErrorEnhance(name="original")
        AiErrorEnhanceEngine().register(item)
        updated = AiErrorEnhanceEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert AiErrorEnhanceEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = AiErrorEnhance(name="delete-me")
        AiErrorEnhanceEngine().register(item)
        assert AiErrorEnhanceEngine().delete(item.id) is True
        assert AiErrorEnhanceEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            AiErrorEnhanceEngine().register(AiErrorEnhance(name=f"cap-{i}"))
        assert len(AiErrorEnhanceEngine().list()) == 100

    def test_singleton(self):
        e1 = AiErrorEnhanceEngine()
        e2 = AiErrorEnhanceEngine()
        assert e1 is e2
