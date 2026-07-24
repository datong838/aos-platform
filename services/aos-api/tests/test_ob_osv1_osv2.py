"""
W5 — OSv1-OSv2 迁移框架
Tests: OsvMigrationEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ob_osv1_osv2 import OsvMigration, OsvMigrationEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    OsvMigrationEngine().reset()
    yield
    OsvMigrationEngine().reset()


class TestOsvMigrationEngine:
    def test_register(self):
        item = OsvMigration(name="test-item")
        result = OsvMigrationEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = OsvMigration(name="get-test")
        OsvMigrationEngine().register(item)
        found = OsvMigrationEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert OsvMigrationEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            OsvMigrationEngine().register(OsvMigration(name=f"list-{i}"))
        items = OsvMigrationEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = OsvMigration(name="original")
        OsvMigrationEngine().register(item)
        updated = OsvMigrationEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert OsvMigrationEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = OsvMigration(name="delete-me")
        OsvMigrationEngine().register(item)
        assert OsvMigrationEngine().delete(item.id) is True
        assert OsvMigrationEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            OsvMigrationEngine().register(OsvMigration(name=f"cap-{i}"))
        assert len(OsvMigrationEngine().list()) == 100

    def test_singleton(self):
        e1 = OsvMigrationEngine()
        e2 = OsvMigrationEngine()
        assert e1 is e2
