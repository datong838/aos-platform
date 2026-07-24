"""W2-T · k-LLM 路由编排组测试：#71 智能路由 + #72 场景化路由 + #73 熔断/热切换."""
from __future__ import annotations

import pytest

from aos_api.llm_routing import (
    BlockRoute,
    CircuitConfig,
    CircuitState,
    FailoverEngine,
    LLMRoutingFacade,
    ModelCandidate,
    RouteRule,
    RoutingError,
    RoutingRequest,
    ScenarioRouter,
    SmartRouter,
)


# ──────────────── #71 智能路由 ────────────────

def test_smart_register_candidate():
    eng = SmartRouter()
    c = eng.register(ModelCandidate(id="agnes-text", tier="high"))
    assert c.id == "agnes-text"
    assert c.tier == "high"


def test_smart_unregister():
    eng = SmartRouter()
    eng.register(ModelCandidate(id="m1"))
    assert eng.unregister("m1") is True
    assert eng.list() == []
    assert eng.unregister("m1") is False


def test_smart_list_enabled_only():
    eng = SmartRouter()
    eng.register(ModelCandidate(id="m1", enabled=True))
    eng.register(ModelCandidate(id="m2", enabled=False))
    assert len(eng.list()) == 2
    assert len(eng.list(enabled_only=True)) == 1
    assert eng.list(enabled_only=True)[0].id == "m1"


def test_smart_choose_basic():
    eng = SmartRouter()
    eng.register(ModelCandidate(id="low-model", tier="low", max_context=4096))
    eng.register(ModelCandidate(id="high-model", tier="high", max_context=32768))
    result = eng.choose(RoutingRequest(query="hello", complexity=5, context_length=8000))
    # high-model 在复杂度+上下文维度都更优
    assert result["model_id"] == "high-model"
    assert "score" in result
    assert "alternatives" in result
    assert "score_breakdown" in result


def test_smart_choose_context_filter():
    eng = SmartRouter()
    eng.register(ModelCandidate(id="small", tier="mid", max_context=4096))
    eng.register(ModelCandidate(id="large", tier="mid", max_context=32768))
    result = eng.choose(RoutingRequest(context_length=8000))
    assert result["model_id"] == "large"


def test_smart_choose_modality_filter():
    eng = SmartRouter()
    eng.register(ModelCandidate(id="text-only", tier="mid", modalities=["text"]))
    eng.register(ModelCandidate(id="vision", tier="mid", modalities=["image", "text"]))
    result = eng.choose(RoutingRequest(preferred_modalities=["image"]))
    assert result["model_id"] == "vision"


def test_smart_choose_security_restricted():
    eng = SmartRouter()
    eng.register(ModelCandidate(id="public", tier="mid", egress="allow"))
    eng.register(ModelCandidate(id="private", tier="mid", egress="forbidden"))
    result = eng.choose(RoutingRequest(security_label="restricted"))
    assert result["model_id"] == "private"


def test_smart_choose_cost_budget():
    eng = SmartRouter()
    eng.register(ModelCandidate(id="cheap", tier="mid", max_context=32768, cost_per_1k=0.001))
    eng.register(ModelCandidate(id="expensive", tier="mid", max_context=32768, cost_per_1k=0.05))
    # context 10k, budget 0.05 → expensive 投射 0.5 超预算
    result = eng.choose(RoutingRequest(context_length=10000, cost_budget=0.05))
    assert result["model_id"] == "cheap"


def test_smart_choose_no_candidate():
    eng = SmartRouter()
    eng.register(ModelCandidate(id="m1", max_context=1024))
    with pytest.raises(RoutingError) as exc:
        eng.choose(RoutingRequest(context_length=100000))
    assert exc.value.code == "NO_CANDIDATE"


def test_smart_choose_complexity_tier_match():
    eng = SmartRouter()
    eng.register(ModelCandidate(id="low", tier="low"))
    eng.register(ModelCandidate(id="high", tier="high"))
    # complexity=5 期望 high tier
    result = eng.choose(RoutingRequest(complexity=5))
    assert result["model_id"] == "high"


def test_smart_choose_tag_overlap():
    eng = SmartRouter()
    eng.register(ModelCandidate(id="m1", tier="mid", tags=["general"]))
    eng.register(ModelCandidate(id="m2", tier="mid", tags=["code", "python"]))
    result = eng.choose(RoutingRequest(prefer_tags=["code"]))
    assert result["model_id"] == "m2"


def test_smart_choose_alternatives():
    eng = SmartRouter()
    eng.register(ModelCandidate(id="a", tier="mid"))
    eng.register(ModelCandidate(id="b", tier="mid"))
    eng.register(ModelCandidate(id="c", tier="mid"))
    result = eng.choose(RoutingRequest())
    assert len(result["alternatives"]) == 2
    assert all("model_id" in alt and "score" in alt for alt in result["alternatives"])


# ──────────────── #72 场景化路由 ────────────────

def test_scenario_upsert_rule_create():
    eng = ScenarioRouter()
    r = eng.upsert_rule(RouteRule(
        id="chat-default", task="聊天", task_type="chat", primary="agnes-text",
    ))
    assert r.id == "chat-default"
    assert r.fallback == ""
    assert r.egress == "继承"


def test_scenario_upsert_rule_update():
    eng = ScenarioRouter()
    eng.upsert_rule(RouteRule(id="r1", task="t", task_type="chat", primary="m1"))
    eng.upsert_rule(RouteRule(id="r1", task="t2", task_type="chat", primary="m2"))
    r = eng.get_rule("r1")
    assert r.task == "t2"
    assert r.primary == "m2"


def test_scenario_get_rule_not_found():
    eng = ScenarioRouter()
    with pytest.raises(RoutingError) as exc:
        eng.get_rule("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_scenario_list_rules_filter():
    eng = ScenarioRouter()
    eng.upsert_rule(RouteRule(id="r1", task="t", task_type="chat", primary="m1"))
    eng.upsert_rule(RouteRule(id="r2", task="t", task_type="code", primary="m2"))
    assert len(eng.list_rules()) == 2
    assert len(eng.list_rules(task_type="chat")) == 1
    assert eng.list_rules(task_type="chat")[0].id == "r1"


def test_scenario_delete_rule():
    eng = ScenarioRouter()
    eng.upsert_rule(RouteRule(id="r1", task="t", task_type="chat", primary="m"))
    assert eng.delete_rule("r1") is True
    with pytest.raises(RoutingError):
        eng.get_rule("r1")


def test_scenario_resolve_block_priority():
    eng = ScenarioRouter()
    eng.upsert_rule(RouteRule(id="r1", task="t", task_type="chat", primary="scenario-model"))
    eng.upsert_block(BlockRoute(block_id="b1", model_id="block-model"))
    result = eng.resolve("chat", block_id="b1")
    assert result["primary"] == "block-model"
    assert result["source"] == "block"


def test_scenario_resolve_block_inherit_skips_block():
    eng = ScenarioRouter()
    eng.upsert_rule(RouteRule(id="r1", task="t", task_type="chat", primary="scenario-model"))
    eng.upsert_block(BlockRoute(block_id="b1", model_id="block-model", inherit=True))
    result = eng.resolve("chat", block_id="b1")
    assert result["primary"] == "scenario-model"
    assert result["source"] == "scenario"


def test_scenario_resolve_scenario_hit():
    eng = ScenarioRouter()
    eng.upsert_rule(RouteRule(
        id="r1", task="t", task_type="code", primary="coder", fallback="general",
        egress="审批后",
    ))
    result = eng.resolve("code")
    assert result["primary"] == "coder"
    assert result["fallback"] == "general"
    assert result["egress"] == "审批后"
    assert result["source"] == "scenario"


def test_scenario_resolve_default_fallback():
    eng = ScenarioRouter()
    result = eng.resolve("nonexistent_task_type_xyz")
    assert result["source"] == "default"
    assert "primary" in result


def test_scenario_block_crud():
    eng = ScenarioRouter()
    b = eng.upsert_block(BlockRoute(block_id="b1", model_id="m1"))
    assert eng.get_block("b1").model_id == "m1"
    assert len(eng.list_blocks()) == 1
    eng.upsert_block(BlockRoute(block_id="b1", model_id="m2"))
    assert eng.get_block("b1").model_id == "m2"
    assert eng.delete_block("b1") is True
    with pytest.raises(RoutingError):
        eng.get_block("b1")


def test_scenario_block_delete_protects_rules():
    eng = ScenarioRouter()
    eng.upsert_rule(RouteRule(id="r1", task="t", task_type="chat", primary="m"))
    eng.upsert_block(BlockRoute(block_id="b1", model_id="m"))
    eng.delete_block("b1")
    # rule 应仍然存在
    assert eng.get_rule("r1").primary == "m"


def test_scenario_export_rules_aligned_with_81():
    eng = ScenarioRouter()
    eng.upsert_rule(RouteRule(
        id="summarize", task="摘要", task_type="summarize",
        primary="m1", fallback="—", egress="禁公网", span=False,
    ))
    items = eng.export_rules()
    assert len(items) == 1
    # 与 81 §2.1 RouteRule 结构对齐
    assert set(items[0].keys()) >= {"id", "task", "primary", "fallback", "egress", "span"}


def test_scenario_import_rules_overwrites():
    eng = ScenarioRouter()
    eng.upsert_rule(RouteRule(id="r1", task="old", task_type="chat", primary="old-m"))
    imported = eng.import_rules([
        {"id": "r1", "task": "new", "task_type": "chat", "primary": "new-m"},
        {"id": "r2", "task": "added", "task_type": "code", "primary": "code-m"},
    ])
    assert len(imported) == 2
    assert eng.get_rule("r1").primary == "new-m"
    assert eng.get_rule("r2").primary == "code-m"


def test_scenario_invalid_task_type():
    eng = ScenarioRouter()
    with pytest.raises(RoutingError) as exc:
        eng.upsert_rule(RouteRule(id="r1", task="t", task_type="invalid_type", primary="m"))
    assert exc.value.code == "INVALID_TASK_TYPE"


def test_scenario_invalid_egress():
    eng = ScenarioRouter()
    with pytest.raises(RoutingError) as exc:
        eng.upsert_rule(RouteRule(
            id="r1", task="t", task_type="chat", primary="m", egress="invalid",
        ))
    assert exc.value.code == "INVALID_EGRESS"


# ──────────────── #73 熔断/热切换 ────────────────

class _FakeClock:
    """可控时钟，便于熔断冷却测试。"""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _ok_chat(query: str, model: str | None = None, **kwargs):
    return {"answer": f"[{model}] {query}", "model": model}


def _fail_chat(query: str, model: str | None = None, **kwargs):
    raise RuntimeError(f"model {model} down")


def test_failover_get_state_initial():
    eng = FailoverEngine(chat_callable=_ok_chat)
    st = eng.get_state("m1")
    assert st.state == "closed"
    assert st.consecutive_failures == 0


def test_failover_record_call_failure_increments():
    eng = FailoverEngine(chat_callable=_ok_chat)
    eng.record_call("m1", success=False, error="x")
    eng.record_call("m1", success=False, error="y")
    st = eng.get_state("m1")
    assert st.consecutive_failures == 2


def test_failover_record_call_success_resets():
    eng = FailoverEngine(chat_callable=_ok_chat)
    eng.record_call("m1", success=False)
    eng.record_call("m1", success=False)
    eng.record_call("m1", success=True)
    st = eng.get_state("m1")
    assert st.consecutive_failures == 0
    assert st.state == "closed"


def test_failover_circuit_opens_on_threshold():
    eng = FailoverEngine(chat_callable=_ok_chat)
    eng.set_config("m1", CircuitConfig(failure_threshold=3))
    eng.record_call("m1", success=False)
    eng.record_call("m1", success=False)
    assert eng.get_state("m1").state == "closed"
    eng.record_call("m1", success=False)
    assert eng.get_state("m1").state == "open"


def test_failover_can_call_open_within_cooldown():
    clock = _FakeClock()
    eng = FailoverEngine(chat_callable=_ok_chat, clock=clock)
    eng.set_config("m1", CircuitConfig(failure_threshold=2, cooldown_seconds=60))
    eng.record_call("m1", success=False)
    eng.record_call("m1", success=False)
    assert eng.get_state("m1").state == "open"
    clock.advance(30)  # 冷却未到
    assert eng.can_call("m1") is False


def test_failover_open_to_half_open_after_cooldown():
    clock = _FakeClock()
    eng = FailoverEngine(chat_callable=_ok_chat, clock=clock)
    eng.set_config("m1", CircuitConfig(failure_threshold=2, cooldown_seconds=60))
    eng.record_call("m1", success=False)
    eng.record_call("m1", success=False)
    assert eng.get_state("m1").state == "open"
    clock.advance(60)  # 冷却到期
    assert eng.can_call("m1") is True
    assert eng.get_state("m1").state == "half_open"


def test_failover_half_open_success_closes():
    clock = _FakeClock()
    eng = FailoverEngine(chat_callable=_ok_chat, clock=clock)
    eng.set_config("m1", CircuitConfig(
        failure_threshold=2, cooldown_seconds=60, success_threshold=1,
    ))
    eng.record_call("m1", success=False)
    eng.record_call("m1", success=False)
    clock.advance(60)
    eng.can_call("m1")  # 推进到 half_open
    eng.record_call("m1", success=True)
    assert eng.get_state("m1").state == "closed"
    assert eng.get_state("m1").consecutive_failures == 0


def test_failover_half_open_failure_reopens():
    clock = _FakeClock()
    eng = FailoverEngine(chat_callable=_ok_chat, clock=clock)
    eng.set_config("m1", CircuitConfig(
        failure_threshold=2, cooldown_seconds=60, success_threshold=1,
    ))
    eng.record_call("m1", success=False)
    eng.record_call("m1", success=False)
    clock.advance(60)
    eng.can_call("m1")  # half_open
    opened_at = eng.get_state("m1").opened_at
    eng.record_call("m1", success=False)
    assert eng.get_state("m1").state == "open"
    # opened_at 重置
    assert eng.get_state("m1").opened_at >= opened_at


def test_failover_call_with_failover_primary_success():
    eng = FailoverEngine(chat_callable=_ok_chat)
    result = eng.call_with_failover("hello", primary="m1", fallback="m2")
    assert result["model"] == "m1"
    assert result["fallback_used"] is False
    assert "answer" in result
    assert "call_record_id" in result


def test_failover_call_with_failover_primary_fails_then_fallback():
    # 主模 m1 调用失败，切到 fallback m2 成功
    def chat(query, model=None, **kw):
        if model == "m1":
            raise RuntimeError("m1 down")
        return {"answer": f"[{model}] {query}", "model": model}

    eng = FailoverEngine(chat_callable=chat)
    result = eng.call_with_failover("hello", primary="m1", fallback="m2")
    assert result["model"] == "m2"
    assert result["fallback_used"] is True
    assert result["route_source"] == "failover"
    # 主模失败计数应被记录
    assert eng.get_state("m1").consecutive_failures == 1


def test_failover_call_with_failover_primary_open_skips_to_fallback():
    clock = _FakeClock()
    eng = FailoverEngine(chat_callable=_ok_chat, clock=clock)
    eng.set_config("m1", CircuitConfig(failure_threshold=2, cooldown_seconds=60))
    # 让 m1 进入 open
    eng.record_call("m1", success=False)
    eng.record_call("m1", success=False)
    assert eng.get_state("m1").state == "open"

    called = []

    def spy_chat(query, model=None, **kw):
        called.append(model)
        return {"answer": f"[{model}] {query}", "model": model}

    eng._chat = spy_chat
    result = eng.call_with_failover("hello", primary="m1", fallback="m2")
    assert "m1" not in called  # m1 熔断未调用
    assert "m2" in called
    assert result["model"] == "m2"
    assert result["fallback_used"] is True


def test_failover_call_with_failover_no_fallback():
    eng = FailoverEngine(chat_callable=_fail_chat)
    with pytest.raises(RoutingError) as exc:
        eng.call_with_failover("hello", primary="m1", fallback="")
    assert exc.value.code == "PRIMARY_FAILED_NO_FALLBACK"


def test_failover_call_with_failover_all_failed():
    eng = FailoverEngine(chat_callable=_fail_chat)
    with pytest.raises(RoutingError) as exc:
        eng.call_with_failover("hello", primary="m1", fallback="m2")
    assert exc.value.code == "ALL_FAILED"


def test_failover_reset():
    eng = FailoverEngine(chat_callable=_ok_chat)
    eng.set_config("m1", CircuitConfig(failure_threshold=2))
    eng.record_call("m1", success=False)
    eng.record_call("m1", success=False)
    assert eng.get_state("m1").state == "open"
    st = eng.reset("m1")
    assert st.state == "closed"
    assert st.consecutive_failures == 0


def test_failover_records_list_filter():
    eng = FailoverEngine(chat_callable=_ok_chat)
    eng.record_call("m1", success=True)
    eng.record_call("m2", success=True)
    eng.record_call("m1", success=False)
    all_records = eng.list_records()
    assert len(all_records) == 3
    m1_records = eng.list_records(model_id="m1")
    assert len(m1_records) == 2
    assert all(r.model_id == "m1" for r in m1_records)


# ──────────────── 集成 ────────────────

def test_facade_smart_route_and_call_end_to_end():
    smart = SmartRouter()
    smart.register(ModelCandidate(id="primary-model", tier="high", max_context=8192))
    smart.register(ModelCandidate(id="backup-model", tier="low", max_context=4096))
    failover = FailoverEngine(chat_callable=_ok_chat)
    facade = LLMRoutingFacade(smart=smart, scenario=ScenarioRouter(), failover=failover)

    # 高复杂度任务期望 high tier 的 primary-model
    result = facade.smart_route_and_call(RoutingRequest(query="hello", complexity=5))
    assert result["model"] == "primary-model"
    assert result["fallback_used"] is False
    assert "routing_decision" in result
    assert result["routing_decision"]["model_id"] == "primary-model"


def test_facade_scenario_route_and_call_end_to_end():
    scenario = ScenarioRouter()
    scenario.upsert_rule(RouteRule(
        id="chat-rule", task="聊天", task_type="chat",
        primary="chat-model", fallback="",
    ))
    failover = FailoverEngine(chat_callable=_ok_chat)
    facade = LLMRoutingFacade(smart=SmartRouter(), scenario=scenario, failover=failover)

    result = facade.scenario_route_and_call("chat", "你好")
    assert result["model"] == "chat-model"
    assert result["route_source"] == "scenario"
    assert "answer" in result


def test_facade_call_with_failover_mock_llm协同():
    """主模 mock-llm 调用成功（与 llm_gateway mock fallback 协同）."""
    # 这里直接注入 _ok_chat 模拟 mock-llm 调用成功
    failover = FailoverEngine(chat_callable=_ok_chat)
    result = failover.call_with_failover(
        "测试", primary="mock-llm", fallback="",
    )
    assert result["model"] == "mock-llm"
    assert "answer" in result
    assert result["fallback_used"] is False
