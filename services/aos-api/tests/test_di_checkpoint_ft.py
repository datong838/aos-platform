"""
W5 — 检查点容错
Tests: CheckpointFaultToleranceEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.di_checkpoint_ft import CheckpointFaultTolerance, CheckpointFaultToleranceEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    CheckpointFaultToleranceEngine().reset()
    yield
    CheckpointFaultToleranceEngine().reset()


class TestCheckpointFaultToleranceEngine:
    def test_register(self):
        item = CheckpointFaultTolerance(name="test-item")
        result = CheckpointFaultToleranceEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = CheckpointFaultTolerance(name="get-test")
        CheckpointFaultToleranceEngine().register(item)
        found = CheckpointFaultToleranceEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert CheckpointFaultToleranceEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            CheckpointFaultToleranceEngine().register(CheckpointFaultTolerance(name=f"list-{i}"))
        items = CheckpointFaultToleranceEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = CheckpointFaultTolerance(name="original")
        CheckpointFaultToleranceEngine().register(item)
        updated = CheckpointFaultToleranceEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert CheckpointFaultToleranceEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = CheckpointFaultTolerance(name="delete-me")
        CheckpointFaultToleranceEngine().register(item)
        assert CheckpointFaultToleranceEngine().delete(item.id) is True
        assert CheckpointFaultToleranceEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            CheckpointFaultToleranceEngine().register(CheckpointFaultTolerance(name=f"cap-{i}"))
        assert len(CheckpointFaultToleranceEngine().list()) == 100

    def test_singleton(self):
        e1 = CheckpointFaultToleranceEngine()
        e2 = CheckpointFaultToleranceEngine()
        assert e1 is e2
