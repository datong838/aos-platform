"""
W5 — 制品发布凭证
Tests: ArtifactCredentialEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_artifact_credential import ArtifactCredential, ArtifactCredentialEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ArtifactCredentialEngine().reset()
    yield
    ArtifactCredentialEngine().reset()


class TestArtifactCredentialEngine:
    def test_register(self):
        item = ArtifactCredential(name="test-item")
        result = ArtifactCredentialEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ArtifactCredential(name="get-test")
        ArtifactCredentialEngine().register(item)
        found = ArtifactCredentialEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ArtifactCredentialEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ArtifactCredentialEngine().register(ArtifactCredential(name=f"list-{i}"))
        items = ArtifactCredentialEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ArtifactCredential(name="original")
        ArtifactCredentialEngine().register(item)
        updated = ArtifactCredentialEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ArtifactCredentialEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ArtifactCredential(name="delete-me")
        ArtifactCredentialEngine().register(item)
        assert ArtifactCredentialEngine().delete(item.id) is True
        assert ArtifactCredentialEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ArtifactCredentialEngine().register(ArtifactCredential(name=f"cap-{i}"))
        assert len(ArtifactCredentialEngine().list()) == 100

    def test_singleton(self):
        e1 = ArtifactCredentialEngine()
        e2 = ArtifactCredentialEngine()
        assert e1 is e2
