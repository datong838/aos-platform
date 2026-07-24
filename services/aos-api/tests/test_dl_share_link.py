"""
W5 — 快速分享链接
Tests: ShareLinkEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.dl_share_link import ShareLink, ShareLinkEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ShareLinkEngine().reset()
    yield
    ShareLinkEngine().reset()


class TestShareLinkEngine:
    def test_register(self):
        item = ShareLink(name="test-item")
        result = ShareLinkEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ShareLink(name="get-test")
        ShareLinkEngine().register(item)
        found = ShareLinkEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ShareLinkEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ShareLinkEngine().register(ShareLink(name=f"list-{i}"))
        items = ShareLinkEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ShareLink(name="original")
        ShareLinkEngine().register(item)
        updated = ShareLinkEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ShareLinkEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ShareLink(name="delete-me")
        ShareLinkEngine().register(item)
        assert ShareLinkEngine().delete(item.id) is True
        assert ShareLinkEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ShareLinkEngine().register(ShareLink(name=f"cap-{i}"))
        assert len(ShareLinkEngine().list()) == 100

    def test_singleton(self):
        e1 = ShareLinkEngine()
        e2 = ShareLinkEngine()
        assert e1 is e2
