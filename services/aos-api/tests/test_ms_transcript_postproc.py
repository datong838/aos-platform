"""
W5 — 转录文本后续处理
Tests: TranscriptPostprocEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_transcript_postproc import TranscriptPostproc, TranscriptPostprocEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    TranscriptPostprocEngine().reset()
    yield
    TranscriptPostprocEngine().reset()


class TestTranscriptPostprocEngine:
    def test_register(self):
        item = TranscriptPostproc(name="test-item")
        result = TranscriptPostprocEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = TranscriptPostproc(name="get-test")
        TranscriptPostprocEngine().register(item)
        found = TranscriptPostprocEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert TranscriptPostprocEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            TranscriptPostprocEngine().register(TranscriptPostproc(name=f"list-{i}"))
        items = TranscriptPostprocEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = TranscriptPostproc(name="original")
        TranscriptPostprocEngine().register(item)
        updated = TranscriptPostprocEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert TranscriptPostprocEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = TranscriptPostproc(name="delete-me")
        TranscriptPostprocEngine().register(item)
        assert TranscriptPostprocEngine().delete(item.id) is True
        assert TranscriptPostprocEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            TranscriptPostprocEngine().register(TranscriptPostproc(name=f"cap-{i}"))
        assert len(TranscriptPostprocEngine().list()) == 100

    def test_singleton(self):
        e1 = TranscriptPostprocEngine()
        e2 = TranscriptPostprocEngine()
        assert e1 is e2
