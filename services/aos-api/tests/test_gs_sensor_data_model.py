"""
W6 — 传感器数据模型
Tests: SensorDataModelEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.gs_sensor_data_model import SensorDataModel, SensorDataModelEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    SensorDataModelEngine().reset()
    yield
    SensorDataModelEngine().reset()


class TestSensorDataModelEngine:
    def test_register(self):
        item = SensorDataModel(name="test-item")
        result = SensorDataModelEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = SensorDataModel(name="get-test")
        SensorDataModelEngine().register(item)
        found = SensorDataModelEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert SensorDataModelEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            SensorDataModelEngine().register(SensorDataModel(name=f"list-{i}"))
        items = SensorDataModelEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = SensorDataModel(name="original")
        SensorDataModelEngine().register(item)
        updated = SensorDataModelEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert SensorDataModelEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = SensorDataModel(name="delete-me")
        SensorDataModelEngine().register(item)
        assert SensorDataModelEngine().delete(item.id) is True
        assert SensorDataModelEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            SensorDataModelEngine().register(SensorDataModel(name=f"cap-{i}"))
        assert len(SensorDataModelEngine().list()) == 100

    def test_singleton(self):
        e1 = SensorDataModelEngine()
        e2 = SensorDataModelEngine()
        assert e1 is e2
