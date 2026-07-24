"""
W5 — 多类型制品支持
Tests: MultiArtifactEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_multi_artifact import MultiArtifact, MultiArtifactEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    MultiArtifactEngine().reset()
    yield
    MultiArtifactEngine().reset()


class TestMultiArtifactEngine:
    def test_register(self):
        item = MultiArtifact(name="test-item")
        result = MultiArtifactEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = MultiArtifact(name="get-test")
        MultiArtifactEngine().register(item)
        found = MultiArtifactEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert MultiArtifactEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            MultiArtifactEngine().register(MultiArtifact(name=f"list-{i}"))
        items = MultiArtifactEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = MultiArtifact(name="original")
        MultiArtifactEngine().register(item)
        updated = MultiArtifactEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert MultiArtifactEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = MultiArtifact(name="delete-me")
        MultiArtifactEngine().register(item)
        assert MultiArtifactEngine().delete(item.id) is True
        assert MultiArtifactEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            MultiArtifactEngine().register(MultiArtifact(name=f"cap-{i}"))
        assert len(MultiArtifactEngine().list()) == 100

    def test_singleton(self):
        e1 = MultiArtifactEngine()
        e2 = MultiArtifactEngine()
        assert e1 is e2
