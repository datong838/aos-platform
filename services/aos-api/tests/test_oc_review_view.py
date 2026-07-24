"""
W5 — 审查视图
Tests: ReviewViewEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oc_review_view import ReviewView, ReviewViewEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ReviewViewEngine().reset()
    yield
    ReviewViewEngine().reset()


class TestReviewViewEngine:
    def test_register(self):
        item = ReviewView(name="test-item")
        result = ReviewViewEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ReviewView(name="get-test")
        ReviewViewEngine().register(item)
        found = ReviewViewEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ReviewViewEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ReviewViewEngine().register(ReviewView(name=f"list-{i}"))
        items = ReviewViewEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ReviewView(name="original")
        ReviewViewEngine().register(item)
        updated = ReviewViewEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ReviewViewEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ReviewView(name="delete-me")
        ReviewViewEngine().register(item)
        assert ReviewViewEngine().delete(item.id) is True
        assert ReviewViewEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ReviewViewEngine().register(ReviewView(name=f"cap-{i}"))
        assert len(ReviewViewEngine().list()) == 100

    def test_singleton(self):
        e1 = ReviewViewEngine()
        e2 = ReviewViewEngine()
        assert e1 is e2
