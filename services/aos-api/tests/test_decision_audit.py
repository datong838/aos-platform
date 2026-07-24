"""W2-X · AIP 决策审计组单测：#84 Decision Lineage + #85 Insight Backfill + #87 Capability Adapter."""
from __future__ import annotations

import pytest

from aos_api.decision_audit import (
    AdapterManifest,
    BackfillConfig,
    CapabilityAdapterEngine,
    DecisionAuditError,
    DecisionLineageEngine,
    DecisionRecord,
    InsightBackfillEngine,
    InsightObject,
)


# ════════════════════════════════════════════════════════════════
# #84 DecisionLineageEngine（12）
# ════════════════════════════════════════════════════════════════

class TestDecisionLineage:
    """#84 · 决策谱系。"""

    def test_record_returns_with_id(self):
        eng = DecisionLineageEngine()
        rec = DecisionRecord(logic_id="logic-1")
        out = eng.record(rec)
        assert out.id.startswith("dec-")
        assert out.logic_id == "logic-1"

    def test_get_not_found(self):
        eng = DecisionLineageEngine()
        with pytest.raises(DecisionAuditError) as exc:
            eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self):
        eng = DecisionLineageEngine()
        eng.record(DecisionRecord(logic_id="l1"))
        eng.record(DecisionRecord(logic_id="l2"))
        items = eng.list()
        assert len(items) == 2

    def test_list_filter_by_logic_id(self):
        eng = DecisionLineageEngine()
        eng.record(DecisionRecord(logic_id="l1", actor="a"))
        eng.record(DecisionRecord(logic_id="l2", actor="a"))
        items = eng.list(logic_id="l1")
        assert len(items) == 1
        assert items[0].logic_id == "l1"

    def test_list_filter_by_proposal_id(self):
        eng = DecisionLineageEngine()
        eng.record(DecisionRecord(logic_id="l1", proposal_id="p1"))
        eng.record(DecisionRecord(logic_id="l2", proposal_id="p2"))
        items = eng.list(proposal_id="p1")
        assert len(items) == 1
        assert items[0].proposal_id == "p1"

    def test_list_filter_by_actor(self):
        eng = DecisionLineageEngine()
        eng.record(DecisionRecord(logic_id="l1", actor="alice"))
        eng.record(DecisionRecord(logic_id="l2", actor="bob"))
        items = eng.list(actor="alice")
        assert len(items) == 1
        assert items[0].actor == "alice"

    def test_get_timeline(self):
        eng = DecisionLineageEngine()
        rec = eng.record(DecisionRecord(
            logic_id="l1",
            tool_calls=[{"name": "tool_a"}, {"name": "tool_b"}],
            approval_result="approved",
            actor="alice",
        ))
        tl = eng.get_timeline(rec.id)
        assert tl["decision_id"] == rec.id
        assert tl["logic_id"] == "l1"
        assert len(tl["events"]) == 3  # 2 tool_call + 1 approval
        assert tl["events"][0]["type"] == "tool_call"
        assert tl["events"][2]["type"] == "approval"

    def test_trace_by_proposal(self):
        eng = DecisionLineageEngine()
        eng.record(DecisionRecord(logic_id="l1", proposal_id="p1"))
        eng.record(DecisionRecord(logic_id="l2", proposal_id="p1"))
        eng.record(DecisionRecord(logic_id="l3", proposal_id="p2"))
        items = eng.trace("p1")
        assert len(items) == 2
        assert all(r.proposal_id == "p1" for r in items)

    def test_record_full_fields_preserved(self):
        eng = DecisionLineageEngine()
        rec = DecisionRecord(
            logic_id="l1",
            proposal_id="p1",
            model_id="gpt-4",
            prompt_version="v1",
            object_refs=["obj-1"],
            wiki_fields=["wiki-1"],
            cot="think...",
            tool_calls=[{"name": "x"}],
            draft_params={"k": "v"},
            approval_result="approved",
            actor="alice",
            metadata={"trace_id": "t1"},
        )
        out = eng.record(rec)
        got = eng.get(out.id)
        assert got.model_id == "gpt-4"
        assert got.prompt_version == "v1"
        assert got.object_refs == ["obj-1"]
        assert got.wiki_fields == ["wiki-1"]
        assert got.cot == "think..."
        assert got.tool_calls == [{"name": "x"}]
        assert got.draft_params == {"k": "v"}
        assert got.approval_result == "approved"
        assert got.metadata == {"trace_id": "t1"}

    def test_list_limit(self):
        eng = DecisionLineageEngine()
        for i in range(10):
            eng.record(DecisionRecord(logic_id=f"l{i}"))
        items = eng.list(limit=3)
        assert len(items) == 3

    def test_max_200_records_eviction(self):
        eng = DecisionLineageEngine()
        first_id = None
        for i in range(210):
            rec = eng.record(DecisionRecord(logic_id=f"l{i}"))
            if i == 0:
                first_id = rec.id
        # 第一条已被淘汰
        with pytest.raises(DecisionAuditError):
            eng.get(first_id)
        # 但仍有 200 条
        items = eng.list(limit=500)
        assert len(items) == 200

    def test_get_single(self):
        eng = DecisionLineageEngine()
        rec = eng.record(DecisionRecord(logic_id="l1", actor="alice"))
        got = eng.get(rec.id)
        assert got.id == rec.id
        assert got.actor == "alice"


# ════════════════════════════════════════════════════════════════
# #85 InsightBackfillEngine（14）
# ════════════════════════════════════════════════════════════════

class TestInsightBackfill:
    """#85 · Insight 回填。"""

    def test_get_config_default(self):
        eng = InsightBackfillEngine()
        cfg = eng.get_config()
        assert cfg.confidence_threshold == 0.85
        assert cfg.auto_backfill is False
        assert cfg.max_daily_backfill == 100

    def test_update_config(self):
        eng = InsightBackfillEngine()
        new_cfg = BackfillConfig(confidence_threshold=0.9, auto_backfill=True, max_daily_backfill=50)
        eng.update_config(new_cfg)
        got = eng.get_config()
        assert got.confidence_threshold == 0.9
        assert got.auto_backfill is True
        assert got.max_daily_backfill == 50

    def test_register_insight(self):
        eng = InsightBackfillEngine()
        ins = InsightObject(title="t", content="c", confidence=0.9, source_decision_id="d1")
        out = eng.register_insight(ins)
        assert out.id.startswith("ins-")
        assert out.title == "t"

    def test_get_insight_not_found(self):
        eng = InsightBackfillEngine()
        with pytest.raises(DecisionAuditError) as exc:
            eng.get_insight("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_insights_default(self):
        eng = InsightBackfillEngine()
        eng.register_insight(InsightObject(title="t1", content="c", confidence=0.9, source_decision_id="d1"))
        eng.register_insight(InsightObject(title="t2", content="c", confidence=0.9, source_decision_id="d2"))
        items = eng.list_insights()
        assert len(items) == 2

    def test_list_insights_min_confidence(self):
        eng = InsightBackfillEngine()
        eng.register_insight(InsightObject(title="t1", content="c", confidence=0.5, source_decision_id="d1"))
        eng.register_insight(InsightObject(title="t2", content="c", confidence=0.95, source_decision_id="d2"))
        items = eng.list_insights(min_confidence=0.9)
        assert len(items) == 1
        assert items[0].confidence == 0.95

    def test_list_insights_by_source_decision_id(self):
        eng = InsightBackfillEngine()
        eng.register_insight(InsightObject(title="t1", content="c", confidence=0.9, source_decision_id="d1"))
        eng.register_insight(InsightObject(title="t2", content="c", confidence=0.9, source_decision_id="d2"))
        items = eng.list_insights(source_decision_id="d1")
        assert len(items) == 1
        assert items[0].source_decision_id == "d1"

    def test_list_insights_by_backfill_status(self):
        eng = InsightBackfillEngine()
        eng.register_insight(InsightObject(title="t1", content="c", confidence=0.9, source_decision_id="d1"))
        # 第二个改为 completed
        ins2 = eng.register_insight(InsightObject(title="t2", content="c", confidence=0.9, source_decision_id="d2"))
        eng.backfill(ins2.id)
        items = eng.list_insights(backfill_status="completed")
        assert len(items) == 1
        assert items[0].backfill_status == "completed"

    def test_backfill_success(self):
        eng = InsightBackfillEngine()
        ins = eng.register_insight(InsightObject(title="t", content="c", confidence=0.9, source_decision_id="d1"))
        out = eng.backfill(ins.id)
        assert out.backfill_status == "completed"

    def test_evaluate_and_register_high_confidence(self):
        eng = InsightBackfillEngine()
        # 默认 threshold=0.85
        ins = eng.evaluate_and_register(
            decision_id="d1", title="t", content="c", confidence=0.95, links=["obj-1"],
        )
        assert ins.id.startswith("ins-")
        assert ins.confidence == 0.95
        assert ins.links == ["obj-1"]
        assert ins.source_decision_id == "d1"

    def test_evaluate_and_register_below_threshold(self):
        eng = InsightBackfillEngine()
        with pytest.raises(DecisionAuditError) as exc:
            eng.evaluate_and_register(
                decision_id="d1", title="t", content="c", confidence=0.5,
            )
        assert exc.value.code == "BELOW_THRESHOLD"

    def test_list_pending(self):
        eng = InsightBackfillEngine()
        ins1 = eng.register_insight(InsightObject(title="t1", content="c", confidence=0.9, source_decision_id="d1"))
        eng.register_insight(InsightObject(title="t2", content="c", confidence=0.9, source_decision_id="d2"))
        eng.backfill(ins1.id)  # 改为 completed
        pending = eng.list_pending()
        assert len(pending) == 1
        assert pending[0].title == "t2"

    def test_cleanup_failed(self):
        eng = InsightBackfillEngine()
        # 构造一个 failed 状态的 Insight
        ins = eng.register_insight(InsightObject(title="t", content="c", confidence=0.9, source_decision_id="d1"))
        ins.backfill_status = "failed"
        eng._insights[ins.id] = ins  # 直接改状态用于测试
        # 再加一个 pending 的
        eng.register_insight(InsightObject(title="t2", content="c", confidence=0.9, source_decision_id="d2"))
        n = eng.cleanup()
        assert n == 1
        # failed 已清理，剩 1 个
        assert len(eng.list_insights()) == 1

    def test_backfill_already_completed(self):
        eng = InsightBackfillEngine()
        ins = eng.register_insight(InsightObject(title="t", content="c", confidence=0.9, source_decision_id="d1"))
        eng.backfill(ins.id)
        with pytest.raises(DecisionAuditError) as exc:
            eng.backfill(ins.id)
        assert exc.value.code == "ALREADY_BACKFILLED"


# ════════════════════════════════════════════════════════════════
# #87 CapabilityAdapterEngine（16）
# ════════════════════════════════════════════════════════════════

class TestCapabilityAdapter:
    """#87 · Capability Adapter。"""

    def test_register_c0_adapter(self):
        eng = CapabilityAdapterEngine()
        m = AdapterManifest(id="a1", name="adapter1", capability_class="C0")
        out = eng.register(m)
        assert out.id == "a1"
        assert out.capability_class == "C0"

    def test_register_invalid_class(self):
        eng = CapabilityAdapterEngine()
        with pytest.raises(DecisionAuditError) as exc:
            eng.register(AdapterManifest(id="a1", name="x", capability_class="X9"))
        assert exc.value.code == "INVALID_CLASS"

    def test_register_invalid_auth_type(self):
        eng = CapabilityAdapterEngine()
        with pytest.raises(DecisionAuditError) as exc:
            eng.register(AdapterManifest(id="a1", name="x", capability_class="C0", auth_type="invalid"))
        assert exc.value.code == "INVALID_AUTH_TYPE"

    def test_get_not_found(self):
        eng = CapabilityAdapterEngine()
        with pytest.raises(DecisionAuditError) as exc:
            eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self):
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C0"))
        eng.register(AdapterManifest(id="a2", name="y", capability_class="C1"))
        items = eng.list()
        assert len(items) == 2

    def test_list_filter_by_class(self):
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C0"))
        eng.register(AdapterManifest(id="a2", name="y", capability_class="C1"))
        items = eng.list(capability_class="C0")
        assert len(items) == 1
        assert items[0].capability_class == "C0"

    def test_list_enabled_only(self):
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C0", enabled=True))
        eng.register(AdapterManifest(id="a2", name="y", capability_class="C0", enabled=False))
        items = eng.list(enabled_only=True)
        assert len(items) == 1
        assert items[0].id == "a1"

    def test_update(self):
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C0", description="old"))
        updated = eng.update("a1", {"description": "new", "enabled": False})
        assert updated.description == "new"
        assert updated.enabled is False
        # get 返回新值
        got = eng.get("a1")
        assert got.description == "new"

    def test_delete(self):
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C0"))
        assert eng.delete("a1") is True
        # 再次删除返回 False
        assert eng.delete("a1") is False

    def test_invoke_c0_success(self):
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C0"))
        inv = eng.invoke("a1", {"k": "v"}, invoke_callable=lambda x: {"result": x["k"]})
        assert inv.status == "completed"
        assert inv.outputs == {"result": "v"}
        assert inv.operation == "invoke"

    def test_invoke_c1_invalid_class(self):
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C1"))
        with pytest.raises(DecisionAuditError) as exc:
            eng.invoke("a1", {})
        assert exc.value.code == "INVALID_CLASS"

    def test_invoke_disabled_adapter(self):
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C0", enabled=False))
        with pytest.raises(DecisionAuditError) as exc:
            eng.invoke("a1", {})
        assert exc.value.code == "ADAPTER_DISABLED"

    def test_submit_c1_returns_job_id(self):
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C1"))
        inv = eng.submit("a1", {"k": "v"}, submit_callable=lambda x: "job-123")
        assert inv.operation == "submit"
        assert inv.job_id == "job-123"
        assert inv.status == "running"

    def test_status_c1(self):
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C1"))
        inv = eng.status("a1", "job-1", status_callable=lambda j: "running")
        assert inv.operation == "status"
        assert inv.job_id == "job-1"
        assert inv.status == "running"

    def test_cancel_c1(self):
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C1"))
        inv = eng.cancel("a1", "job-1")
        assert inv.operation == "cancel"
        assert inv.status == "cancelled"

    def test_session_open_close_c2(self):
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C2"))
        # open
        open_inv = eng.session_open("a1", {"user": "alice"}, open_callable=lambda x: "sess-1")
        assert open_inv.operation == "session.open"
        assert open_inv.session_id == "sess-1"
        assert open_inv.status == "running"
        # close
        close_inv = eng.session_close("a1", "sess-1")
        assert close_inv.operation == "session.close"
        assert close_inv.session_id == "sess-1"
        assert close_inv.status == "completed"


# ════════════════════════════════════════════════════════════════
# 补充：单例
# ════════════════════════════════════════════════════════════════

class TestSingletons:
    """单例 getter 测试。"""

    def test_get_decision_lineage_engine_singleton(self):
        from aos_api.decision_audit import get_decision_lineage_engine
        a = get_decision_lineage_engine()
        b = get_decision_lineage_engine()
        assert a is b

    def test_get_insight_backfill_engine_singleton(self):
        from aos_api.decision_audit import get_insight_backfill_engine
        a = get_insight_backfill_engine()
        b = get_insight_backfill_engine()
        assert a is b

    def test_get_capability_adapter_engine_singleton(self):
        from aos_api.decision_audit import get_capability_adapter_engine
        a = get_capability_adapter_engine()
        b = get_capability_adapter_engine()
        assert a is b


# ════════════════════════════════════════════════════════════════
# 补充：扩展边界
# ════════════════════════════════════════════════════════════════

class TestExtended:
    """边界与扩展用例。"""

    def test_invoke_c0_with_default_callable_echo(self):
        """invoke 默认 callable 返回 echo。"""
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C0"))
        inv = eng.invoke("a1", {"hello": "world"})
        assert inv.status == "completed"
        assert inv.outputs == {"echo": {"hello": "world"}}

    def test_invoke_c0_failure_captured(self):
        """invoke callable 抛异常 → status=failed。"""
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C0"))

        def _bad(_: dict) -> dict:
            raise RuntimeError("boom")

        inv = eng.invoke("a1", {}, invoke_callable=_bad)
        assert inv.status == "failed"
        assert "boom" in inv.error

    def test_submit_default_job_id(self):
        """submit 默认 callable 生成 job_id。"""
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C1"))
        inv = eng.submit("a1", {})
        assert inv.job_id.startswith("job-")

    def test_status_invalid_status(self):
        """status 未知状态 → INVALID_STATUS。"""
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C1"))
        with pytest.raises(DecisionAuditError) as exc:
            eng.status("a1", "j1", status_callable=lambda j: "unknown_state")
        assert exc.value.code == "INVALID_STATUS"

    def test_artifact_default_callable(self):
        """artifact 默认 callable 返回 job_id。"""
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C1"))
        inv = eng.artifact("a1", "job-1")
        assert inv.status == "completed"
        assert inv.outputs == {"job_id": "job-1"}

    def test_session_open_default_session_id(self):
        """session_open 默认 callable 生成 session_id。"""
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C2"))
        inv = eng.session_open("a1")
        assert inv.session_id.startswith("sess-")

    def test_update_immutable_class(self):
        """update 不允许改 capability_class。"""
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C0"))
        with pytest.raises(DecisionAuditError) as exc:
            eng.update("a1", {"capability_class": "C1"})
        assert exc.value.code == "IMMUTABLE_FIELD"

    def test_list_invocations_by_adapter(self):
        """list_invocations 按 adapter_id 过滤。"""
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C0"))
        eng.register(AdapterManifest(id="a2", name="y", capability_class="C0"))
        eng.invoke("a1", {})
        eng.invoke("a2", {})
        items = eng.list_invocations(adapter_id="a1")
        assert all(i.adapter_id == "a1" for i in items)
        assert len(items) == 1  # invoke 二次写覆盖同 id，故 1 条

    def test_register_insight_invalid_confidence(self):
        """register_insight confidence 越界 → INVALID_CONFIDENCE。"""
        eng = InsightBackfillEngine()
        with pytest.raises(DecisionAuditError) as exc:
            eng.register_insight(InsightObject(title="t", content="c", confidence=1.5, source_decision_id="d1"))
        assert exc.value.code == "INVALID_CONFIDENCE"

    def test_update_config_invalid_threshold(self):
        """update_config threshold 越界 → INVALID_THRESHOLD。"""
        eng = InsightBackfillEngine()
        with pytest.raises(DecisionAuditError) as exc:
            eng.update_config(BackfillConfig(confidence_threshold=1.5))
        assert exc.value.code == "INVALID_THRESHOLD"

    def test_invoke_invocation_max_cap(self):
        """200 条调用记录上限：旧记录被淘汰。"""
        eng = CapabilityAdapterEngine()
        eng.register(AdapterManifest(id="a1", name="x", capability_class="C0"))
        for _ in range(210):
            eng.invoke("a1", {})  # 每次 2 条
        items = eng.list_invocations(limit=500)
        # 每次写 2 条，故上限 200 条对应 100 次 invoke
        assert len(items) == 200

    def test_decision_timeline_empty_events(self):
        """无 tool_calls/approval 时 timeline 仅含 started_at。"""
        eng = DecisionLineageEngine()
        rec = eng.record(DecisionRecord(logic_id="l1"))
        tl = eng.get_timeline(rec.id)
        assert tl["events"] == []
        assert tl["started_at"] == rec.timestamp
