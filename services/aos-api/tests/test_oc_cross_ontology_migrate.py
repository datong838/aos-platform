"""
W5 — 跨 Ontology 迁移
Tests: CrossOntologyMigrateEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oc_cross_ontology_migrate import CrossOntologyMigrate, CrossOntologyMigrateEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    CrossOntologyMigrateEngine().reset()
    yield
    CrossOntologyMigrateEngine().reset()


class TestCrossOntologyMigrateEngine:
    def test_register(self):
        item = CrossOntologyMigrate(name="test-item")
        result = CrossOntologyMigrateEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = CrossOntologyMigrate(name="get-test")
        CrossOntologyMigrateEngine().register(item)
        found = CrossOntologyMigrateEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert CrossOntologyMigrateEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            CrossOntologyMigrateEngine().register(CrossOntologyMigrate(name=f"list-{i}"))
        items = CrossOntologyMigrateEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = CrossOntologyMigrate(name="original")
        CrossOntologyMigrateEngine().register(item)
        updated = CrossOntologyMigrateEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert CrossOntologyMigrateEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = CrossOntologyMigrate(name="delete-me")
        CrossOntologyMigrateEngine().register(item)
        assert CrossOntologyMigrateEngine().delete(item.id) is True
        assert CrossOntologyMigrateEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            CrossOntologyMigrateEngine().register(CrossOntologyMigrate(name=f"cap-{i}"))
        assert len(CrossOntologyMigrateEngine().list()) == 100

    def test_singleton(self):
        e1 = CrossOntologyMigrateEngine()
        e2 = CrossOntologyMigrateEngine()
        assert e1 is e2
