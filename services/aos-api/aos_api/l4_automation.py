"""W2-W · L4 自动化收尾组：#82 L4 熔断 + #83 模型预热 + #86 三种提案通道.

本模块是 AIP L4 全自动态的收口三件：
    - L4CircuitEngine       跨链路失败率监控 + 自动降级 L3 + 告警
    - ModelWarmupEngine     模型预热状态机（cold/warming/ready/failed）+ warm-up 探测
    - ProposalChannelEngine 三种提案通道（sync/async_automate/async_pipeline）+ 默认暂存 + 审批台

底层 FailoverEngine/MaturityEngine/AutomateEngine 不重写，仅作监控与分发层。
"""
from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from typing import Any, Callable

from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────────
# 公共工具
# ────────────────────────────────────────────────────────────────

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


class L4AutomationError(Exception):
    """W2-W L4 自动化收尾组错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════════════════════════════════════════════════
# #82 L4 熔断
# ════════════════════════════════════════════════════════════════

class L4CircuitConfig(BaseModel):
    """L4 熔断配置。"""

    window_size: int = 100
    failure_threshold: float = 0.05    # 5%
    recovery_threshold: float = 0.025  # 滞回 2.5%
    cooldown_seconds: float = 60.0
    auto_degrade_to: str = "L3"


class L4CircuitState(BaseModel):
    """L4 熔断状态。"""

    current_level: str = "L4"
    window_failures: int = 0
    window_total: int = 0
    failure_rate: float = 0.0
    last_degraded_at: float = 0.0
    last_recovered_at: float = 0.0
    degraded: bool = False


class L4Alert(BaseModel):
    """L4 告警记录。"""

    id: str = Field(default_factory=lambda: _uid("l4alert"))
    timestamp: float = Field(default_factory=_now_ts)
    type: str                          # degrade / recover / threshold_exceeded
    message: str
    failure_rate: float = 0.0
    level: str = "L4"


class L4CircuitEngine:
    """#82 · L4 熔断引擎。"""

    def __init__(
        self,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._config = L4CircuitConfig()
        self._state = L4CircuitState()
        self._window: deque[bool] = deque()
        self._alerts: list[L4Alert] = []
        self._clock = clock or _now_ts

    def get_config(self) -> L4CircuitConfig:
        with self._lock:
            return self._config.model_copy()

    def update_config(self, cfg: L4CircuitConfig) -> L4CircuitConfig:
        if cfg.window_size <= 0:
            raise L4AutomationError(
                "INVALID_CONFIG", "window_size 必须 > 0",
            )
        if not (0.0 < cfg.failure_threshold <= 1.0):
            raise L4AutomationError(
                "INVALID_CONFIG", "failure_threshold 必须在 (0, 1]",
            )
        if not (0.0 <= cfg.recovery_threshold < cfg.failure_threshold):
            raise L4AutomationError(
                "INVALID_CONFIG", "recovery_threshold 必须 < failure_threshold",
            )
        with self._lock:
            self._config = cfg
            # 窗口可能需缩容
            while len(self._window) > cfg.window_size:
                self._window.popleft()
            self._recompute_state_locked()
            return self._config.model_copy()

    def get_state(self) -> L4CircuitState:
        with self._lock:
            return self._state.model_copy()

    def record_call(self, success: bool) -> L4CircuitState:
        with self._lock:
            self._window.append(success)
            while len(self._window) > self._config.window_size:
                self._window.popleft()
            self._recompute_state_locked()

            now = self._clock()
            # 降级评估
            if (
                not self._state.degraded
                and self._state.window_total >= 10  # 最少样本
                and self._state.failure_rate > self._config.failure_threshold
            ):
                self._state.degraded = True
                self._state.current_level = self._config.auto_degrade_to
                self._state.last_degraded_at = now
                alert = L4Alert(
                    type="degrade",
                    message=f"L4 失败率 {self._state.failure_rate:.2%} > 阈值 "
                            f"{self._config.failure_threshold:.2%}，降级到 "
                            f"{self._config.auto_degrade_to}",
                    failure_rate=self._state.failure_rate,
                    level=self._config.auto_degrade_to,
                )
                self._append_alert_locked(alert)
            # 恢复评估（滞回 + cooldown）
            elif (
                self._state.degraded
                and self._state.window_total >= 10
                and self._state.failure_rate <= self._config.recovery_threshold
                and (now - self._state.last_degraded_at) >= self._config.cooldown_seconds
            ):
                self._state.degraded = False
                self._state.current_level = "L4"
                self._state.last_recovered_at = now
                alert = L4Alert(
                    type="recover",
                    message=f"L4 失败率回落到 {self._state.failure_rate:.2%}，恢复 L4",
                    failure_rate=self._state.failure_rate,
                    level="L4",
                )
                self._append_alert_locked(alert)
            return self._state.model_copy()

    def force_degrade(self, reason: str = "manual") -> L4Alert:
        with self._lock:
            now = self._clock()
            self._state.degraded = True
            self._state.current_level = self._config.auto_degrade_to
            self._state.last_degraded_at = now
            alert = L4Alert(
                type="degrade",
                message=f"L4 手动降级（{reason}）",
                failure_rate=self._state.failure_rate,
                level=self._config.auto_degrade_to,
            )
            self._append_alert_locked(alert)
            return alert

    def force_recover(self) -> L4Alert:
        with self._lock:
            now = self._clock()
            self._state.degraded = False
            self._state.current_level = "L4"
            self._state.last_recovered_at = now
            alert = L4Alert(
                type="recover",
                message="L4 手动恢复",
                failure_rate=self._state.failure_rate,
                level="L4",
            )
            self._append_alert_locked(alert)
            return alert

    def list_alerts(self, limit: int = 50) -> list[L4Alert]:
        with self._lock:
            items = list(self._alerts)
        return list(reversed(items[-limit:]))

    def reset(self) -> None:
        with self._lock:
            self._state = L4CircuitState()
            self._window.clear()
            self._alerts.clear()

    # —— 内部辅助 ——

    def _recompute_state_locked(self) -> None:
        total = len(self._window)
        failures = sum(1 for s in self._window if not s)
        self._state.window_total = total
        self._state.window_failures = failures
        self._state.failure_rate = (failures / total) if total > 0 else 0.0

    def _append_alert_locked(self, alert: L4Alert) -> None:
        self._alerts.append(alert)
        if len(self._alerts) > 200:
            self._alerts = self._alerts[-200:]


# ════════════════════════════════════════════════════════════════
# #83 模型预热
# ════════════════════════════════════════════════════════════════

class WarmupState(BaseModel):
    """模型预热状态。"""

    model_id: str
    state: str = "cold"                # cold / warming / ready / failed
    last_warmup_at: float = 0.0
    last_ready_at: float = 0.0
    last_failed_at: float = 0.0
    failure_count: int = 0
    cooldown_until: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class WarmupProbeResult(BaseModel):
    """预热探测结果。"""

    model_id: str
    success: bool
    duration_ms: int = 0
    error: str = ""
    timestamp: float = Field(default_factory=_now_ts)


_VALID_WARMUP_STATES = {"cold", "warming", "ready", "failed"}


class ModelWarmupEngine:
    """#83 · 模型预热引擎。"""

    def __init__(
        self,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, WarmupState] = {}
        self._probe_results: list[WarmupProbeResult] = []
        self._clock = clock or _now_ts

    def register_model(
        self, model_id: str, metadata: dict[str, Any] | None = None,
    ) -> WarmupState:
        if not model_id:
            raise L4AutomationError("INVALID_MODEL_ID", "model_id 不能为空")
        with self._lock:
            state = WarmupState(model_id=model_id, metadata=metadata or {})
            self._states[model_id] = state
            return state

    def get_state(self, model_id: str) -> WarmupState:
        with self._lock:
            s = self._states.get(model_id)
        if not s:
            raise L4AutomationError("NOT_FOUND", f"模型 {model_id} 未注册预热")
        return s

    def list_states(self) -> list[WarmupState]:
        with self._lock:
            return list(self._states.values())

    def warmup(
        self,
        model_id: str,
        probe_callable: Callable[[], bool] | None = None,
    ) -> WarmupProbeResult:
        with self._lock:
            s = self._states.get(model_id)
            if not s:
                raise L4AutomationError("NOT_FOUND", f"模型 {model_id} 未注册预热")
            now = self._clock()
            if s.cooldown_until > now:
                raise L4AutomationError(
                    "IN_COOLDOWN",
                    f"模型 {model_id} 处于冷却期至 {s.cooldown_until}",
                )
            s.state = "warming"
            s.last_warmup_at = now

        # 实际探测在锁外执行（避免阻塞）
        probe = probe_callable or (lambda: True)
        started = self._clock()
        success = False
        error_msg = ""
        try:
            success = bool(probe())
        except Exception as exc:  # noqa: BLE001
            error_msg = str(exc)
            success = False
        duration_ms = max(1, int((self._clock() - started) * 1000))

        result = WarmupProbeResult(
            model_id=model_id,
            success=success,
            duration_ms=duration_ms,
            error=error_msg,
            timestamp=self._clock(),
        )

        with self._lock:
            s = self._states.get(model_id)
            if not s:
                # 极端竞态：注册被删
                return result
            now = self._clock()
            if success:
                s.state = "ready"
                s.last_ready_at = now
                # 不重置 failure_count，便于审计累计
            else:
                s.state = "failed"
                s.last_failed_at = now
                s.failure_count += 1
                # 退避：5s × count，上限 60s
                backoff = min(60.0, 5.0 * s.failure_count)
                s.cooldown_until = now + backoff
            self._probe_results.append(result)
            if len(self._probe_results) > 200:
                self._probe_results = self._probe_results[-200:]
            return result

    def mark_ready(self, model_id: str) -> WarmupState:
        with self._lock:
            s = self._states.get(model_id)
            if not s:
                raise L4AutomationError("NOT_FOUND", f"模型 {model_id} 未注册预热")
            s.state = "ready"
            s.last_ready_at = self._clock()
            return s.model_copy()

    def mark_failed(self, model_id: str, error: str = "") -> WarmupState:
        with self._lock:
            s = self._states.get(model_id)
            if not s:
                raise L4AutomationError("NOT_FOUND", f"模型 {model_id} 未注册预热")
            s.state = "failed"
            s.last_failed_at = self._clock()
            s.failure_count += 1
            return s.model_copy()

    def remove_model(self, model_id: str) -> bool:
        with self._lock:
            if model_id not in self._states:
                raise L4AutomationError("NOT_FOUND", f"模型 {model_id} 未注册预热")
            del self._states[model_id]
            return True

    def list_probe_results(
        self, model_id: str | None = None, limit: int = 50,
    ) -> list[WarmupProbeResult]:
        with self._lock:
            items = list(self._probe_results)
        if model_id:
            items = [r for r in items if r.model_id == model_id]
        return list(reversed(items[-limit:]))


# ════════════════════════════════════════════════════════════════
# #86 三种提案通道
# ════════════════════════════════════════════════════════════════

class ProposalChannel(BaseModel):
    """提案通道定义。"""

    type: str                          # sync / async_automate / async_pipeline
    name: str
    description: str = ""
    enabled: bool = True


class ProposalSubmission(BaseModel):
    """提案提交记录。"""

    id: str = Field(default_factory=lambda: _uid("prop"))
    channel: str                       # sync / async_automate / async_pipeline
    logic_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"            # pending / running / completed / failed / cancelled
    submitted_by: str = ""
    submitted_at: float = Field(default_factory=_now_ts)
    completed_at: float = 0.0
    visible_until: float = 0.0         # 24h 安全窗口
    approval_status: str = "pending"   # pending / approved / rejected
    approved_by: str = ""
    approved_at: float = 0.0
    error: str = ""


DEFAULT_CHANNELS: dict[str, ProposalChannel] = {
    "sync": ProposalChannel(
        type="sync", name="同步通道",
        description="Logic 直接嵌 Workshop，结果即时回写",
    ),
    "async_automate": ProposalChannel(
        type="async_automate", name="异步 Automate 通道",
        description="Automate 触发，结果入 Draft 待审批",
    ),
    "async_pipeline": ProposalChannel(
        type="async_pipeline", name="异步管道通道",
        description="Pipeline 批处理，结果入 Draft 待审批",
    ),
}

_VALID_CHANNEL_TYPES = {"sync", "async_automate", "async_pipeline"}


class ProposalChannelEngine:
    """#86 · 三种提案通道引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._channels: dict[str, ProposalChannel] = {
            k: v.model_copy() for k, v in DEFAULT_CHANNELS.items()
        }
        self._submissions: dict[str, ProposalSubmission] = {}

    def list_channels(self) -> list[ProposalChannel]:
        with self._lock:
            return [
                self._channels[t] for t in _VALID_CHANNEL_TYPES
                if t in self._channels
            ]

    def get_channel(self, channel_type: str) -> ProposalChannel:
        with self._lock:
            c = self._channels.get(channel_type)
        if not c:
            raise L4AutomationError("NOT_FOUND", f"通道 {channel_type} 不存在")
        return c

    def upsert_channel(self, channel: ProposalChannel) -> ProposalChannel:
        if channel.type not in _VALID_CHANNEL_TYPES:
            raise L4AutomationError(
                "INVALID_CHANNEL_TYPE",
                f"未知通道类型: {channel.type}（仅支持 sync/async_automate/async_pipeline）",
            )
        with self._lock:
            self._channels[channel.type] = channel
        return channel

    def submit(
        self,
        channel: str,
        logic_id: str,
        payload: dict[str, Any] | None = None,
        submitted_by: str = "",
        visibility_hours: float = 24.0,
    ) -> ProposalSubmission:
        if channel not in _VALID_CHANNEL_TYPES:
            raise L4AutomationError(
                "INVALID_CHANNEL", f"未知通道: {channel}",
            )
        if not logic_id:
            raise L4AutomationError("INVALID_LOGIC_ID", "logic_id 不能为空")
        with self._lock:
            ch = self._channels.get(channel)
            if not ch:
                raise L4AutomationError("INVALID_CHANNEL", f"通道 {channel} 不存在")
            if not ch.enabled:
                raise L4AutomationError(
                    "CHANNEL_DISABLED", f"通道 {channel} 已禁用",
                )
            now = _now_ts()
            submission = ProposalSubmission(
                channel=channel,
                logic_id=logic_id,
                payload=payload or {},
                submitted_by=submitted_by,
                submitted_at=now,
                visible_until=now + visibility_hours * 3600.0,
            )
            # sync 通道：即时完成 + 自动审批通过
            if channel == "sync":
                submission.status = "completed"
                submission.completed_at = now
                submission.approval_status = "approved"
                submission.approved_by = submitted_by or "system"
                submission.approved_at = now
            self._submissions[submission.id] = submission
            # 200 条上限
            if len(self._submissions) > 200:
                # 删除最早的
                oldest = min(
                    self._submissions.values(),
                    key=lambda s: s.submitted_at,
                )
                self._submissions.pop(oldest.id, None)
            return submission

    def get_submission(self, submission_id: str) -> ProposalSubmission:
        with self._lock:
            s = self._submissions.get(submission_id)
        if not s:
            raise L4AutomationError("NOT_FOUND", f"提案 {submission_id} 不存在")
        return s

    def list_submissions(
        self,
        channel: str | None = None,
        status: str | None = None,
        approval_status: str | None = None,
        include_expired: bool = False,
    ) -> list[ProposalSubmission]:
        now = _now_ts()
        with self._lock:
            items = list(self._submissions.values())
        if channel:
            items = [s for s in items if s.channel == channel]
        if status:
            items = [s for s in items if s.status == status]
        if approval_status:
            items = [s for s in items if s.approval_status == approval_status]
        if not include_expired:
            items = [
                s for s in items
                if s.visible_until == 0 or s.visible_until >= now or s.status != "pending"
            ]
        items.sort(key=lambda s: s.submitted_at, reverse=True)
        return items

    def approve(self, submission_id: str, approver: str) -> ProposalSubmission:
        with self._lock:
            s = self._submissions.get(submission_id)
            if not s:
                raise L4AutomationError("NOT_FOUND", f"提案 {submission_id} 不存在")
            if s.approval_status == "approved":
                raise L4AutomationError(
                    "ALREADY_APPROVED", f"提案 {submission_id} 已审批通过",
                )
            if s.approval_status == "rejected":
                raise L4AutomationError(
                    "ALREADY_REJECTED", f"提案 {submission_id} 已驳回",
                )
            if s.status == "cancelled":
                raise L4AutomationError(
                    "SUBMISSION_CANCELLED", f"提案 {submission_id} 已取消",
                )
            now = _now_ts()
            s.approval_status = "approved"
            s.approved_by = approver
            s.approved_at = now
            s.status = "completed"
            s.completed_at = now
            return s

    def reject(
        self, submission_id: str, approver: str, reason: str = "",
    ) -> ProposalSubmission:
        with self._lock:
            s = self._submissions.get(submission_id)
            if not s:
                raise L4AutomationError("NOT_FOUND", f"提案 {submission_id} 不存在")
            if s.approval_status in ("approved", "rejected"):
                raise L4AutomationError(
                    "ALREADY_DECIDED", f"提案 {submission_id} 已决策",
                )
            if s.status == "cancelled":
                raise L4AutomationError(
                    "SUBMISSION_CANCELLED", f"提案 {submission_id} 已取消",
                )
            now = _now_ts()
            s.approval_status = "rejected"
            s.approved_by = approver
            s.approved_at = now
            s.status = "failed"
            s.completed_at = now
            s.error = reason
            return s

    def cancel(self, submission_id: str) -> ProposalSubmission:
        with self._lock:
            s = self._submissions.get(submission_id)
            if not s:
                raise L4AutomationError("NOT_FOUND", f"提案 {submission_id} 不存在")
            if s.status in ("completed", "failed", "cancelled"):
                raise L4AutomationError(
                    "SUBMISSION_FINAL", f"提案 {submission_id} 已终态，不可取消",
                )
            now = _now_ts()
            s.status = "cancelled"
            s.completed_at = now
            return s

    def cleanup_expired(self) -> int:
        now = _now_ts()
        count = 0
        with self._lock:
            for s in list(self._submissions.values()):
                if (
                    s.status == "pending"
                    and s.visible_until > 0
                    and s.visible_until < now
                ):
                    s.status = "cancelled"
                    s.completed_at = now
                    s.error = "expired"
                    count += 1
        return count


# ────────────────────────────────────────────────────────────────
# 单例 getters（双重检查锁）
# ────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_l4_circuit_engine: L4CircuitEngine | None = None
_model_warmup_engine: ModelWarmupEngine | None = None
_proposal_channel_engine: ProposalChannelEngine | None = None


def get_l4_circuit_engine() -> L4CircuitEngine:
    global _l4_circuit_engine
    if _l4_circuit_engine is None:
        with _lock:
            if _l4_circuit_engine is None:
                _l4_circuit_engine = L4CircuitEngine()
    return _l4_circuit_engine


def get_model_warmup_engine() -> ModelWarmupEngine:
    global _model_warmup_engine
    if _model_warmup_engine is None:
        with _lock:
            if _model_warmup_engine is None:
                _model_warmup_engine = ModelWarmupEngine()
    return _model_warmup_engine


def get_proposal_channel_engine() -> ProposalChannelEngine:
    global _proposal_channel_engine
    if _proposal_channel_engine is None:
        with _lock:
            if _proposal_channel_engine is None:
                _proposal_channel_engine = ProposalChannelEngine()
    return _proposal_channel_engine
