"""
W5 — 任务模型
Tests: TaskModelEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oc_task_model import TaskModel, TaskModelEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    TaskModelEngine().reset()
    yield
    TaskModelEngine().reset()


class TestTaskModelEngine:
    def test_register(self):
        item = TaskModel(name="test-item")
        result = TaskModelEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = TaskModel(name="get-test")
        TaskModelEngine().register(item)
        found = TaskModelEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert TaskModelEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            TaskModelEngine().register(TaskModel(name=f"list-{i}"))
        items = TaskModelEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = TaskModel(name="original")
        TaskModelEngine().register(item)
        updated = TaskModelEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert TaskModelEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = TaskModel(name="delete-me")
        TaskModelEngine().register(item)
        assert TaskModelEngine().delete(item.id) is True
        assert TaskModelEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            TaskModelEngine().register(TaskModel(name=f"cap-{i}"))
        assert len(TaskModelEngine().list()) == 100

    def test_singleton(self):
        e1 = TaskModelEngine()
        e2 = TaskModelEngine()
        assert e1 is e2
