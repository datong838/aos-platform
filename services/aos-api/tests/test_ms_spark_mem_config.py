"""
W6 — Spark 内存配置建议
Tests: SparkMemConfigEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_spark_mem_config import SparkMemConfig, SparkMemConfigEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    SparkMemConfigEngine().reset()
    yield
    SparkMemConfigEngine().reset()


class TestSparkMemConfigEngine:
    def test_register(self):
        item = SparkMemConfig(name="test-item")
        result = SparkMemConfigEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = SparkMemConfig(name="get-test")
        SparkMemConfigEngine().register(item)
        found = SparkMemConfigEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert SparkMemConfigEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            SparkMemConfigEngine().register(SparkMemConfig(name=f"list-{i}"))
        items = SparkMemConfigEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = SparkMemConfig(name="original")
        SparkMemConfigEngine().register(item)
        updated = SparkMemConfigEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert SparkMemConfigEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = SparkMemConfig(name="delete-me")
        SparkMemConfigEngine().register(item)
        assert SparkMemConfigEngine().delete(item.id) is True
        assert SparkMemConfigEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            SparkMemConfigEngine().register(SparkMemConfig(name=f"cap-{i}"))
        assert len(SparkMemConfigEngine().list()) == 100

    def test_singleton(self):
        e1 = SparkMemConfigEngine()
        e2 = SparkMemConfigEngine()
        assert e1 is e2
