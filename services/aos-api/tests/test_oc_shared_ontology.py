"""
W6 — 共享 Ontology
Tests: SharedOntologyEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oc_shared_ontology import SharedOntology, SharedOntologyEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    SharedOntologyEngine().reset()
    yield
    SharedOntologyEngine().reset()


class TestSharedOntologyEngine:
    def test_register(self):
        item = SharedOntology(name="test-item")
        result = SharedOntologyEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = SharedOntology(name="get-test")
        SharedOntologyEngine().register(item)
        found = SharedOntologyEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert SharedOntologyEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            SharedOntologyEngine().register(SharedOntology(name=f"list-{i}"))
        items = SharedOntologyEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = SharedOntology(name="original")
        SharedOntologyEngine().register(item)
        updated = SharedOntologyEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert SharedOntologyEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = SharedOntology(name="delete-me")
        SharedOntologyEngine().register(item)
        assert SharedOntologyEngine().delete(item.id) is True
        assert SharedOntologyEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            SharedOntologyEngine().register(SharedOntology(name=f"cap-{i}"))
        assert len(SharedOntologyEngine().list()) == 100

    def test_singleton(self):
        e1 = SharedOntologyEngine()
        e2 = SharedOntologyEngine()
        assert e1 is e2
