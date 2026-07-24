"""
W5 — 元数据状态体系
Tests: MetadataStateEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oe_metadata_state import MetadataState, MetadataStateEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    MetadataStateEngine().reset()
    yield
    MetadataStateEngine().reset()


class TestMetadataStateEngine:
    def test_register(self):
        item = MetadataState(name="test-item")
        result = MetadataStateEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = MetadataState(name="get-test")
        MetadataStateEngine().register(item)
        found = MetadataStateEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert MetadataStateEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            MetadataStateEngine().register(MetadataState(name=f"list-{i}"))
        items = MetadataStateEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = MetadataState(name="original")
        MetadataStateEngine().register(item)
        updated = MetadataStateEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert MetadataStateEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = MetadataState(name="delete-me")
        MetadataStateEngine().register(item)
        assert MetadataStateEngine().delete(item.id) is True
        assert MetadataStateEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            MetadataStateEngine().register(MetadataState(name=f"cap-{i}"))
        assert len(MetadataStateEngine().list()) == 100

    def test_singleton(self):
        e1 = MetadataStateEngine()
        e2 = MetadataStateEngine()
        assert e1 is e2
