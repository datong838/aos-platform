"""
W5 — Archetypes 切换
Tests: AtArchetypesToggleEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.at_archetypes_toggle import AtArchetypesToggle, AtArchetypesToggleEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    AtArchetypesToggleEngine().reset()
    yield
    AtArchetypesToggleEngine().reset()


class TestAtArchetypesToggleEngine:
    def test_register(self):
        item = AtArchetypesToggle(name="test-item")
        result = AtArchetypesToggleEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = AtArchetypesToggle(name="get-test")
        AtArchetypesToggleEngine().register(item)
        found = AtArchetypesToggleEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert AtArchetypesToggleEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            AtArchetypesToggleEngine().register(AtArchetypesToggle(name=f"list-{i}"))
        items = AtArchetypesToggleEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = AtArchetypesToggle(name="original")
        AtArchetypesToggleEngine().register(item)
        updated = AtArchetypesToggleEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert AtArchetypesToggleEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = AtArchetypesToggle(name="delete-me")
        AtArchetypesToggleEngine().register(item)
        assert AtArchetypesToggleEngine().delete(item.id) is True
        assert AtArchetypesToggleEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            AtArchetypesToggleEngine().register(AtArchetypesToggle(name=f"cap-{i}"))
        assert len(AtArchetypesToggleEngine().list()) == 100

    def test_singleton(self):
        e1 = AtArchetypesToggleEngine()
        e2 = AtArchetypesToggleEngine()
        assert e1 is e2
