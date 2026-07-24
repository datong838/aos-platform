"""
W6 — Spark Profiles
Tests: SparkProfileEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_spark_profiles import SparkProfile, SparkProfileEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    SparkProfileEngine().reset()
    yield
    SparkProfileEngine().reset()


class TestSparkProfileEngine:
    def test_register(self):
        item = SparkProfile(name="test-item")
        result = SparkProfileEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = SparkProfile(name="get-test")
        SparkProfileEngine().register(item)
        found = SparkProfileEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert SparkProfileEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            SparkProfileEngine().register(SparkProfile(name=f"list-{i}"))
        items = SparkProfileEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = SparkProfile(name="original")
        SparkProfileEngine().register(item)
        updated = SparkProfileEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert SparkProfileEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = SparkProfile(name="delete-me")
        SparkProfileEngine().register(item)
        assert SparkProfileEngine().delete(item.id) is True
        assert SparkProfileEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            SparkProfileEngine().register(SparkProfile(name=f"cap-{i}"))
        assert len(SparkProfileEngine().list()) == 100

    def test_singleton(self):
        e1 = SparkProfileEngine()
        e2 = SparkProfileEngine()
        assert e1 is e2
