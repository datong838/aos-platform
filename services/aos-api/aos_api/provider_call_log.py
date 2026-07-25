"""Provider Call Log Engine — 222plan Phase A.

供应商调用日志引擎：记录每次 LLM 调用的元数据。

对应 222 文档第 23 章 Tab 4 调用日志。
从 FailoverEngine.CallRecord + LLM Gateway 调用中聚合。
"""
from __future__ import annotations

import secrets as _secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.provider_call_log")

_KV_KEY = "model_provider_call_logs"
_MAX_LOGS_PER_PROVIDER = 500


class ProviderCallLog(BaseModel):
    log_id: str
    provider_id: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    status: str = "success"  # success / failed / timeout
    trace_id: str = ""
    created_at: str = ""


class ProviderCallLogEngine:
    """Singleton + threading.Lock. In-memory with KV persistence."""

    _instance: ProviderCallLogEngine | None = None
    _lock = threading.Lock()

    def __new__(cls) -> ProviderCallLogEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    self = super().__new__(cls)
                    self._store: dict[str, list[ProviderCallLog]] = {}
                    self._load()
                    cls._instance = self
        return cls._instance

    def _load(self) -> None:
        from aos_api.aip_kv_store import get_payload

        raw = get_payload(_KV_KEY)
        if not raw or not isinstance(raw, dict):
            return
        by_id = raw.get("byProvider") or {}
        for pid, items in by_id.items():
            if not isinstance(items, list):
                continue
            logs = []
            for item in items:
                try:
                    logs.append(ProviderCallLog(**item))
                except Exception:
                    pass
            if logs:
                self._store[pid] = logs[-_MAX_LOGS_PER_PROVIDER:]
        log.info("call_log_load providers=%d", len(self._store))

    def _save(self) -> None:
        from aos_api.aip_kv_store import put_payload

        data = {
            "byProvider": {
                pid: [l.model_dump() for l in logs]
                for pid, logs in self._store.items()
            }
        }
        put_payload(_KV_KEY, data)

    def add_log(
        self,
        provider_id: str,
        model: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
        cost_usd: float = 0.0,
        status: str = "success",
        trace_id: str = "",
    ) -> ProviderCallLog:
        """Record a call log entry."""
        entry = ProviderCallLog(
            log_id=f"log_{_secrets.token_hex(8)}",
            provider_id=provider_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            status=status,
            trace_id=trace_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        logs = self._store.setdefault(provider_id, [])
        logs.append(entry)
        # Trim to max
        if len(logs) > _MAX_LOGS_PER_PROVIDER:
            self._store[provider_id] = logs[-_MAX_LOGS_PER_PROVIDER:]
        self._save()
        return entry

    def list_logs(
        self,
        provider_id: str,
        status_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProviderCallLog]:
        """List call logs with optional filtering. Newest first."""
        logs = list(self._store.get(provider_id, []))
        if status_filter:
            logs = [l for l in logs if l.status == status_filter]
        logs.reverse()  # Newest first
        return logs[offset : offset + limit]

    def get_stats(self, provider_id: str) -> dict[str, Any]:
        """Get aggregate stats for a provider."""
        logs = self._store.get(provider_id, [])
        if not logs:
            return {
                "total_calls": 0,
                "success": 0,
                "failed": 0,
                "timeout": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "avg_latency_ms": 0,
            }
        total = len(logs)
        success = sum(1 for l in logs if l.status == "success")
        failed = sum(1 for l in logs if l.status == "failed")
        timeout = sum(1 for l in logs if l.status == "timeout")
        tokens = sum(l.input_tokens + l.output_tokens for l in logs)
        cost = sum(l.cost_usd for l in logs)
        latency_vals = [l.latency_ms for l in logs if l.latency_ms > 0]
        avg_latency = sum(latency_vals) / len(latency_vals) if latency_vals else 0
        return {
            "total_calls": total,
            "success": success,
            "failed": failed,
            "timeout": timeout,
            "total_tokens": tokens,
            "total_cost_usd": round(cost, 4),
            "avg_latency_ms": round(avg_latency),
        }


_engine: ProviderCallLogEngine | None = None
_engine_lock = threading.Lock()


def get_call_log_engine() -> ProviderCallLogEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = ProviderCallLogEngine()
    return _engine
