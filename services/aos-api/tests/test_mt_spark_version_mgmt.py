"""
W6 — Spark 版本管理
Tests: SparkVersionMgmtEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.mt_spark_version_mgmt import SparkVersionMgmt, SparkVersionMgmtEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    SparkVersionMgmtEngine().reset()
    yield
    SparkVersionMgmtEngine().reset()


class TestSparkVersionMgmtEngine:
    def test_register(self):
        item = SparkVersionMgmt(name="test-item")
        result = SparkVersionMgmtEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = SparkVersionMgmt(name="get-test")
        SparkVersionMgmtEngine().register(item)
        found = SparkVersionMgmtEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert SparkVersionMgmtEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            SparkVersionMgmtEngine().register(SparkVersionMgmt(name=f"list-{i}"))
        items = SparkVersionMgmtEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = SparkVersionMgmt(name="original")
        SparkVersionMgmtEngine().register(item)
        updated = SparkVersionMgmtEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert SparkVersionMgmtEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = SparkVersionMgmt(name="delete-me")
        SparkVersionMgmtEngine().register(item)
        assert SparkVersionMgmtEngine().delete(item.id) is True
        assert SparkVersionMgmtEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            SparkVersionMgmtEngine().register(SparkVersionMgmt(name=f"cap-{i}"))
        assert len(SparkVersionMgmtEngine().list()) == 100

    def test_singleton(self):
        e1 = SparkVersionMgmtEngine()
        e2 = SparkVersionMgmtEngine()
        assert e1 is e2
