"""Phase 3 · AIP Agents 引擎.

Agent 列表（含 source/tags/calls 统计）+ prompt + tools + guardrails。
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()


class GuardrailRule(BaseModel):
    id: str = ""
    name: str = ""
    type: str = "content_filter"  # content_filter | pii | injection | token_limit
    action: str = "block"  # block | warn | redact
    enabled: bool = True


class ToolRef(BaseModel):
    id: str = ""
    name: str = ""
    category: str = ""
    enabled: bool = True


class Agent(BaseModel):
    id: str = Field(default_factory=lambda: "aip-agent-" + uuid.uuid4().hex[:8])
    name: str = ""
    description: str = ""
    source: str = "platform"  # platform | marketplace | custom
    tags: list[str] = Field(default_factory=list)
    status: str = "active"  # active | draft | archived
    system_prompt: str = ""
    tools: list[ToolRef] = Field(default_factory=list)
    guardrails: list[GuardrailRule] = Field(default_factory=list)
    calls: int = 0
    success_rate: float = 1.0
    avg_latency_ms: int = 0
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class AgentsEngine:
    """AIP Agents 引擎。Singleton + threading.Lock。"""

    _instance: "AgentsEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "AgentsEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._agents: dict[str, Agent] = {}
        return cls._instance

    def create(self, name: str, **kwargs: Any) -> Agent:
        with _LOCK:
            agent = Agent(name=name, **kwargs)
            self._agents[agent.id] = agent
            return agent

    def get(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def list(self, source: str | None = None, tag: str | None = None, status: str | None = None) -> list[Agent]:
        items = list(self._agents.values())
        if source:
            items = [a for a in items if a.source == source]
        if tag:
            items = [a for a in items if tag in a.tags]
        if status:
            items = [a for a in items if a.status == status]
        return items

    def update(self, agent_id: str, **kwargs: Any) -> Agent:
        with _LOCK:
            agent = self._agents.get(agent_id)
            if agent is None:
                raise KeyError(f"Agent {agent_id} not found")
            for k, v in kwargs.items():
                if hasattr(agent, k):
                    setattr(agent, k, v)
            agent.updated_at = time.time()
            return agent

    def delete(self, agent_id: str) -> bool:
        with _LOCK:
            return self._agents.pop(agent_id, None) is not None

    # ── Prompt ──
    def get_prompt(self, agent_id: str) -> str | None:
        agent = self._agents.get(agent_id)
        return agent.system_prompt if agent else None

    def set_prompt(self, agent_id: str, prompt: str) -> Agent:
        return self.update(agent_id, system_prompt=prompt)

    # ── Tools ──
    def list_tools(self, agent_id: str) -> list[ToolRef]:
        agent = self._agents.get(agent_id)
        return list(agent.tools) if agent else []

    # ── Guardrails ──
    def get_guardrails(self, agent_id: str) -> list[GuardrailRule]:
        agent = self._agents.get(agent_id)
        return list(agent.guardrails) if agent else []

    def set_guardrails(self, agent_id: str, rules: list[dict[str, Any]]) -> Agent:
        gr = [GuardrailRule(**r) for r in rules]
        return self.update(agent_id, guardrails=gr)

    # ── Stats ──
    def stats(self) -> dict[str, Any]:
        items = list(self._agents.values())
        total_calls = sum(a.calls for a in items)
        by_source: dict[str, int] = {}
        for a in items:
            by_source[a.source] = by_source.get(a.source, 0) + 1
        return {
            "total": len(items),
            "total_calls": total_calls,
            "by_source": by_source,
            "avg_success_rate": sum(a.success_rate for a in items) / len(items) if items else 0,
        }

    def reset(self) -> None:
        with _LOCK:
            self._agents.clear()


def get_engine() -> AgentsEngine:
    return AgentsEngine()
