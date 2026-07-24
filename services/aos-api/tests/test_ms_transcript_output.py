"""
W5 — 转录输出选项
Tests: TranscriptOutputEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_transcript_output import TranscriptOutput, TranscriptOutputEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    TranscriptOutputEngine().reset()
    yield
    TranscriptOutputEngine().reset()


class TestTranscriptOutputEngine:
    def test_register(self):
        item = TranscriptOutput(name="test-item")
        result = TranscriptOutputEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = TranscriptOutput(name="get-test")
        TranscriptOutputEngine().register(item)
        found = TranscriptOutputEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert TranscriptOutputEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            TranscriptOutputEngine().register(TranscriptOutput(name=f"list-{i}"))
        items = TranscriptOutputEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = TranscriptOutput(name="original")
        TranscriptOutputEngine().register(item)
        updated = TranscriptOutputEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert TranscriptOutputEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = TranscriptOutput(name="delete-me")
        TranscriptOutputEngine().register(item)
        assert TranscriptOutputEngine().delete(item.id) is True
        assert TranscriptOutputEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            TranscriptOutputEngine().register(TranscriptOutput(name=f"cap-{i}"))
        assert len(TranscriptOutputEngine().list()) == 100

    def test_singleton(self):
        e1 = TranscriptOutputEngine()
        e2 = TranscriptOutputEngine()
        assert e1 is e2
