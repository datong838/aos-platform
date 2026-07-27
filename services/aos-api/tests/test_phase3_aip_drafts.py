"""Phase 3 · AIP Drafts — 单元测试。"""
import pytest

from aos_api.aip_drafts_engine import get_engine, DraftsEngine


@pytest.fixture(autouse=True)
def reset_engine():
    get_engine().reset()
    yield


def test_create_and_get():
    eng = get_engine()
    draft = eng.create("Test Draft", author="user1")
    assert draft.title == "Test Draft"
    fetched = eng.get(draft.id)
    assert fetched is not None


def test_list_filter():
    eng = get_engine()
    eng.create("D1", draft_type="report", status="draft")
    eng.create("D2", draft_type="config", status="approved")
    reports = eng.list(draft_type="report")
    assert len(reports) == 1
    drafts = eng.list(status="draft")
    assert len(drafts) == 1


def test_approve():
    eng = get_engine()
    draft = eng.create("ToApprove")
    approved = eng.approve(draft.id, reviewer="admin1")
    assert approved.status == "approved"
    assert approved.reviewer == "admin1"
    assert approved.reviewed_at is not None


def test_reject():
    eng = get_engine()
    draft = eng.create("ToReject")
    rejected = eng.reject(draft.id, reviewer="admin1", reason="bad")
    assert rejected.status == "rejected"
    assert rejected.metadata["reject_reason"] == "bad"


def test_reopen():
    eng = get_engine()
    draft = eng.create("ToReopen")
    eng.reject(draft.id, reviewer="admin")
    reopened = eng.reopen(draft.id)
    assert reopened.status == "draft"
    assert reopened.reviewed_at is None


def test_approve_already_approved_fails():
    eng = get_engine()
    draft = eng.create("Double")
    eng.approve(draft.id)
    with pytest.raises(ValueError):
        eng.approve(draft.id)


def test_delete():
    eng = get_engine()
    draft = eng.create("ToDelete")
    assert eng.delete(draft.id) is True
    assert eng.get(draft.id) is None


def test_stats():
    eng = get_engine()
    eng.create("D1", status="draft")
    eng.create("D2")
    eng.create("D3")
    eng.approve(eng.list()[0].id, reviewer="r")
    stats = eng.stats()
    assert stats["total"] == 3
    assert "by_status" in stats


def test_singleton():
    e1 = get_engine()
    e2 = DraftsEngine()
    assert e1 is e2
