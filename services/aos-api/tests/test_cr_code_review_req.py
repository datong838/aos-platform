"""
W5 — 代码审核要求
Tests: CodeReviewReqEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_code_review_req import CodeReviewReq, CodeReviewReqEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    CodeReviewReqEngine().reset()
    yield
    CodeReviewReqEngine().reset()


class TestCodeReviewReqEngine:
    def test_register(self):
        item = CodeReviewReq(name="test-item")
        result = CodeReviewReqEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = CodeReviewReq(name="get-test")
        CodeReviewReqEngine().register(item)
        found = CodeReviewReqEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert CodeReviewReqEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            CodeReviewReqEngine().register(CodeReviewReq(name=f"list-{i}"))
        items = CodeReviewReqEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = CodeReviewReq(name="original")
        CodeReviewReqEngine().register(item)
        updated = CodeReviewReqEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert CodeReviewReqEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = CodeReviewReq(name="delete-me")
        CodeReviewReqEngine().register(item)
        assert CodeReviewReqEngine().delete(item.id) is True
        assert CodeReviewReqEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            CodeReviewReqEngine().register(CodeReviewReq(name=f"cap-{i}"))
        assert len(CodeReviewReqEngine().list()) == 100

    def test_singleton(self):
        e1 = CodeReviewReqEngine()
        e2 = CodeReviewReqEngine()
        assert e1 is e2
