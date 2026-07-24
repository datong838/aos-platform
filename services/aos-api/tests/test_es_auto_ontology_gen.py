"""
W5 — 自动 Ontology 生成
Tests: AutoOntologyGenEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.es_auto_ontology_gen import AutoOntologyGen, AutoOntologyGenEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    AutoOntologyGenEngine().reset()
    yield
    AutoOntologyGenEngine().reset()


class TestAutoOntologyGenEngine:
    def test_register(self):
        item = AutoOntologyGen(name="test-item")
        result = AutoOntologyGenEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = AutoOntologyGen(name="get-test")
        AutoOntologyGenEngine().register(item)
        found = AutoOntologyGenEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert AutoOntologyGenEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            AutoOntologyGenEngine().register(AutoOntologyGen(name=f"list-{i}"))
        items = AutoOntologyGenEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = AutoOntologyGen(name="original")
        AutoOntologyGenEngine().register(item)
        updated = AutoOntologyGenEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert AutoOntologyGenEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = AutoOntologyGen(name="delete-me")
        AutoOntologyGenEngine().register(item)
        assert AutoOntologyGenEngine().delete(item.id) is True
        assert AutoOntologyGenEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            AutoOntologyGenEngine().register(AutoOntologyGen(name=f"cap-{i}"))
        assert len(AutoOntologyGenEngine().list()) == 100

    def test_singleton(self):
        e1 = AutoOntologyGenEngine()
        e2 = AutoOntologyGenEngine()
        assert e1 is e2
