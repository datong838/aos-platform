"""Phase 3 · AIP Lineage — 单元测试。"""
import pytest

from aos_api.aip_lineage_engine import get_engine, LineageEngine, TRACE_SEGMENTS


@pytest.fixture(autouse=True)
def reset_engine():
    get_engine().reset()
    yield


def test_create_and_get():
    eng = get_engine()
    rec = eng.create(agent_id="a-1", query="test query")
    assert rec.agent_id == "a-1"
    fetched = eng.get(rec.id)
    assert fetched is not None


def test_list_filter():
    eng = get_engine()
    eng.create(agent_id="a1", query="q1")
    eng.create(agent_id="a2", query="q2", status="failed")
    a1_items = eng.list(agent_id="a1")
    assert len(a1_items) == 1
    failed = eng.list(status="failed")
    assert len(failed) == 1


def test_update():
    eng = get_engine()
    rec = eng.create(agent_id="a1", query="q")
    updated = eng.update(rec.id, status="degraded", tokens_used=500)
    assert updated.status == "degraded"
    assert updated.tokens_used == 500


def test_delete():
    eng = get_engine()
    rec = eng.create(agent_id="a1", query="q")
    assert eng.delete(rec.id) is True
    assert eng.get(rec.id) is None


def test_build_default_trace():
    eng = get_engine()
    segments = eng.build_default_trace("a-1", "test")
    assert len(segments) == 6
    names = [s.name for s in segments]
    assert names == TRACE_SEGMENTS


def test_trace_segment_detail():
    eng = get_engine()
    segments = eng.build_default_trace("a-1", "hello world")
    input_seg = segments[0]
    assert input_seg.name == "input"
    assert input_seg.duration_ms > 0
    assert "query_length" in input_seg.detail


def test_stats():
    eng = get_engine()
    eng.create(agent_id="a1", query="q1", status="ok")
    eng.create(agent_id="a2", query="q2", status="failed")
    stats = eng.stats()
    assert stats["total"] == 2
    assert "by_status" in stats


def test_singleton():
    e1 = get_engine()
    e2 = LineageEngine()
    assert e1 is e2
