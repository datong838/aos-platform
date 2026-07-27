"""Phase 3 · AIP Tools & Evals 引擎.

工具目录（7 类）+ 工具质量评分（总分+3子分）+ Eval 状态。
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()

TOOL_CATEGORIES = ["data", "build", "governance", "ai", "ops", "security", "integration"]


class QualityScore(BaseModel):
    tool_id: str = ""
    overall: float = 0.0  # 总分 0-100
    accuracy: float = 0.0  # 准确性
    latency: float = 0.0  # 延迟评分
    reliability: float = 0.0  # 可靠性
    evaluated_at: float = Field(default_factory=lambda: time.time())


class Tool(BaseModel):
    id: str = Field(default_factory=lambda: "aip-tool-" + uuid.uuid4().hex[:8])
    name: str = ""
    category: str = "data"
    description: str = ""
    version: str = "1.0.0"
    enabled: bool = True
    config_schema: dict[str, Any] = Field(default_factory=dict)
    quality: QualityScore | None = None
    calls: int = 0
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class EvalRecord(BaseModel):
    id: str = Field(default_factory=lambda: "aip-eval-" + uuid.uuid4().hex[:8])
    name: str = ""
    eval_type: str = "tool"  # tool | rag | gen | l4
    target_id: str = ""  # 被评估的对象 id
    status: str = "pending"  # pending | running | passed | failed
    score: float = 0.0
    l4_allowed: bool = False  # 是否允许进入 L4 自动化
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class CircuitRecord(BaseModel):
    id: str = Field(default_factory=lambda: "aip-circuit-" + uuid.uuid4().hex[:8])
    tool_id: str = ""
    reason: str = ""
    state: str = "closed"  # closed | open | half_open
    trip_count: int = 0
    created_at: float = Field(default_factory=lambda: time.time())


class ToolsEngine:
    """AIP Tools & Evals 引擎。"""

    _instance: "ToolsEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "ToolsEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tools: dict[str, Tool] = {}
                    cls._instance._evals: dict[str, EvalRecord] = {}
                    cls._instance._circuits: dict[str, CircuitRecord] = {}
        return cls._instance

    # ── Tools ──
    def create_tool(self, name: str, **kwargs: Any) -> Tool:
        with _LOCK:
            tool = Tool(name=name, **kwargs)
            self._tools[tool.id] = tool
            return tool

    def get_tool(self, tool_id: str) -> Tool | None:
        return self._tools.get(tool_id)

    def list_tools(self, category: str | None = None, enabled: bool | None = None) -> list[Tool]:
        items = list(self._tools.values())
        if category:
            items = [t for t in items if t.category == category]
        if enabled is not None:
            items = [t for t in items if t.enabled == enabled]
        return items

    def update_tool(self, tool_id: str, **kwargs: Any) -> Tool:
        with _LOCK:
            tool = self._tools.get(tool_id)
            if tool is None:
                raise KeyError(f"Tool {tool_id} not found")
            for k, v in kwargs.items():
                if hasattr(tool, k):
                    setattr(tool, k, v)
            tool.updated_at = time.time()
            return tool

    def delete_tool(self, tool_id: str) -> bool:
        with _LOCK:
            return self._tools.pop(tool_id, None) is not None

    # ── Quality ──
    def get_quality(self, tool_id: str) -> QualityScore | None:
        tool = self._tools.get(tool_id)
        return tool.quality if tool else None

    def set_quality(self, tool_id: str, overall: float, accuracy: float, latency: float, reliability: float) -> Tool:
        with _LOCK:
            tool = self._tools.get(tool_id)
            if tool is None:
                raise KeyError(f"Tool {tool_id} not found")
            tool.quality = QualityScore(
                tool_id=tool_id, overall=overall,
                accuracy=accuracy, latency=latency, reliability=reliability,
            )
            tool.updated_at = time.time()
            return tool

    # ── Evals ──
    def create_eval(self, name: str, **kwargs: Any) -> EvalRecord:
        with _LOCK:
            ev = EvalRecord(name=name, **kwargs)
            self._evals[ev.id] = ev
            return ev

    def get_eval(self, eval_id: str) -> EvalRecord | None:
        return self._evals.get(eval_id)

    def list_evals(self, eval_type: str | None = None, status: str | None = None) -> list[EvalRecord]:
        items = list(self._evals.values())
        if eval_type:
            items = [e for e in items if e.eval_type == eval_type]
        if status:
            items = [e for e in items if e.status == status]
        return items

    def update_eval(self, eval_id: str, **kwargs: Any) -> EvalRecord:
        with _LOCK:
            ev = self._evals.get(eval_id)
            if ev is None:
                raise KeyError(f"Eval {eval_id} not found")
            for k, v in kwargs.items():
                if hasattr(ev, k):
                    setattr(ev, k, v)
            ev.updated_at = time.time()
            return ev

    def delete_eval(self, eval_id: str) -> bool:
        with _LOCK:
            return self._evals.pop(eval_id, None) is not None

    # ── Circuit ──
    def trip_circuit(self, tool_id: str, reason: str) -> CircuitRecord:
        with _LOCK:
            rec = CircuitRecord(tool_id=tool_id, reason=reason, state="open", trip_count=1)
            self._circuits[rec.id] = rec
            # 禁用对应工具
            tool = self._tools.get(tool_id)
            if tool:
                tool.enabled = False
            return rec

    def list_circuits(self) -> list[CircuitRecord]:
        return list(self._circuits.values())

    def reset_circuit(self, circuit_id: str) -> CircuitRecord:
        with _LOCK:
            rec = self._circuits.get(circuit_id)
            if rec is None:
                raise KeyError(f"Circuit {circuit_id} not found")
            rec.state = "closed"
            tool = self._tools.get(rec.tool_id)
            if tool:
                tool.enabled = True
            return rec

    def reset(self) -> None:
        with _LOCK:
            self._tools.clear()
            self._evals.clear()
            self._circuits.clear()


def get_engine() -> ToolsEngine:
    return ToolsEngine()
