"""
W5 — 分类标记
Tests: ClassifyTagEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_classify_tag import ClassifyTag, ClassifyTagEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ClassifyTagEngine().reset()
    yield
    ClassifyTagEngine().reset()


class TestClassifyTagEngine:
    def test_register(self):
        item = ClassifyTag(name="test-item")
        result = ClassifyTagEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ClassifyTag(name="get-test")
        ClassifyTagEngine().register(item)
        found = ClassifyTagEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ClassifyTagEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ClassifyTagEngine().register(ClassifyTag(name=f"list-{i}"))
        items = ClassifyTagEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ClassifyTag(name="original")
        ClassifyTagEngine().register(item)
        updated = ClassifyTagEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ClassifyTagEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ClassifyTag(name="delete-me")
        ClassifyTagEngine().register(item)
        assert ClassifyTagEngine().delete(item.id) is True
        assert ClassifyTagEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ClassifyTagEngine().register(ClassifyTag(name=f"cap-{i}"))
        assert len(ClassifyTagEngine().list()) == 100

    def test_singleton(self):
        e1 = ClassifyTagEngine()
        e2 = ClassifyTagEngine()
        assert e1 is e2
