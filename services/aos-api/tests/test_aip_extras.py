"""W2-V · AIP 智能层扩展组测试：#78 调试器 + #79 Automate + #80 四层成熟度."""
from __future__ import annotations

import pytest

from aos_api.aip_extras import (
    AIPExtrasError,
    AutomateEngine,
    AutomateTrigger,
    DebuggerEngine,
    MaturityEngine,
    MaturityLevel,
    ProposedChange,
    _eval_condition,
)


# ════════════════════ #78 DebuggerEngine ════════════════════

class TestDebuggerEngine:
    """调试器引擎 14 项测试。"""

    def test_create_session_returns_id(self) -> None:
        eng = DebuggerEngine()
        s = eng.create_session("logic-1", {"x": 1})
        assert s.id.startswith("dbg-")
        assert s.logic_id == "logic-1"
        assert s.status == "pending"
        assert s.current_step == 0
        # inputs 非空时生成 input_x + execute 两个步骤
        assert len(s.steps) == 2

    def test_get_session_not_found(self) -> None:
        eng = DebuggerEngine()
        with pytest.raises(AIPExtrasError) as exc:
            eng.get_session("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_sessions_by_logic(self) -> None:
        eng = DebuggerEngine()
        eng.create_session("L1", {})
        eng.create_session("L2", {})
        eng.create_session("L1", {})
        items = eng.list_sessions(logic_id="L1")
        assert len(items) == 2
        assert all(s.logic_id == "L1" for s in items)

    def test_step_forward_first_step(self) -> None:
        eng = DebuggerEngine()
        s = eng.create_session("L1", {"a": 1})
        step = eng.step_forward(s.id)
        assert step.status == "completed"
        assert step.index == 0
        assert step.variables_after.get("a") == 1
        s2 = eng.get_session(s.id)
        assert s2.current_step == 1
        assert s2.status == "paused"

    def test_step_forward_to_completion(self) -> None:
        eng = DebuggerEngine()
        s = eng.create_session("L1", {"a": 1})
        eng.step_forward(s.id)
        eng.step_forward(s.id)  # execute 步骤
        s2 = eng.get_session(s.id)
        assert s2.status == "completed"
        assert s2.current_step == 2

    def test_step_forward_after_completed(self) -> None:
        eng = DebuggerEngine()
        s = eng.create_session("L1", {"a": 1})
        eng.step_forward(s.id)
        eng.step_forward(s.id)
        with pytest.raises(AIPExtrasError) as exc:
            eng.step_forward(s.id)
        assert exc.value.code == "SESSION_COMPLETED"

    def test_step_backward(self) -> None:
        eng = DebuggerEngine()
        s = eng.create_session("L1", {"a": 1})
        eng.step_forward(s.id)
        step = eng.step_backward(s.id)
        assert step.index == 0
        s2 = eng.get_session(s.id)
        assert s2.current_step == 0
        assert s2.status == "pending"

    def test_step_backward_at_beginning(self) -> None:
        eng = DebuggerEngine()
        s = eng.create_session("L1", {"a": 1})
        with pytest.raises(AIPExtrasError) as exc:
            eng.step_backward(s.id)
        assert exc.value.code == "AT_BEGINNING"

    def test_run_to_completion(self) -> None:
        eng = DebuggerEngine()
        s = eng.create_session("L1", {"a": 1, "b": 2})
        final = eng.run_to_completion(s.id)
        assert final.status == "completed"
        assert final.current_step == len(final.steps)

    def test_preview_proposal_not_applied(self) -> None:
        eng = DebuggerEngine()
        s = eng.create_session("L1", {"a": 1})
        p = eng.preview_proposal(s.id, [
            ProposedChange(object_type="OT", object_id="o1", field_path="name",
                           new_value="X", rationale="LLM 推理"),
        ])
        assert p.applied is False
        assert len(p.proposed_changes) == 1
        assert p.debug_session_id == s.id

    def test_list_proposals(self) -> None:
        eng = DebuggerEngine()
        s = eng.create_session("L1", {"a": 1})
        eng.preview_proposal(s.id, [])
        eng.preview_proposal(s.id, [])
        items = eng.list_proposals(session_id=s.id)
        assert len(items) == 2

    def test_apply_proposal(self) -> None:
        eng = DebuggerEngine()
        s = eng.create_session("L1", {"a": 1})
        p = eng.preview_proposal(s.id, [])
        applied = eng.apply_proposal(p.id)
        assert applied.applied is True

    def test_apply_proposal_already_applied(self) -> None:
        eng = DebuggerEngine()
        s = eng.create_session("L1", {"a": 1})
        p = eng.preview_proposal(s.id, [])
        eng.apply_proposal(p.id)
        with pytest.raises(AIPExtrasError) as exc:
            eng.apply_proposal(p.id)
        assert exc.value.code == "ALREADY_APPLIED"

    def test_preview_multiple_changes(self) -> None:
        eng = DebuggerEngine()
        s = eng.create_session("L1", {"a": 1})
        p = eng.preview_proposal(s.id, [
            ProposedChange(object_type="OT", object_id="o1", field_path="f1",
                           change_type="create", new_value=1),
            ProposedChange(object_type="OT", object_id="o2", field_path="f2",
                           change_type="update", old_value=0, new_value=1),
            ProposedChange(object_type="OT", object_id="o3", field_path="f3",
                           change_type="delete", old_value="x"),
        ])
        assert len(p.proposed_changes) == 3
        assert p.proposed_changes[0].change_type == "create"
        assert p.proposed_changes[1].change_type == "update"
        assert p.proposed_changes[2].change_type == "delete"


# ════════════════════ #79 AutomateEngine ════════════════════

class _FakeClock:
    """可控时钟，用于 cooldown 测试。"""

    def __init__(self, t0: float = 1000.0) -> None:
        self.t = t0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class TestAutomateEngine:
    """Automate 引擎 13 项测试。"""

    def _make_trigger(self, **kw: object) -> AutomateTrigger:
        defaults: dict[str, object] = {
            "name": "t1",
            "logic_id": "L1",
            "event_type": "manual",
        }
        defaults.update(kw)
        return AutomateTrigger(**defaults)

    def test_upsert_trigger_new(self) -> None:
        eng = AutomateEngine()
        t = eng.upsert_trigger(self._make_trigger())
        assert t.id.startswith("trg-")
        assert t.trigger_count == 0

    def test_get_trigger_not_found(self) -> None:
        eng = AutomateEngine()
        with pytest.raises(AIPExtrasError) as exc:
            eng.get_trigger("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_triggers_enabled_only(self) -> None:
        eng = AutomateEngine()
        eng.upsert_trigger(self._make_trigger(name="t1", enabled=True))
        eng.upsert_trigger(self._make_trigger(name="t2", enabled=False))
        all_items = eng.list_triggers(enabled_only=False)
        enabled = eng.list_triggers(enabled_only=True)
        assert len(all_items) == 2
        assert len(enabled) == 1
        assert enabled[0].name == "t1"

    def test_delete_trigger(self) -> None:
        eng = AutomateEngine()
        t = eng.upsert_trigger(self._make_trigger())
        assert eng.delete_trigger(t.id) is True
        with pytest.raises(AIPExtrasError):
            eng.get_trigger(t.id)

    def test_evaluate_condition_met(self) -> None:
        eng = AutomateEngine()
        t = eng.upsert_trigger(self._make_trigger(
            condition={"event_type": "object_changed"},
        ))
        assert eng.evaluate(t.id, {"event_type": "object_changed"}) is True

    def test_evaluate_condition_not_met(self) -> None:
        eng = AutomateEngine()
        t = eng.upsert_trigger(self._make_trigger(
            condition={"event_type": "object_changed"},
        ))
        assert eng.evaluate(t.id, {"event_type": "schedule"}) is False

    def test_fire_success(self) -> None:
        clk = _FakeClock()
        eng = AutomateEngine(clock=clk)
        t = eng.upsert_trigger(self._make_trigger())
        run = eng.fire(t.id, {"event_type": "manual"})
        assert run.status == "completed"
        assert run.proposal_id.startswith("prop-")
        t2 = eng.get_trigger(t.id)
        assert t2.trigger_count == 1
        assert t2.last_triggered_at == clk.t

    def test_fire_disabled(self) -> None:
        eng = AutomateEngine()
        t = eng.upsert_trigger(self._make_trigger(enabled=False))
        with pytest.raises(AIPExtrasError) as exc:
            eng.fire(t.id)
        assert exc.value.code == "AUTOMATE_DISABLED"

    def test_fire_in_cooldown(self) -> None:
        clk = _FakeClock()
        eng = AutomateEngine(clock=clk)
        t = eng.upsert_trigger(self._make_trigger(cooldown_seconds=10.0))
        eng.fire(t.id)  # 第一次成功
        clk.advance(5.0)  # 还在冷却期
        with pytest.raises(AIPExtrasError) as exc:
            eng.fire(t.id)
        assert exc.value.code == "IN_COOLDOWN"

    def test_fire_condition_not_met(self) -> None:
        eng = AutomateEngine()
        t = eng.upsert_trigger(self._make_trigger(
            condition={"event_type": "object_changed"},
        ))
        with pytest.raises(AIPExtrasError) as exc:
            eng.fire(t.id, {"event_type": "schedule"})
        assert exc.value.code == "CONDITION_NOT_MET"

    def test_list_runs(self) -> None:
        eng = AutomateEngine()
        t = eng.upsert_trigger(self._make_trigger())
        eng.fire(t.id)
        eng.fire(t.id)
        items = eng.list_runs(trigger_id=t.id)
        assert len(items) == 2

    def test_get_run_not_found(self) -> None:
        eng = AutomateEngine()
        with pytest.raises(AIPExtrasError) as exc:
            eng.get_run("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_fire_multiple_accumulates_count(self) -> None:
        clk = _FakeClock()
        eng = AutomateEngine(clock=clk)
        t = eng.upsert_trigger(self._make_trigger())
        for _ in range(3):
            eng.fire(t.id)
            clk.advance(1.0)
        t2 = eng.get_trigger(t.id)
        assert t2.trigger_count == 3
        assert len(eng.list_runs()) == 3


# ════════════════════ #80 MaturityEngine ════════════════════

class TestMaturityEngine:
    """四层成熟度引擎 13 项测试。"""

    def test_list_levels(self) -> None:
        eng = MaturityEngine()
        items = eng.list_levels()
        assert len(items) == 4
        assert [lv.level for lv in items] == ["L1", "L2", "L3", "L4"]

    def test_get_level_l2(self) -> None:
        eng = MaturityEngine()
        lv = eng.get_level("L2")
        assert lv.level == "L2"
        assert "llm_gateway" in lv.required_capabilities

    def test_get_level_not_found(self) -> None:
        eng = MaturityEngine()
        with pytest.raises(AIPExtrasError) as exc:
            eng.get_level("L9")
        assert exc.value.code == "NOT_FOUND"

    def test_upsert_level_update(self) -> None:
        eng = MaturityEngine()
        new_l2 = MaturityLevel(
            level="L2", name="辅助-改",
            description="改后描述",
            required_capabilities=["llm_gateway", "prompt_engineering", "evals", "new_cap"],
        )
        eng.upsert_level(new_l2)
        got = eng.get_level("L2")
        assert got.name == "辅助-改"
        assert "new_cap" in got.required_capabilities

    def test_register_capability(self) -> None:
        eng = MaturityEngine()
        eng.register_capability("rule_engine", True)
        caps = eng.list_capabilities()
        assert caps.get("rule_engine") is True

    def test_list_capabilities(self) -> None:
        eng = MaturityEngine()
        eng.register_capability("a", True)
        eng.register_capability("b", False)
        caps = eng.list_capabilities()
        assert len(caps) == 2
        assert caps["a"] is True
        assert caps["b"] is False

    def test_assess_all_satisfied_l4(self) -> None:
        eng = MaturityEngine()
        for c in ["rule_engine", "manual_call",
                  "llm_gateway", "prompt_engineering", "evals",
                  "logic_engine", "automate", "debugger", "proposal_preview",
                  "failover", "circuit_breaker", "auto_apply", "monitoring"]:
            eng.register_capability(c, True)
        asmt = eng.assess()
        assert asmt.current_level == "L4"
        assert asmt.score == 1.0
        assert asmt.gaps == []

    def test_assess_only_l1_satisfied(self) -> None:
        eng = MaturityEngine()
        eng.register_capability("rule_engine", True)
        eng.register_capability("manual_call", True)
        asmt = eng.assess()
        assert asmt.current_level == "L1"
        assert asmt.score < 1.0

    def test_assess_partial_highest_satisfied(self) -> None:
        eng = MaturityEngine()
        # L1 + L2 满足，L3 缺
        for c in ["rule_engine", "manual_call",
                  "llm_gateway", "prompt_engineering", "evals"]:
            eng.register_capability(c, True)
        asmt = eng.assess()
        assert asmt.current_level == "L2"

    def test_assess_gaps_includes_missing(self) -> None:
        eng = MaturityEngine()
        # 全空 → current=L0，gaps 应包含 L1~L4 全部缺失
        asmt = eng.assess()
        assert "L1:rule_engine" in asmt.gaps
        assert "L4:monitoring" in asmt.gaps
        assert asmt.score == 0.0

    def test_assess_recommendation_nonempty(self) -> None:
        eng = MaturityEngine()
        asmt = eng.assess()
        assert asmt.recommendation
        assert "当前" in asmt.recommendation

    def test_set_and_get_target_level(self) -> None:
        eng = MaturityEngine()
        eng.set_target_level("L3")
        assert eng.get_target_level() == "L3"

    def test_list_assessments_history(self) -> None:
        eng = MaturityEngine()
        eng.assess()
        eng.assess()
        items = eng.list_assessments()
        assert len(items) == 2


# ════════════════════ 条件评估辅助 ════════════════════

class TestEvalCondition:
    """_eval_condition 辅助测试。"""

    def test_empty_condition_is_true(self) -> None:
        assert _eval_condition({}, {"a": 1}) is True

    def test_eq_op_dict(self) -> None:
        assert _eval_condition(
            {"x": {"op": "eq", "value": 5}}, {"x": 5}
        ) is True
        assert _eval_condition(
            {"x": {"op": "eq", "value": 5}}, {"x": 6}
        ) is False

    def test_gt_lt_op(self) -> None:
        assert _eval_condition(
            {"x": {"op": "gt", "value": 10}}, {"x": 11}
        ) is True
        assert _eval_condition(
            {"x": {"op": "lt", "value": 10}}, {"x": 11}
        ) is False
