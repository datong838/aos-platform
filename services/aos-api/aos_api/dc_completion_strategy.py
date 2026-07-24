"""W3 Task 1.1 · Completion Strategy 完成策略引擎（220w L156）.

四种触发策略：ON_SUCCESS / ON_FAILURE / ALWAYS / NEVER
支持 cooldown 冷却期和 max_retries 最大重试次数。
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel

_MAX_STRATEGIES = 200
_VALID_TRIGGERS = {"ON_SUCCESS", "ON_FAILURE", "ALWAYS", "NEVER"}
_VALID_TASK_RESULTS = {"SUCCESS", "FAILURE", "TIMEOUT", "CANCELLED"}


def _utcnow() -> datetime:
    return datetime.utcnow()


# ════════════════════ Models ════════════════════

class CompletionStrategy(BaseModel):
    strategy_id: str = ""
    name: str
    trigger: str = "ON_SUCCESS"  # ON_SUCCESS | ON_FAILURE | ALWAYS | NEVER
    downstream_task_ids: list[str] = []
    cooldown_seconds: int = 0
    max_retries: int = 3
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CompletionStrategyError(Exception):
    """完成策略错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════ Engine ════════════════════

class CompletionStrategyEngine:
    """Completion Strategy 完成策略引擎."""

    _instance: Optional[CompletionStrategyEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._strategies: dict[str, CompletionStrategy] = {}
        self._last_fired: dict[str, datetime] = {}  # strategy_id → last fire time
        self._fire_counts: dict[str, int] = {}  # strategy_id → fire count
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> CompletionStrategyEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── CRUD ──

    def register(self, strategy: CompletionStrategy) -> CompletionStrategy:
        if not strategy.name or not strategy.name.strip():
            raise CompletionStrategyError("MISSING_NAME", "name is required")
        if strategy.trigger not in _VALID_TRIGGERS:
            raise CompletionStrategyError(
                "INVALID_TRIGGER",
                f"trigger must be one of {_VALID_TRIGGERS}",
            )
        now = _utcnow()
        sid = f"cs-{uuid.uuid4().hex[:8]}"
        stored = strategy.model_copy(
            update={
                "strategy_id": sid,
                "created_at": now,
                "updated_at": now,
            }
        )
        with self._lock:
            if len(self._strategies) >= _MAX_STRATEGIES:
                oldest = min(
                    self._strategies.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._strategies[oldest.strategy_id]
                self._last_fired.pop(oldest.strategy_id, None)
                self._fire_counts.pop(oldest.strategy_id, None)
            self._strategies[sid] = stored
            self._fire_counts[sid] = 0
        return stored

    def get(self, strategy_id: str) -> CompletionStrategy:
        with self._lock:
            s = self._strategies.get(strategy_id)
        if s is None:
            raise CompletionStrategyError("NOT_FOUND", f"strategy {strategy_id} not found")
        return s

    def list(
        self,
        trigger: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> list[CompletionStrategy]:
        with self._lock:
            items = list(self._strategies.values())
        if trigger:
            items = [s for s in items if s.trigger == trigger]
        if enabled is not None:
            items = [s for s in items if s.enabled == enabled]
        return items

    def update(self, strategy_id: str, patch: dict) -> CompletionStrategy:
        with self._lock:
            s = self._strategies.get(strategy_id)
        if s is None:
            raise CompletionStrategyError("NOT_FOUND", f"strategy {strategy_id} not found")
        if "trigger" in patch and patch["trigger"] not in _VALID_TRIGGERS:
            raise CompletionStrategyError(
                "INVALID_TRIGGER",
                f"trigger must be one of {_VALID_TRIGGERS}",
            )
        updated = s.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._strategies[strategy_id] = updated
        return updated

    def delete(self, strategy_id: str) -> None:
        with self._lock:
            if strategy_id not in self._strategies:
                raise CompletionStrategyError("NOT_FOUND", f"strategy {strategy_id} not found")
            del self._strategies[strategy_id]
            self._last_fired.pop(strategy_id, None)
            self._fire_counts.pop(strategy_id, None)

    # ── evaluate 评估 ──

    def evaluate(self, task_id: str, task_result: str) -> list[str]:
        """根据任务执行结果，返回应触发的下游 task_id 列表."""
        if task_result not in _VALID_TASK_RESULTS:
            raise CompletionStrategyError(
                "INVALID_RESULT",
                f"task_result must be one of {_VALID_TASK_RESULTS}",
            )

        triggered: list[str] = []
        now = _utcnow()

        with self._lock:
            strategies_snapshot = list(self._strategies.values())

        for s in strategies_snapshot:
            if not s.enabled:
                continue

            # 触发条件判断
            should_fire = False
            if s.trigger == "ALWAYS":
                should_fire = True
            elif s.trigger == "NEVER":
                should_fire = False
            elif s.trigger == "ON_SUCCESS":
                should_fire = task_result == "SUCCESS"
            elif s.trigger == "ON_FAILURE":
                should_fire = task_result in ("FAILURE", "TIMEOUT")

            if not should_fire:
                continue

            # 重试次数限制
            if self._fire_counts.get(s.strategy_id, 0) >= s.max_retries:
                continue

            # 冷却期检查
            last = self._last_fired.get(s.strategy_id)
            if last and s.cooldown_seconds > 0:
                elapsed = (now - last).total_seconds()
                if elapsed < s.cooldown_seconds:
                    continue

            # 通过所有检查 → 触发
            triggered.extend(s.downstream_task_ids)
            with self._lock:
                self._last_fired[s.strategy_id] = now
                self._fire_counts[s.strategy_id] = self._fire_counts.get(s.strategy_id, 0) + 1

        return triggered


# ════════════════════ Singleton helper ════════════════════

def get_engine() -> CompletionStrategyEngine:
    return CompletionStrategyEngine.get_instance()
