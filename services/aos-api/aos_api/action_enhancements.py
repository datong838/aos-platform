"""W2-#54/#55/#56/#57/#76 · Action 增强组。

五项功能合一：
  - #54 Side Effects: Notification/Webhook 副作用
  - #55 Optimistic UI: 乐观 UI 前置提交 + 失败回滚
  - #56 Soft Delete: Action 层软删除（复用 writeback）
  - #57 Effect Retry: 副作用重试 ×3 → DLQ 死信队列
  - #76 Merge Strategy: 字段级合并 / LastWriteWins / 人工仲裁
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── #54 Side Effects ──


class EffectType(str, Enum):
    NOTIFICATION = "notification"
    WEBHOOK = "webhook"


class ActionEffect(BaseModel):
    id: str = Field(default_factory=lambda: "eff-" + uuid.uuid4().hex[:8])
    action_type_id: str
    type: EffectType
    config: dict[str, Any] = Field(default_factory=dict)
    retry: int = 3
    enabled: bool = True


class EffectResult(BaseModel):
    effect_id: str
    status: Literal["success", "failed", "pending", "dlq"]
    message: str = ""
    attempt: int = 0


# ── #55 Optimistic UI ──


class OptimisticToken(BaseModel):
    token: str = Field(default_factory=lambda: "opt-" + uuid.uuid4().hex[:12])
    action_type_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=_now)
    rollback_key: str | None = None


class OptimisticResult(BaseModel):
    ok: bool
    token: str
    rollback_required: bool = False
    rollback_payload: dict[str, Any] | None = None


# ── #56 Soft Delete（复用 writeback）──


# ── #57 DLQ ──


class DLQEntry(BaseModel):
    id: str = Field(default_factory=lambda: "dlq-" + uuid.uuid4().hex[:8])
    effect_id: str
    action_type_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    attempts: int = 0
    max_attempts: int = 3
    last_error: str = ""
    enqueued_at: str = Field(default_factory=_now)
    next_retry_at: str | None = None


# ── #76 Merge Strategy ──


class MergeStrategy(str, Enum):
    FIELD_LEVEL = "field_level"
    LAST_WRITE_WINS = "last_write_wins"
    MANUAL_ARBITRATION = "manual_arbitration"


class MergeConflict(BaseModel):
    field: str
    current_value: Any
    incoming_value: Any


class MergeResult(BaseModel):
    merged: dict[str, Any] = Field(default_factory=dict)
    strategy: MergeStrategy
    conflicts: list[MergeConflict] = Field(default_factory=list)


# ── 引擎 ──


class ActionEnhancementError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ActionEnhancementEngine:
    def __init__(self) -> None:
        self._effects: dict[str, ActionEffect] = {}
        self._optimistic_tokens: dict[str, OptimisticToken] = {}
        self._dlq: dict[str, DLQEntry] = {}
        self._notification_log: list[dict[str, Any]] = []
        self._webhook_log: list[dict[str, Any]] = []

    # ── #54 Side Effects ──

    def create_effect(self, effect: ActionEffect) -> ActionEffect:
        if not effect.action_type_id:
            raise ActionEnhancementError("MISSING_ACTION", "effect 缺少 action_type_id")
        self._effects[effect.id] = effect
        return effect

    def get_effect(self, effect_id: str) -> ActionEffect | None:
        return self._effects.get(effect_id)

    def list_effects(self, action_type_id: str | None = None) -> list[ActionEffect]:
        if action_type_id:
            return [e for e in self._effects.values() if e.action_type_id == action_type_id]
        return list(self._effects.values())

    def delete_effect(self, effect_id: str) -> bool:
        existed = effect_id in self._effects
        self._effects.pop(effect_id, None)
        return existed

    def trigger_effect(self, effect_id: str, payload: dict[str, Any]) -> EffectResult:
        effect = self._effects.get(effect_id)
        if effect is None:
            raise ActionEnhancementError("NOT_FOUND", f"effect {effect_id!r} 不存在")
        if not effect.enabled:
            return EffectResult(effect_id=effect_id, status="pending", message="effect 已禁用")

        attempts = 0
        last_error = ""
        while attempts < effect.retry:
            attempts += 1
            try:
                if effect.type == EffectType.NOTIFICATION:
                    self._execute_notification(effect, payload)
                    return EffectResult(
                        effect_id=effect_id, status="success", attempt=attempts,
                        message="notification 发送成功",
                    )
                elif effect.type == EffectType.WEBHOOK:
                    self._execute_webhook(effect, payload)
                    return EffectResult(
                        effect_id=effect_id, status="success", attempt=attempts,
                        message="webhook 调用成功",
                    )
            except Exception as exc:
                last_error = str(exc)

        self._dlq[effect_id] = DLQEntry(
            effect_id=effect_id,
            action_type_id=effect.action_type_id,
            payload=payload,
            attempts=attempts,
            max_attempts=effect.retry,
            last_error=last_error,
        )
        return EffectResult(
            effect_id=effect_id, status="dlq", attempt=attempts,
            message=f"重试 {attempts} 次失败，已进入 DLQ",
        )

    def _execute_notification(self, effect: ActionEffect, payload: dict[str, Any]) -> None:
        recipients = effect.config.get("recipients", [])
        template = effect.config.get("template", "")
        self._notification_log.append({
            "effect_id": effect.id,
            "recipients": recipients,
            "template": template,
            "payload": payload,
            "sent_at": _now(),
        })

    def _execute_webhook(self, effect: ActionEffect, payload: dict[str, Any]) -> None:
        url = effect.config.get("url", "")
        method = effect.config.get("method", "POST")
        headers = effect.config.get("headers", {})
        self._webhook_log.append({
            "effect_id": effect.id,
            "url": url,
            "method": method,
            "headers": headers,
            "payload": payload,
            "sent_at": _now(),
        })

    # ── #55 Optimistic UI ──

    def optimistic_submit(
        self, action_type_id: str, payload: dict[str, Any]
    ) -> OptimisticResult:
        token = OptimisticToken(action_type_id=action_type_id, payload=payload)
        self._optimistic_tokens[token.token] = token
        return OptimisticResult(ok=True, token=token.token)

    def optimistic_commit(self, token: str) -> OptimisticResult:
        opt = self._optimistic_tokens.get(token)
        if opt is None:
            raise ActionEnhancementError("NOT_FOUND", f"optimistic token {token!r} 不存在")
        self._optimistic_tokens.pop(token)
        return OptimisticResult(ok=True, token=token)

    def optimistic_rollback(self, token: str) -> OptimisticResult:
        opt = self._optimistic_tokens.get(token)
        if opt is None:
            raise ActionEnhancementError("NOT_FOUND", f"optimistic token {token!r} 不存在")
        result = OptimisticResult(
            ok=True,
            token=token,
            rollback_required=True,
            rollback_payload=opt.payload,
        )
        self._optimistic_tokens.pop(token)
        return result

    # ── #56 Soft Delete ──

    def soft_delete(self, dataset_rid: str, pk: str) -> dict[str, Any]:
        from .writeback import WritebackOp, get_store

        store = get_store()
        txn_id = store.begin(dataset_rid)
        store.apply(txn_id, [WritebackOp(op="soft_delete", pk=pk)])
        store.commit(txn_id)
        return {"dataset_rid": dataset_rid, "pk": pk, "deleted": True, "txn_id": txn_id}

    def undelete(self, dataset_rid: str, pk: str) -> dict[str, Any]:
        from .writeback import WritebackOp, get_store

        store = get_store()
        txn_id = store.begin(dataset_rid)
        store.apply(txn_id, [WritebackOp(op="undelete", pk=pk)])
        store.commit(txn_id)
        return {"dataset_rid": dataset_rid, "pk": pk, "deleted": False, "txn_id": txn_id}

    # ── #57 DLQ ──

    def list_dlq(self) -> list[DLQEntry]:
        return list(self._dlq.values())

    def retry_dlq(self, entry_id: str) -> EffectResult:
        entry = self._dlq.get(entry_id)
        if entry is None:
            raise ActionEnhancementError("NOT_FOUND", f"DLQ entry {entry_id!r} 不存在")
        effect = self._effects.get(entry.effect_id)
        if effect is None:
            return EffectResult(
                effect_id=entry.effect_id, status="failed",
                message=f"关联的 effect {entry.effect_id!r} 已删除",
            )
        result = self.trigger_effect(entry.effect_id, entry.payload)
        if result.status == "success":
            self._dlq.pop(entry_id)
        return result

    def clear_dlq(self) -> int:
        count = len(self._dlq)
        self._dlq.clear()
        return count

    # ── #76 Merge Strategy ──

    def merge(
        self,
        current: dict[str, Any],
        incoming: dict[str, Any],
        strategy: MergeStrategy | str = MergeStrategy.FIELD_LEVEL,
    ) -> MergeResult:
        if isinstance(strategy, str):
            try:
                strategy = MergeStrategy(strategy)
            except ValueError:
                raise ActionEnhancementError(
                    "UNKNOWN_STRATEGY",
                    f"未知合并策略 {strategy!r}，可用：{[s.value for s in MergeStrategy]}",
                )

        if strategy == MergeStrategy.FIELD_LEVEL:
            merged = {**current, **incoming}
            return MergeResult(merged=merged, strategy=strategy)

        if strategy == MergeStrategy.LAST_WRITE_WINS:
            return MergeResult(merged=dict(incoming), strategy=strategy)

        conflicts = []
        for key in set(current.keys()) & set(incoming.keys()):
            if current[key] != incoming[key]:
                conflicts.append(MergeConflict(
                    field=key,
                    current_value=current[key],
                    incoming_value=incoming[key],
                ))
        return MergeResult(
            merged=dict(current),
            strategy=strategy,
            conflicts=conflicts,
        )


# ── 单例 ──

_engine = ActionEnhancementEngine()


def get_engine() -> ActionEnhancementEngine:
    return _engine
