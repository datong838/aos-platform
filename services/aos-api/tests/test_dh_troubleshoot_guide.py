"""
W5 — 故障排除指南
Tests: TroubleshootGuideEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.dh_troubleshoot_guide import TroubleshootGuide, TroubleshootGuideEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    TroubleshootGuideEngine().reset()
    yield
    TroubleshootGuideEngine().reset()


class TestTroubleshootGuideEngine:
    def test_register(self):
        item = TroubleshootGuide(name="test-item")
        result = TroubleshootGuideEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = TroubleshootGuide(name="get-test")
        TroubleshootGuideEngine().register(item)
        found = TroubleshootGuideEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert TroubleshootGuideEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            TroubleshootGuideEngine().register(TroubleshootGuide(name=f"list-{i}"))
        items = TroubleshootGuideEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = TroubleshootGuide(name="original")
        TroubleshootGuideEngine().register(item)
        updated = TroubleshootGuideEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert TroubleshootGuideEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = TroubleshootGuide(name="delete-me")
        TroubleshootGuideEngine().register(item)
        assert TroubleshootGuideEngine().delete(item.id) is True
        assert TroubleshootGuideEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            TroubleshootGuideEngine().register(TroubleshootGuide(name=f"cap-{i}"))
        assert len(TroubleshootGuideEngine().list()) == 100

    def test_singleton(self):
        e1 = TroubleshootGuideEngine()
        e2 = TroubleshootGuideEngine()
        assert e1 is e2
