"""
W6 — Docker 制品发布
Tests: DockerArtifactPublishEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_docker_artifact_publish import DockerArtifactPublish, DockerArtifactPublishEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    DockerArtifactPublishEngine().reset()
    yield
    DockerArtifactPublishEngine().reset()


class TestDockerArtifactPublishEngine:
    def test_register(self):
        item = DockerArtifactPublish(name="test-item")
        result = DockerArtifactPublishEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = DockerArtifactPublish(name="get-test")
        DockerArtifactPublishEngine().register(item)
        found = DockerArtifactPublishEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert DockerArtifactPublishEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            DockerArtifactPublishEngine().register(DockerArtifactPublish(name=f"list-{i}"))
        items = DockerArtifactPublishEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = DockerArtifactPublish(name="original")
        DockerArtifactPublishEngine().register(item)
        updated = DockerArtifactPublishEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert DockerArtifactPublishEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = DockerArtifactPublish(name="delete-me")
        DockerArtifactPublishEngine().register(item)
        assert DockerArtifactPublishEngine().delete(item.id) is True
        assert DockerArtifactPublishEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            DockerArtifactPublishEngine().register(DockerArtifactPublish(name=f"cap-{i}"))
        assert len(DockerArtifactPublishEngine().list()) == 100

    def test_singleton(self):
        e1 = DockerArtifactPublishEngine()
        e2 = DockerArtifactPublishEngine()
        assert e1 is e2
