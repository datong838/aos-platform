"""
W5 — 制品库集成
Tests: ArtifactRegistryEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_artifact_registry import ArtifactRegistry, ArtifactRegistryEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ArtifactRegistryEngine().reset()
    yield
    ArtifactRegistryEngine().reset()


class TestArtifactRegistryEngine:
    def test_register(self):
        item = ArtifactRegistry(name="test-item")
        result = ArtifactRegistryEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ArtifactRegistry(name="get-test")
        ArtifactRegistryEngine().register(item)
        found = ArtifactRegistryEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ArtifactRegistryEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ArtifactRegistryEngine().register(ArtifactRegistry(name=f"list-{i}"))
        items = ArtifactRegistryEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ArtifactRegistry(name="original")
        ArtifactRegistryEngine().register(item)
        updated = ArtifactRegistryEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ArtifactRegistryEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ArtifactRegistry(name="delete-me")
        ArtifactRegistryEngine().register(item)
        assert ArtifactRegistryEngine().delete(item.id) is True
        assert ArtifactRegistryEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ArtifactRegistryEngine().register(ArtifactRegistry(name=f"cap-{i}"))
        assert len(ArtifactRegistryEngine().list()) == 100

    def test_singleton(self):
        e1 = ArtifactRegistryEngine()
        e2 = ArtifactRegistryEngine()
        assert e1 is e2
