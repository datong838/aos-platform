"""
W5 — Ontology 实体浏览
Tests: OntologyBrowseEntryEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.dl_ontology_browse import OntologyBrowseEntry, OntologyBrowseEntryEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    OntologyBrowseEntryEngine().reset()
    yield
    OntologyBrowseEntryEngine().reset()


class TestOntologyBrowseEntryEngine:
    def test_register(self):
        item = OntologyBrowseEntry(name="test-item")
        result = OntologyBrowseEntryEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = OntologyBrowseEntry(name="get-test")
        OntologyBrowseEntryEngine().register(item)
        found = OntologyBrowseEntryEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert OntologyBrowseEntryEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            OntologyBrowseEntryEngine().register(OntologyBrowseEntry(name=f"list-{i}"))
        items = OntologyBrowseEntryEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = OntologyBrowseEntry(name="original")
        OntologyBrowseEntryEngine().register(item)
        updated = OntologyBrowseEntryEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert OntologyBrowseEntryEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = OntologyBrowseEntry(name="delete-me")
        OntologyBrowseEntryEngine().register(item)
        assert OntologyBrowseEntryEngine().delete(item.id) is True
        assert OntologyBrowseEntryEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            OntologyBrowseEntryEngine().register(OntologyBrowseEntry(name=f"cap-{i}"))
        assert len(OntologyBrowseEntryEngine().list()) == 100

    def test_singleton(self):
        e1 = OntologyBrowseEntryEngine()
        e2 = OntologyBrowseEntryEngine()
        assert e1 is e2
