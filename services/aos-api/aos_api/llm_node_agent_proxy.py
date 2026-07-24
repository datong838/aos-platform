"""LLM Node + Agent Proxy + Dynamic Scheduling 引擎组合模块。"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


_MAX_ITEMS = 200


class LlmNodeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class AgentProxyError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class SchedulingScenarioError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ────────────────────────────────────────────────────────────────
# LlmNodeEngine — LLM 节点引擎
# ────────────────────────────────────────────────────────────────

LlmNodeType = Literal["entity_extraction", "visual_template", "text_classification", "summarization"]


class LlmNode(BaseModel):
    node_id: str = Field(default_factory=lambda: _new_id("ln"))
    name: str
    node_type: LlmNodeType
    prompt_template: str = ""
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


_VALID_NODE_TYPES = {"entity_extraction", "visual_template", "text_classification", "summarization"}


class LlmNodeEngine:
    def __init__(self) -> None:
        self._nodes: dict[str, LlmNode] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def create_node(self, name: str, node_type: str, **kwargs: Any) -> LlmNode:
        if not name:
            raise LlmNodeError("MISSING_NAME", "节点名称不能为空")
        if node_type not in _VALID_NODE_TYPES:
            raise LlmNodeError("INVALID_NODE_TYPE", f"无效节点类型: {node_type}（合法: {sorted(_VALID_NODE_TYPES)}）")

        node = LlmNode(name=name, node_type=node_type, **kwargs)
        with self._lock:
            self._nodes[node.node_id] = node
            self._order.append(node.node_id)
            if len(self._order) > _MAX_ITEMS:
                oldest = self._order.pop(0)
                self._nodes.pop(oldest, None)
        return node

    def get_node(self, node_id: str) -> LlmNode:
        with self._lock:
            node = self._nodes.get(node_id)
        if node is None:
            raise LlmNodeError("NOT_FOUND", f"节点 {node_id} 不存在")
        return node

    def list_nodes(self, node_type: str | None = None, enabled: bool | None = None) -> list[LlmNode]:
        with self._lock:
            items = list(self._nodes.values())
        if node_type:
            items = [n for n in items if n.node_type == node_type]
        if enabled is not None:
            items = [n for n in items if n.enabled == enabled]
        return items

    def update_node(self, node_id: str, **kwargs: Any) -> LlmNode:
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                raise LlmNodeError("NOT_FOUND", f"节点 {node_id} 不存在")
            for k, v in kwargs.items():
                if hasattr(node, k):
                    setattr(node, k, v)
            node.updated_at = _now_iso()
        return node

    def delete_node(self, node_id: str) -> bool:
        with self._lock:
            node = self._nodes.pop(node_id, None)
            if node is None:
                return False
            try:
                self._order.remove(node_id)
            except ValueError:
                pass
            return True

    def execute_node(self, node_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        node = self.get_node(node_id)
        if not node.enabled:
            raise LlmNodeError("NOT_FOUND", f"节点 {node_id} 已禁用")
        return {
            "node_id": node.node_id,
            "node_name": node.name,
            "node_type": node.node_type,
            "input": input_data,
            "output": {
                "status": "success",
                "result": f"[模拟执行] {node.node_type} 节点处理完成",
                "processed_at": _now_iso(),
            },
        }


# ────────────────────────────────────────────────────────────────
# AgentProxyEngine — Agent Proxy/Worker 引擎
# ────────────────────────────────────────────────────────────────

ProxyType = Literal["reverse_proxy", "forward_proxy", "load_balancer"]
HealthStatus = Literal["healthy", "unhealthy", "degraded"]


class AgentProxy(BaseModel):
    proxy_id: str = Field(default_factory=lambda: _new_id("ap"))
    name: str
    proxy_type: ProxyType
    target_url: str
    listen_port: int
    enabled: bool = True
    health_status: HealthStatus = "healthy"
    last_health_check_at: str | None = None
    error_message: str = ""
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


_VALID_PROXY_TYPES = {"reverse_proxy", "forward_proxy", "load_balancer"}


class AgentProxyEngine:
    def __init__(self) -> None:
        self._proxies: dict[str, AgentProxy] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def create_proxy(self, name: str, proxy_type: str, target_url: str, listen_port: int, **kwargs: Any) -> AgentProxy:
        if not name:
            raise AgentProxyError("MISSING_NAME", "代理名称不能为空")
        if not target_url:
            raise AgentProxyError("MISSING_TARGET_URL", "目标 URL 不能为空")
        if proxy_type not in _VALID_PROXY_TYPES:
            raise AgentProxyError("INVALID_PROXY_TYPE", f"无效代理类型: {proxy_type}（合法: {sorted(_VALID_PROXY_TYPES)}）")

        proxy = AgentProxy(
            name=name,
            proxy_type=proxy_type,
            target_url=target_url,
            listen_port=listen_port,
            **kwargs,
        )
        with self._lock:
            self._proxies[proxy.proxy_id] = proxy
            self._order.append(proxy.proxy_id)
            if len(self._order) > _MAX_ITEMS:
                oldest = self._order.pop(0)
                self._proxies.pop(oldest, None)
        return proxy

    def get_proxy(self, proxy_id: str) -> AgentProxy:
        with self._lock:
            proxy = self._proxies.get(proxy_id)
        if proxy is None:
            raise AgentProxyError("NOT_FOUND", f"代理 {proxy_id} 不存在")
        return proxy

    def list_proxies(self, proxy_type: str | None = None, health_status: str | None = None) -> list[AgentProxy]:
        with self._lock:
            items = list(self._proxies.values())
        if proxy_type:
            items = [p for p in items if p.proxy_type == proxy_type]
        if health_status:
            items = [p for p in items if p.health_status == health_status]
        return items

    def update_proxy(self, proxy_id: str, **kwargs: Any) -> AgentProxy:
        with self._lock:
            proxy = self._proxies.get(proxy_id)
            if proxy is None:
                raise AgentProxyError("NOT_FOUND", f"代理 {proxy_id} 不存在")
            for k, v in kwargs.items():
                if hasattr(proxy, k):
                    setattr(proxy, k, v)
            proxy.updated_at = _now_iso()
        return proxy

    def delete_proxy(self, proxy_id: str) -> bool:
        with self._lock:
            proxy = self._proxies.pop(proxy_id, None)
            if proxy is None:
                return False
            try:
                self._order.remove(proxy_id)
            except ValueError:
                pass
            return True

    def toggle_proxy(self, proxy_id: str) -> AgentProxy:
        with self._lock:
            proxy = self._proxies.get(proxy_id)
            if proxy is None:
                raise AgentProxyError("NOT_FOUND", f"代理 {proxy_id} 不存在")
            proxy.enabled = not proxy.enabled
            proxy.updated_at = _now_iso()
        return proxy

    def health_check(self, proxy_id: str) -> AgentProxy:
        with self._lock:
            proxy = self._proxies.get(proxy_id)
            if proxy is None:
                raise AgentProxyError("NOT_FOUND", f"代理 {proxy_id} 不存在")
            proxy.health_status = "healthy"
            proxy.last_health_check_at = _now_iso()
            proxy.error_message = ""
        return proxy


# ────────────────────────────────────────────────────────────────
# DynamicSchedulingEngine — 动态调度场景引擎
# ────────────────────────────────────────────────────────────────

ScenarioType = Literal["sandbox", "staging", "save_action", "custom_save"]


class SchedulingScenario(BaseModel):
    scenario_id: str = Field(default_factory=lambda: _new_id("ds"))
    name: str
    scenario_type: ScenarioType
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    suggestion_rules: list[dict[str, Any]] = Field(default_factory=list)
    search_rules: list[dict[str, Any]] = Field(default_factory=list)
    realtime_evaluation: bool = False
    enabled: bool = True
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


_VALID_SCENARIO_TYPES = {"sandbox", "staging", "save_action", "custom_save"}


class DynamicSchedulingEngine:
    def __init__(self) -> None:
        self._scenarios: dict[str, SchedulingScenario] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def create_scenario(self, name: str, scenario_type: str, **kwargs: Any) -> SchedulingScenario:
        if not name:
            raise SchedulingScenarioError("MISSING_NAME", "场景名称不能为空")
        if scenario_type not in _VALID_SCENARIO_TYPES:
            raise SchedulingScenarioError("INVALID_SCENARIO_TYPE", f"无效场景类型: {scenario_type}（合法: {sorted(_VALID_SCENARIO_TYPES)}）")

        scenario = SchedulingScenario(name=name, scenario_type=scenario_type, **kwargs)
        with self._lock:
            self._scenarios[scenario.scenario_id] = scenario
            self._order.append(scenario.scenario_id)
            if len(self._order) > _MAX_ITEMS:
                oldest = self._order.pop(0)
                self._scenarios.pop(oldest, None)
        return scenario

    def get_scenario(self, scenario_id: str) -> SchedulingScenario:
        with self._lock:
            scenario = self._scenarios.get(scenario_id)
        if scenario is None:
            raise SchedulingScenarioError("NOT_FOUND", f"场景 {scenario_id} 不存在")
        return scenario

    def list_scenarios(self, scenario_type: str | None = None, enabled: bool | None = None) -> list[SchedulingScenario]:
        with self._lock:
            items = list(self._scenarios.values())
        if scenario_type:
            items = [s for s in items if s.scenario_type == scenario_type]
        if enabled is not None:
            items = [s for s in items if s.enabled == enabled]
        return items

    def update_scenario(self, scenario_id: str, **kwargs: Any) -> SchedulingScenario:
        with self._lock:
            scenario = self._scenarios.get(scenario_id)
            if scenario is None:
                raise SchedulingScenarioError("NOT_FOUND", f"场景 {scenario_id} 不存在")
            for k, v in kwargs.items():
                if hasattr(scenario, k):
                    setattr(scenario, k, v)
            scenario.updated_at = _now_iso()
        return scenario

    def delete_scenario(self, scenario_id: str) -> bool:
        with self._lock:
            scenario = self._scenarios.pop(scenario_id, None)
            if scenario is None:
                return False
            try:
                self._order.remove(scenario_id)
            except ValueError:
                pass
            return True

    def run_evaluation(self, scenario_id: str) -> dict[str, Any]:
        scenario = self.get_scenario(scenario_id)
        if not scenario.enabled:
            raise SchedulingScenarioError("NOT_FOUND", f"场景 {scenario_id} 已禁用")
        return {
            "scenario_id": scenario.scenario_id,
            "scenario_name": scenario.name,
            "scenario_type": scenario.scenario_type,
            "evaluation": {
                "status": "completed",
                "constraints_passed": len(scenario.constraints),
                "suggestions_applied": len(scenario.suggestion_rules),
                "search_hits": len(scenario.search_rules),
                "score": 85.0,
                "evaluated_at": _now_iso(),
            },
        }

    def apply_scenario(self, scenario_id: str) -> dict[str, Any]:
        scenario = self.get_scenario(scenario_id)
        if not scenario.enabled:
            raise SchedulingScenarioError("NOT_FOUND", f"场景 {scenario_id} 已禁用")
        return {
            "scenario_id": scenario.scenario_id,
            "scenario_name": scenario.name,
            "applied": True,
            "applied_at": _now_iso(),
        }


# ────────────────────────────────────────────────────────────────
# 单例 getters（双重检查锁）
# ────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_llm_node_engine: LlmNodeEngine | None = None
_agent_proxy_engine: AgentProxyEngine | None = None
_dynamic_scheduling_engine: DynamicSchedulingEngine | None = None


def get_llm_node_engine() -> LlmNodeEngine:
    global _llm_node_engine
    if _llm_node_engine is None:
        with _lock:
            if _llm_node_engine is None:
                _llm_node_engine = LlmNodeEngine()
    return _llm_node_engine


def get_agent_proxy_engine() -> AgentProxyEngine:
    global _agent_proxy_engine
    if _agent_proxy_engine is None:
        with _lock:
            if _agent_proxy_engine is None:
                _agent_proxy_engine = AgentProxyEngine()
    return _agent_proxy_engine


def get_dynamic_scheduling_engine() -> DynamicSchedulingEngine:
    global _dynamic_scheduling_engine
    if _dynamic_scheduling_engine is None:
        with _lock:
            if _dynamic_scheduling_engine is None:
                _dynamic_scheduling_engine = DynamicSchedulingEngine()
    return _dynamic_scheduling_engine