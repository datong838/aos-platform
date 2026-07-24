"""
W5 — Ontology 地理集成
Tests: OntologyGeoEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.gs_ontology_geo import OntologyGeo, OntologyGeoEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    OntologyGeoEngine().reset()
    yield
    OntologyGeoEngine().reset()


class TestOntologyGeoEngine:
    def test_register(self):
        item = OntologyGeo(name="test-item")
        result = OntologyGeoEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = OntologyGeo(name="get-test")
        OntologyGeoEngine().register(item)
        found = OntologyGeoEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert OntologyGeoEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            OntologyGeoEngine().register(OntologyGeo(name=f"list-{i}"))
        items = OntologyGeoEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = OntologyGeo(name="original")
        OntologyGeoEngine().register(item)
        updated = OntologyGeoEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert OntologyGeoEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = OntologyGeo(name="delete-me")
        OntologyGeoEngine().register(item)
        assert OntologyGeoEngine().delete(item.id) is True
        assert OntologyGeoEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            OntologyGeoEngine().register(OntologyGeo(name=f"cap-{i}"))
        assert len(OntologyGeoEngine().list()) == 100

    def test_singleton(self):
        e1 = OntologyGeoEngine()
        e2 = OntologyGeoEngine()
        assert e1 is e2
