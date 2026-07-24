"""
W5 — PR 审查
Tests: PrReviewEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_pr_review import PrReview, PrReviewEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    PrReviewEngine().reset()
    yield
    PrReviewEngine().reset()


class TestPrReviewEngine:
    def test_register(self):
        item = PrReview(name="test-item")
        result = PrReviewEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = PrReview(name="get-test")
        PrReviewEngine().register(item)
        found = PrReviewEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert PrReviewEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            PrReviewEngine().register(PrReview(name=f"list-{i}"))
        items = PrReviewEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = PrReview(name="original")
        PrReviewEngine().register(item)
        updated = PrReviewEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert PrReviewEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = PrReview(name="delete-me")
        PrReviewEngine().register(item)
        assert PrReviewEngine().delete(item.id) is True
        assert PrReviewEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            PrReviewEngine().register(PrReview(name=f"cap-{i}"))
        assert len(PrReviewEngine().list()) == 100

    def test_singleton(self):
        e1 = PrReviewEngine()
        e2 = PrReviewEngine()
        assert e1 is e2
