"""
W6 — 增量包
Tests: IncrementalPackageEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.fr2_incremental_package import IncrementalPackage, IncrementalPackageEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    IncrementalPackageEngine().reset()
    yield
    IncrementalPackageEngine().reset()


class TestIncrementalPackageEngine:
    def test_register(self):
        item = IncrementalPackage(name="test-item")
        result = IncrementalPackageEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = IncrementalPackage(name="get-test")
        IncrementalPackageEngine().register(item)
        found = IncrementalPackageEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert IncrementalPackageEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            IncrementalPackageEngine().register(IncrementalPackage(name=f"list-{i}"))
        items = IncrementalPackageEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = IncrementalPackage(name="original")
        IncrementalPackageEngine().register(item)
        updated = IncrementalPackageEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert IncrementalPackageEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = IncrementalPackage(name="delete-me")
        IncrementalPackageEngine().register(item)
        assert IncrementalPackageEngine().delete(item.id) is True
        assert IncrementalPackageEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            IncrementalPackageEngine().register(IncrementalPackage(name=f"cap-{i}"))
        assert len(IncrementalPackageEngine().list()) == 100

    def test_singleton(self):
        e1 = IncrementalPackageEngine()
        e2 = IncrementalPackageEngine()
        assert e1 is e2
