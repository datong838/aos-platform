"""
W5 — Refresh Token
Tests: RefreshTokenEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.id_refresh_token import RefreshToken, RefreshTokenEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    RefreshTokenEngine().reset()
    yield
    RefreshTokenEngine().reset()


class TestRefreshTokenEngine:
    def test_register(self):
        item = RefreshToken(name="test-item")
        result = RefreshTokenEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = RefreshToken(name="get-test")
        RefreshTokenEngine().register(item)
        found = RefreshTokenEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert RefreshTokenEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            RefreshTokenEngine().register(RefreshToken(name=f"list-{i}"))
        items = RefreshTokenEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = RefreshToken(name="original")
        RefreshTokenEngine().register(item)
        updated = RefreshTokenEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert RefreshTokenEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = RefreshToken(name="delete-me")
        RefreshTokenEngine().register(item)
        assert RefreshTokenEngine().delete(item.id) is True
        assert RefreshTokenEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            RefreshTokenEngine().register(RefreshToken(name=f"cap-{i}"))
        assert len(RefreshTokenEngine().list()) == 100

    def test_singleton(self):
        e1 = RefreshTokenEngine()
        e2 = RefreshTokenEngine()
        assert e1 is e2
