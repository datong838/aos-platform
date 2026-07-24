"""
W5 — 音频文件导入路径
Tests: AudioImportPathEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_audio_import_path import AudioImportPath, AudioImportPathEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    AudioImportPathEngine().reset()
    yield
    AudioImportPathEngine().reset()


class TestAudioImportPathEngine:
    def test_register(self):
        item = AudioImportPath(name="test-item")
        result = AudioImportPathEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = AudioImportPath(name="get-test")
        AudioImportPathEngine().register(item)
        found = AudioImportPathEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert AudioImportPathEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            AudioImportPathEngine().register(AudioImportPath(name=f"list-{i}"))
        items = AudioImportPathEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = AudioImportPath(name="original")
        AudioImportPathEngine().register(item)
        updated = AudioImportPathEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert AudioImportPathEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = AudioImportPath(name="delete-me")
        AudioImportPathEngine().register(item)
        assert AudioImportPathEngine().delete(item.id) is True
        assert AudioImportPathEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            AudioImportPathEngine().register(AudioImportPath(name=f"cap-{i}"))
        assert len(AudioImportPathEngine().list()) == 100

    def test_singleton(self):
        e1 = AudioImportPathEngine()
        e2 = AudioImportPathEngine()
        assert e1 is e2
