"""
W5 — 组织标记
Tests: OrgTagEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_org_tag import OrgTag, OrgTagEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    OrgTagEngine().reset()
    yield
    OrgTagEngine().reset()


class TestOrgTagEngine:
    def test_register(self):
        item = OrgTag(name="test-item")
        result = OrgTagEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = OrgTag(name="get-test")
        OrgTagEngine().register(item)
        found = OrgTagEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert OrgTagEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            OrgTagEngine().register(OrgTag(name=f"list-{i}"))
        items = OrgTagEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = OrgTag(name="original")
        OrgTagEngine().register(item)
        updated = OrgTagEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert OrgTagEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = OrgTag(name="delete-me")
        OrgTagEngine().register(item)
        assert OrgTagEngine().delete(item.id) is True
        assert OrgTagEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            OrgTagEngine().register(OrgTag(name=f"cap-{i}"))
        assert len(OrgTagEngine().list()) == 100

    def test_singleton(self):
        e1 = OrgTagEngine()
        e2 = OrgTagEngine()
        assert e1 is e2
