"""
W5 — 详情子面板
Tests: DetailSubpanelEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.di_detail_subpanel import DetailSubpanel, DetailSubpanelEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    DetailSubpanelEngine().reset()
    yield
    DetailSubpanelEngine().reset()


class TestDetailSubpanelEngine:
    def test_register(self):
        item = DetailSubpanel(name="test-item")
        result = DetailSubpanelEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = DetailSubpanel(name="get-test")
        DetailSubpanelEngine().register(item)
        found = DetailSubpanelEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert DetailSubpanelEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            DetailSubpanelEngine().register(DetailSubpanel(name=f"list-{i}"))
        items = DetailSubpanelEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = DetailSubpanel(name="original")
        DetailSubpanelEngine().register(item)
        updated = DetailSubpanelEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert DetailSubpanelEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = DetailSubpanel(name="delete-me")
        DetailSubpanelEngine().register(item)
        assert DetailSubpanelEngine().delete(item.id) is True
        assert DetailSubpanelEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            DetailSubpanelEngine().register(DetailSubpanel(name=f"cap-{i}"))
        assert len(DetailSubpanelEngine().list()) == 100

    def test_singleton(self):
        e1 = DetailSubpanelEngine()
        e2 = DetailSubpanelEngine()
        assert e1 is e2
