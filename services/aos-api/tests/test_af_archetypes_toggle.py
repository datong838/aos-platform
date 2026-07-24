"""
W5 — Archetypes 切换
Tests: AfArchetypesToggleEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.af_archetypes_toggle import AfArchetypesToggle, AfArchetypesToggleEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    AfArchetypesToggleEngine().reset()
    yield
    AfArchetypesToggleEngine().reset()


class TestAfArchetypesToggleEngine:
    def test_register(self):
        item = AfArchetypesToggle(name="test-item")
        result = AfArchetypesToggleEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = AfArchetypesToggle(name="get-test")
        AfArchetypesToggleEngine().register(item)
        found = AfArchetypesToggleEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert AfArchetypesToggleEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            AfArchetypesToggleEngine().register(AfArchetypesToggle(name=f"list-{i}"))
        items = AfArchetypesToggleEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = AfArchetypesToggle(name="original")
        AfArchetypesToggleEngine().register(item)
        updated = AfArchetypesToggleEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert AfArchetypesToggleEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = AfArchetypesToggle(name="delete-me")
        AfArchetypesToggleEngine().register(item)
        assert AfArchetypesToggleEngine().delete(item.id) is True
        assert AfArchetypesToggleEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            AfArchetypesToggleEngine().register(AfArchetypesToggle(name=f"cap-{i}"))
        assert len(AfArchetypesToggleEngine().list()) == 100

    def test_singleton(self):
        e1 = AfArchetypesToggleEngine()
        e2 = AfArchetypesToggleEngine()
        assert e1 is e2
