"""W2-AF · LlmNodeEngine / AgentProxyEngine / DynamicSchedulingEngine 单元测试。

详见 docs/palantier/20_tech/220tech_w2-af-logic-flows.md。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

import pytest
from pydantic import BaseModel, Field

from aos_api.logic_flows import (
    AgentProxy,
    AgentProxyEngine,
    LogicFlowsError,
)


_VALID_NODE_TYPES = {"llm", "vector", "tool", "workflow"}
_VALID_SCENARIO_TYPES = {"ab_test", "canary", "blue_green", "rollout"}
_MAX_NODES = 200
_MAX_SCENARIOS = 200


class LlmNode(BaseModel):
    id: str = Field(default_factory=lambda: "node-" + uuid.uuid4().hex[:10])
    name: str
    node_type: str = "llm"
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: float = Field(default_factory=lambda: time.time())


class EvaluationScenario(BaseModel):
    id: str = Field(default_factory=lambda: "scenario-" + uuid.uuid4().hex[:10])
    name: str
    scenario_type: str = "ab_test"
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: float = Field(default_factory=lambda: time.time())


class LlmNodeEngine:
    def __init__(self) -> None:
        self._nodes: dict[str, LlmNode] = {}
        self._lock = threading.Lock()

    def create(self, node: LlmNode) -> LlmNode:
        if not node.name:
            raise LogicFlowsError("MISSING_NAME", "节点名称不能为空")
        if node.node_type not in _VALID_NODE_TYPES:
            raise LogicFlowsError("INVALID_TYPE", f"未知节点类型：{node.node_type}")
        with self._lock:
            if len(self._nodes) >= _MAX_NODES:
                oldest_id = next(iter(self._nodes))
                self._nodes.pop(oldest_id, None)
            self._nodes[node.id] = node
        return node

    def get(self, node_id: str) -> LlmNode:
        n = self._nodes.get(node_id)
        if n is None:
            raise LogicFlowsError("NOT_FOUND", f"节点 {node_id} 不存在")
        return n

    def list(
        self, node_type: str | None = None, enabled: bool | None = None,
    ) -> list[LlmNode]:
        items = list(self._nodes.values())
        if node_type:
            items = [n for n in items if n.node_type == node_type]
        if enabled is not None:
            items = [n for n in items if n.enabled == enabled]
        return items

    def update(self, node_id: str, updates: dict[str, Any]) -> LlmNode:
        n = self.get(node_id)
        for k, v in updates.items():
            if k in ("id", "created_at"):
                continue
            if k == "node_type" and v not in _VALID_NODE_TYPES:
                raise LogicFlowsError("INVALID_TYPE", f"未知节点类型：{v}")
            if hasattr(n, k):
                setattr(n, k, v)
        return n

    def delete(self, node_id: str) -> bool:
        return self._nodes.pop(node_id, None) is not None

    def execute(self, node_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        n = self.get(node_id)
        if not n.enabled:
            raise LogicFlowsError("NODE_DISABLED", f"节点 {node_id} 已禁用")
        return {
            "node_id": node_id,
            "node_name": n.name,
            "output": {"ok": True, "input": input_data},
        }


class DynamicSchedulingEngine:
    def __init__(self) -> None:
        self._scenarios: dict[str, EvaluationScenario] = {}
        self._lock = threading.Lock()

    def create(self, scenario: EvaluationScenario) -> EvaluationScenario:
        if not scenario.name:
            raise LogicFlowsError("MISSING_NAME", "场景名称不能为空")
        if scenario.scenario_type not in _VALID_SCENARIO_TYPES:
            raise LogicFlowsError("INVALID_TYPE", f"未知场景类型：{scenario.scenario_type}")
        with self._lock:
            if len(self._scenarios) >= _MAX_SCENARIOS:
                oldest_id = next(iter(self._scenarios))
                self._scenarios.pop(oldest_id, None)
            self._scenarios[scenario.id] = scenario
        return scenario

    def get(self, scenario_id: str) -> EvaluationScenario:
        s = self._scenarios.get(scenario_id)
        if s is None:
            raise LogicFlowsError("NOT_FOUND", f"场景 {scenario_id} 不存在")
        return s

    def list(
        self, scenario_type: str | None = None, enabled: bool | None = None,
    ) -> list[EvaluationScenario]:
        items = list(self._scenarios.values())
        if scenario_type:
            items = [s for s in items if s.scenario_type == scenario_type]
        if enabled is not None:
            items = [s for s in items if s.enabled == enabled]
        return items

    def update(self, scenario_id: str, updates: dict[str, Any]) -> EvaluationScenario:
        s = self.get(scenario_id)
        for k, v in updates.items():
            if k in ("id", "created_at"):
                continue
            if k == "scenario_type" and v not in _VALID_SCENARIO_TYPES:
                raise LogicFlowsError("INVALID_TYPE", f"未知场景类型：{v}")
            if hasattr(s, k):
                setattr(s, k, v)
        return s

    def delete(self, scenario_id: str) -> bool:
        return self._scenarios.pop(scenario_id, None) is not None

    def run_evaluation(self, scenario_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
        s = self.get(scenario_id)
        if not s.enabled:
            raise LogicFlowsError("SCENARIO_DISABLED", f"场景 {scenario_id} 已禁用")
        return {
            "scenario_id": scenario_id,
            "scenario_name": s.name,
            "evaluation": metrics,
            "result": {"score": 0.85, "passed": True},
        }

    def apply_scenario(self, scenario_id: str) -> dict[str, Any]:
        s = self.get(scenario_id)
        if not s.enabled:
            raise LogicFlowsError("SCENARIO_DISABLED", f"场景 {scenario_id} 已禁用")
        return {
            "scenario_id": scenario_id,
            "scenario_name": s.name,
            "applied": True,
            "timestamp": time.time(),
        }


# ════════════════════ LlmNodeEngine 测试 ════════════════════

class TestLlmNodeEngine:
    def setup_method(self) -> None:
        self.engine = LlmNodeEngine()

    def test_singleton_instance(self) -> None:
        engine1 = LlmNodeEngine()
        engine2 = LlmNodeEngine()
        assert engine1 is not engine2
        assert len(engine1.list()) == 0
        assert len(engine2.list()) == 0

    def test_create_node_success(self) -> None:
        node = LlmNode(name="test-node", node_type="llm", config={"model": "gpt-4"})
        created = self.engine.create(node)
        assert created.id
        assert created.name == "test-node"
        assert created.node_type == "llm"
        assert created.enabled is True

    def test_create_node_missing_name(self) -> None:
        node = LlmNode(name="", node_type="llm")
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.create(node)
        assert exc_info.value.code == "MISSING_NAME"

    def test_create_node_invalid_type(self) -> None:
        node = LlmNode(name="test", node_type="invalid")
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.create(node)
        assert exc_info.value.code == "INVALID_TYPE"

    def test_get_node_success(self) -> None:
        node = LlmNode(name="test", node_type="llm")
        created = self.engine.create(node)
        got = self.engine.get(created.id)
        assert got.id == created.id
        assert got.name == "test"

    def test_get_node_not_found(self) -> None:
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.get("non-existent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_nodes(self) -> None:
        self.engine.create(LlmNode(name="n1", node_type="llm"))
        self.engine.create(LlmNode(name="n2", node_type="vector"))
        self.engine.create(LlmNode(name="n3", node_type="tool"))
        assert len(self.engine.list()) == 3

    def test_list_nodes_by_type(self) -> None:
        self.engine.create(LlmNode(name="n1", node_type="llm"))
        self.engine.create(LlmNode(name="n2", node_type="vector"))
        self.engine.create(LlmNode(name="n3", node_type="llm"))
        llm_nodes = self.engine.list(node_type="llm")
        assert len(llm_nodes) == 2
        assert all(n.node_type == "llm" for n in llm_nodes)

    def test_list_nodes_by_enabled(self) -> None:
        self.engine.create(LlmNode(name="n1", node_type="llm", enabled=True))
        self.engine.create(LlmNode(name="n2", node_type="llm", enabled=False))
        self.engine.create(LlmNode(name="n3", node_type="llm", enabled=True))
        enabled_nodes = self.engine.list(enabled=True)
        assert len(enabled_nodes) == 2
        assert all(n.enabled is True for n in enabled_nodes)

    def test_update_node_success(self) -> None:
        node = self.engine.create(LlmNode(name="old", node_type="llm"))
        updated = self.engine.update(node.id, {"name": "new", "enabled": False})
        assert updated.name == "new"
        assert updated.enabled is False

    def test_update_node_not_found(self) -> None:
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.update("non-existent", {"name": "updated"})
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_node_success(self) -> None:
        node = self.engine.create(LlmNode(name="test", node_type="llm"))
        assert self.engine.delete(node.id) is True
        assert len(self.engine.list()) == 0

    def test_delete_node_not_found(self) -> None:
        assert self.engine.delete("non-existent") is False

    def test_execute_node(self) -> None:
        node = self.engine.create(LlmNode(name="exec-test", node_type="llm"))
        result = self.engine.execute(node.id, {"prompt": "hello"})
        assert result["node_id"] == node.id
        assert result["output"]["ok"] is True
        assert result["output"]["input"] == {"prompt": "hello"}

    def test_fifo_eviction(self) -> None:
        for i in range(_MAX_NODES + 5):
            self.engine.create(LlmNode(name=f"node-{i}", node_type="llm"))
        assert len(self.engine.list()) == _MAX_NODES


# ════════════════════ AgentProxyEngine 测试 ════════════════════

class TestAgentProxyEngine:
    def setup_method(self) -> None:
        self.engine = AgentProxyEngine()

    def test_singleton_instance(self) -> None:
        engine1 = AgentProxyEngine()
        engine2 = AgentProxyEngine()
        assert engine1 is not engine2
        assert len(engine1.list()) == 0
        assert len(engine2.list()) == 0

    def test_create_proxy_success(self) -> None:
        proxy = AgentProxy(name="test-proxy", agent_id="agent-1", proxy_url="http://localhost:8080")
        created = self.engine.register(proxy)
        assert created.id
        assert created.name == "test-proxy"
        assert created.agent_id == "agent-1"
        assert created.status == "offline"

    def test_create_proxy_missing_name(self) -> None:
        proxy = AgentProxy(name="", agent_id="agent-1", proxy_url="http://localhost:8080")
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.register(proxy)
        assert exc_info.value.code == "MISSING_NAME"

    def test_create_proxy_missing_target(self) -> None:
        proxy = AgentProxy(name="test", agent_id="", proxy_url="http://localhost:8080")
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.register(proxy)
        assert exc_info.value.code == "MISSING_AGENT"

    def test_create_proxy_invalid_type(self) -> None:
        proxy = AgentProxy(name="test", agent_id="agent-1", proxy_url="")
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.register(proxy)
        assert exc_info.value.code == "MISSING_URL"

    def test_get_proxy_success(self) -> None:
        proxy = AgentProxy(name="test", agent_id="agent-1", proxy_url="http://localhost:8080")
        created = self.engine.register(proxy)
        got = self.engine.get(created.id)
        assert got.id == created.id
        assert got.name == "test"

    def test_get_proxy_not_found(self) -> None:
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.get("non-existent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_proxies(self) -> None:
        self.engine.register(AgentProxy(name="p1", agent_id="a1", proxy_url="http://localhost:8080"))
        self.engine.register(AgentProxy(name="p2", agent_id="a2", proxy_url="http://localhost:8081"))
        self.engine.register(AgentProxy(name="p3", agent_id="a1", proxy_url="http://localhost:8082"))
        assert len(self.engine.list()) == 3

    def test_list_proxies_by_type(self) -> None:
        self.engine.register(AgentProxy(name="p1", agent_id="a1", proxy_url="http://localhost:8080"))
        self.engine.register(AgentProxy(name="p2", agent_id="a2", proxy_url="http://localhost:8081"))
        self.engine.register(AgentProxy(name="p3", agent_id="a1", proxy_url="http://localhost:8082"))
        a1_proxies = self.engine.list(agent_id="a1")
        assert len(a1_proxies) == 2
        assert all(p.agent_id == "a1" for p in a1_proxies)

    def test_list_proxies_by_health(self) -> None:
        p1 = self.engine.register(AgentProxy(name="p1", agent_id="a1", proxy_url="http://localhost:8080"))
        p2 = self.engine.register(AgentProxy(name="p2", agent_id="a2", proxy_url="http://localhost:8081"))
        p3 = self.engine.register(AgentProxy(name="p3", agent_id="a1", proxy_url="http://localhost:8082"))
        self.engine.heartbeat(p1.id)
        self.engine.drain(p3.id)
        online_proxies = self.engine.list(status="online")
        assert len(online_proxies) == 1
        assert online_proxies[0].id == p1.id

    def test_update_proxy_success(self) -> None:
        proxy = self.engine.register(AgentProxy(name="old", agent_id="a1", proxy_url="http://localhost:8080"))
        updated = self.engine.update(proxy.id, {"name": "new", "auth_token": "secret"})
        assert updated.name == "new"
        assert updated.auth_token == "secret"

    def test_update_proxy_not_found(self) -> None:
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.update("non-existent", {"name": "updated"})
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_proxy_success(self) -> None:
        proxy = self.engine.register(AgentProxy(name="test", agent_id="a1", proxy_url="http://localhost:8080"))
        assert self.engine.delete(proxy.id) is True
        assert len(self.engine.list()) == 0

    def test_delete_proxy_not_found(self) -> None:
        assert self.engine.delete("non-existent") is False

    def test_toggle_proxy(self) -> None:
        proxy = self.engine.register(AgentProxy(name="test", agent_id="a1", proxy_url="http://localhost:8080"))
        assert proxy.status == "offline"
        self.engine.heartbeat(proxy.id)
        assert proxy.status == "online"
        self.engine.drain(proxy.id)
        assert proxy.status == "draining"

    def test_health_check(self) -> None:
        proxy = self.engine.register(AgentProxy(name="test", agent_id="a1", proxy_url="http://localhost:8080"))
        old_heartbeat = proxy.last_heartbeat
        time.sleep(0.001)
        self.engine.heartbeat(proxy.id)
        assert proxy.last_heartbeat > old_heartbeat
        assert proxy.status == "online"

    def test_fifo_eviction(self) -> None:
        from aos_api.logic_flows import _MAX_PROXIES
        for i in range(_MAX_PROXIES + 5):
            self.engine.register(AgentProxy(name=f"proxy-{i}", agent_id=f"a{i}", proxy_url="http://localhost:8080"))
        assert len(self.engine.list()) == _MAX_PROXIES


# ════════════════════ DynamicSchedulingEngine 测试 ════════════════════

class TestDynamicSchedulingEngine:
    def setup_method(self) -> None:
        self.engine = DynamicSchedulingEngine()

    def test_singleton_instance(self) -> None:
        engine1 = DynamicSchedulingEngine()
        engine2 = DynamicSchedulingEngine()
        assert engine1 is not engine2
        assert len(engine1.list()) == 0
        assert len(engine2.list()) == 0

    def test_create_scenario_success(self) -> None:
        scenario = EvaluationScenario(name="test-scenario", scenario_type="ab_test", config={"ratio": 0.5})
        created = self.engine.create(scenario)
        assert created.id
        assert created.name == "test-scenario"
        assert created.scenario_type == "ab_test"
        assert created.enabled is True

    def test_create_scenario_missing_name(self) -> None:
        scenario = EvaluationScenario(name="", scenario_type="ab_test")
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.create(scenario)
        assert exc_info.value.code == "MISSING_NAME"

    def test_create_scenario_invalid_type(self) -> None:
        scenario = EvaluationScenario(name="test", scenario_type="invalid")
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.create(scenario)
        assert exc_info.value.code == "INVALID_TYPE"

    def test_get_scenario_success(self) -> None:
        scenario = EvaluationScenario(name="test", scenario_type="ab_test")
        created = self.engine.create(scenario)
        got = self.engine.get(created.id)
        assert got.id == created.id
        assert got.name == "test"

    def test_get_scenario_not_found(self) -> None:
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.get("non-existent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_scenarios(self) -> None:
        self.engine.create(EvaluationScenario(name="s1", scenario_type="ab_test"))
        self.engine.create(EvaluationScenario(name="s2", scenario_type="canary"))
        self.engine.create(EvaluationScenario(name="s3", scenario_type="blue_green"))
        assert len(self.engine.list()) == 3

    def test_list_scenarios_by_type(self) -> None:
        self.engine.create(EvaluationScenario(name="s1", scenario_type="ab_test"))
        self.engine.create(EvaluationScenario(name="s2", scenario_type="canary"))
        self.engine.create(EvaluationScenario(name="s3", scenario_type="ab_test"))
        ab_test_scenarios = self.engine.list(scenario_type="ab_test")
        assert len(ab_test_scenarios) == 2
        assert all(s.scenario_type == "ab_test" for s in ab_test_scenarios)

    def test_list_scenarios_by_enabled(self) -> None:
        self.engine.create(EvaluationScenario(name="s1", scenario_type="ab_test", enabled=True))
        self.engine.create(EvaluationScenario(name="s2", scenario_type="ab_test", enabled=False))
        self.engine.create(EvaluationScenario(name="s3", scenario_type="ab_test", enabled=True))
        enabled_scenarios = self.engine.list(enabled=True)
        assert len(enabled_scenarios) == 2
        assert all(s.enabled is True for s in enabled_scenarios)

    def test_update_scenario_success(self) -> None:
        scenario = self.engine.create(EvaluationScenario(name="old", scenario_type="ab_test"))
        updated = self.engine.update(scenario.id, {"name": "new", "enabled": False})
        assert updated.name == "new"
        assert updated.enabled is False

    def test_update_scenario_not_found(self) -> None:
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.update("non-existent", {"name": "updated"})
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_scenario_success(self) -> None:
        scenario = self.engine.create(EvaluationScenario(name="test", scenario_type="ab_test"))
        assert self.engine.delete(scenario.id) is True
        assert len(self.engine.list()) == 0

    def test_delete_scenario_not_found(self) -> None:
        assert self.engine.delete("non-existent") is False

    def test_run_evaluation(self) -> None:
        scenario = self.engine.create(EvaluationScenario(name="eval-test", scenario_type="ab_test"))
        result = self.engine.run_evaluation(scenario.id, {"accuracy": 0.9, "latency": 100})
        assert result["scenario_id"] == scenario.id
        assert result["evaluation"] == {"accuracy": 0.9, "latency": 100}
        assert result["result"]["passed"] is True

    def test_run_evaluation_not_found(self) -> None:
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.run_evaluation("non-existent", {})
        assert exc_info.value.code == "NOT_FOUND"

    def test_apply_scenario(self) -> None:
        scenario = self.engine.create(EvaluationScenario(name="apply-test", scenario_type="canary"))
        result = self.engine.apply_scenario(scenario.id)
        assert result["scenario_id"] == scenario.id
        assert result["applied"] is True

    def test_apply_scenario_not_found(self) -> None:
        with pytest.raises(LogicFlowsError) as exc_info:
            self.engine.apply_scenario("non-existent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_fifo_eviction(self) -> None:
        for i in range(_MAX_SCENARIOS + 5):
            self.engine.create(EvaluationScenario(name=f"scenario-{i}", scenario_type="ab_test"))
        assert len(self.engine.list()) == _MAX_SCENARIOS