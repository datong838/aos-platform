"""
W5 — 平台 Facade
Tests: PlatformFacadeEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ca_platform_facade import PlatformFacade, PlatformFacadeEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    PlatformFacadeEngine().reset()
    yield
    PlatformFacadeEngine().reset()


class TestPlatformFacadeEngine:
    def test_register(self):
        item = PlatformFacade(name="test-item")
        result = PlatformFacadeEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = PlatformFacade(name="get-test")
        PlatformFacadeEngine().register(item)
        found = PlatformFacadeEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert PlatformFacadeEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            PlatformFacadeEngine().register(PlatformFacade(name=f"list-{i}"))
        items = PlatformFacadeEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = PlatformFacade(name="original")
        PlatformFacadeEngine().register(item)
        updated = PlatformFacadeEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert PlatformFacadeEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = PlatformFacade(name="delete-me")
        PlatformFacadeEngine().register(item)
        assert PlatformFacadeEngine().delete(item.id) is True
        assert PlatformFacadeEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            PlatformFacadeEngine().register(PlatformFacade(name=f"cap-{i}"))
        assert len(PlatformFacadeEngine().list()) == 100

    def test_singleton(self):
        e1 = PlatformFacadeEngine()
        e2 = PlatformFacadeEngine()
        assert e1 is e2
