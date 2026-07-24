"""
W6 — 多源异构三种解法
Tests: MultiSourceHeterogeneousEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.zz_multi_source_heterogeneous import MultiSourceHeterogeneous, MultiSourceHeterogeneousEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    MultiSourceHeterogeneousEngine().reset()
    yield
    MultiSourceHeterogeneousEngine().reset()


class TestMultiSourceHeterogeneousEngine:
    def test_register(self):
        item = MultiSourceHeterogeneous(name="test-item")
        result = MultiSourceHeterogeneousEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = MultiSourceHeterogeneous(name="get-test")
        MultiSourceHeterogeneousEngine().register(item)
        found = MultiSourceHeterogeneousEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert MultiSourceHeterogeneousEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            MultiSourceHeterogeneousEngine().register(MultiSourceHeterogeneous(name=f"list-{i}"))
        items = MultiSourceHeterogeneousEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = MultiSourceHeterogeneous(name="original")
        MultiSourceHeterogeneousEngine().register(item)
        updated = MultiSourceHeterogeneousEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert MultiSourceHeterogeneousEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = MultiSourceHeterogeneous(name="delete-me")
        MultiSourceHeterogeneousEngine().register(item)
        assert MultiSourceHeterogeneousEngine().delete(item.id) is True
        assert MultiSourceHeterogeneousEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            MultiSourceHeterogeneousEngine().register(MultiSourceHeterogeneous(name=f"cap-{i}"))
        assert len(MultiSourceHeterogeneousEngine().list()) == 100

    def test_singleton(self):
        e1 = MultiSourceHeterogeneousEngine()
        e2 = MultiSourceHeterogeneousEngine()
        assert e1 is e2
