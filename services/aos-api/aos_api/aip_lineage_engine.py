"""Phase 3 · AIP Lineage 引擎.

决策 Trace（6 段：输入/检索/推理/熔断/输出/回填）。
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()

TRACE_SEGMENTS = ["input", "retrieval", "reasoning", "circuit", "output", "writeback"]


class TraceSegment(BaseModel):
    name: str  # input | retrieval | reasoning | circuit | output | writeback
    status: str = "ok"  # ok | warning | error | skipped
    duration_ms: int = 0
    detail: dict[str, Any] = Field(default_factory=dict)


class LineageRecord(BaseModel):
    id: str = Field(default_factory=lambda: "aip-lineage-" + uuid.uuid4().hex[:8])
    trace_id: str = ""
    agent_id: str = ""
    query: str = ""
    segments: list[TraceSegment] = Field(default_factory=list)
    total_duration_ms: int = 0
    tokens_used: int = 0
    status: str = "ok"  # ok | degraded | failed
    created_at: float = Field(default_factory=lambda: time.time())


class LineageEngine:
    """AIP Lineage 引擎。"""

    _instance: "LineageEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "LineageEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._records: dict[str, LineageRecord] = {}
        return cls._instance

    def create(self, agent_id: str = "", query: str = "", **kwargs: Any) -> LineageRecord:
        with _LOCK:
            rec = LineageRecord(agent_id=agent_id, query=query, **kwargs)
            if not rec.trace_id:
                rec.trace_id = "trace-" + uuid.uuid4().hex[:12]
            self._records[rec.id] = rec
            return rec

    def get(self, record_id: str) -> LineageRecord | None:
        return self._records.get(record_id)

    def list(self, agent_id: str | None = None, status: str | None = None) -> list[LineageRecord]:
        items = list(self._records.values())
        if agent_id:
            items = [r for r in items if r.agent_id == agent_id]
        if status:
            items = [r for r in items if r.status == status]
        return items

    def update(self, record_id: str, **kwargs: Any) -> LineageRecord:
        with _LOCK:
            rec = self._records.get(record_id)
            if rec is None:
                raise KeyError(f"Lineage record {record_id} not found")
            for k, v in kwargs.items():
                if hasattr(rec, k):
                    setattr(rec, k, v)
            return rec

    def delete(self, record_id: str) -> bool:
        with _LOCK:
            return self._records.pop(record_id, None) is not None

    def build_default_trace(self, agent_id: str, query: str) -> list[TraceSegment]:
        """构建标准 6 段 trace。"""
        return [
            TraceSegment(name="input", status="ok", duration_ms=12,
                         detail={"query_length": len(query), "role": "user"}),
            TraceSegment(name="retrieval", status="ok", duration_ms=45,
                         detail={"sources": 3, "chunks_retrieved": 8}),
            TraceSegment(name="reasoning", status="ok", duration_ms=320,
                         detail={"model": "gpt-4o", "tokens": 347, "cot_steps": 4}),
            TraceSegment(name="circuit", status="ok", duration_ms=5,
                         detail={"breaker_state": "closed", "limits_checked": 3}),
            TraceSegment(name="output", status="ok", duration_ms=18,
                         detail={"response_length": 256, "format": "text"}),
            TraceSegment(name="writeback", status="ok", duration_ms=30,
                         detail={"conversation_updated": True, "memory_stored": True}),
        ]

    def stats(self) -> dict[str, Any]:
        items = list(self._records.values())
        by_status: dict[str, int] = {}
        total_duration = 0
        for r in items:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            total_duration += r.total_duration_ms
        return {
            "total": len(items),
            "by_status": by_status,
            "avg_duration_ms": total_duration / len(items) if items else 0,
        }

    def reset(self) -> None:
        with _LOCK:
            self._records.clear()


def get_engine() -> LineageEngine:
    return LineageEngine()
