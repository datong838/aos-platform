"""
W5 — Ontology 切换器
Tests: OntologySwitcherEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oc_ontology_switcher import OntologySwitcher, OntologySwitcherEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    OntologySwitcherEngine().reset()
    yield
    OntologySwitcherEngine().reset()


class TestOntologySwitcherEngine:
    def test_register(self):
        item = OntologySwitcher(name="test-item")
        result = OntologySwitcherEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = OntologySwitcher(name="get-test")
        OntologySwitcherEngine().register(item)
        found = OntologySwitcherEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert OntologySwitcherEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            OntologySwitcherEngine().register(OntologySwitcher(name=f"list-{i}"))
        items = OntologySwitcherEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = OntologySwitcher(name="original")
        OntologySwitcherEngine().register(item)
        updated = OntologySwitcherEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert OntologySwitcherEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = OntologySwitcher(name="delete-me")
        OntologySwitcherEngine().register(item)
        assert OntologySwitcherEngine().delete(item.id) is True
        assert OntologySwitcherEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            OntologySwitcherEngine().register(OntologySwitcher(name=f"cap-{i}"))
        assert len(OntologySwitcherEngine().list()) == 100

    def test_singleton(self):
        e1 = OntologySwitcherEngine()
        e2 = OntologySwitcherEngine()
        assert e1 is e2
