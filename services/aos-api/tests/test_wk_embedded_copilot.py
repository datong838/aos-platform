"""
W6 — 嵌入式 Copilot
Tests: EmbeddedCopilotEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.wk_embedded_copilot import EmbeddedCopilot, EmbeddedCopilotEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    EmbeddedCopilotEngine().reset()
    yield
    EmbeddedCopilotEngine().reset()


class TestEmbeddedCopilotEngine:
    def test_register(self):
        item = EmbeddedCopilot(name="test-item")
        result = EmbeddedCopilotEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = EmbeddedCopilot(name="get-test")
        EmbeddedCopilotEngine().register(item)
        found = EmbeddedCopilotEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert EmbeddedCopilotEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            EmbeddedCopilotEngine().register(EmbeddedCopilot(name=f"list-{i}"))
        items = EmbeddedCopilotEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = EmbeddedCopilot(name="original")
        EmbeddedCopilotEngine().register(item)
        updated = EmbeddedCopilotEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert EmbeddedCopilotEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = EmbeddedCopilot(name="delete-me")
        EmbeddedCopilotEngine().register(item)
        assert EmbeddedCopilotEngine().delete(item.id) is True
        assert EmbeddedCopilotEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            EmbeddedCopilotEngine().register(EmbeddedCopilot(name=f"cap-{i}"))
        assert len(EmbeddedCopilotEngine().list()) == 100

    def test_singleton(self):
        e1 = EmbeddedCopilotEngine()
        e2 = EmbeddedCopilotEngine()
        assert e1 is e2
