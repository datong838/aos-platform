"""W2-V · AIP 智能层扩展组：#78 调试器 + #79 Automate + #80 四层成熟度.

本模块是 AIP（AI Process）智能层的可观测性与自动化能力补充：
    - DebuggerEngine  CoT 步进调试 + 中间变量快照 + 提议预览（不应用）
    - AutomateEngine  事件触发器 CRUD + 条件评估 + 冷却 + 自动调用 Logic 生成提案
    - MaturityEngine  L1/L2/L3/L4 楼梯评估 + 能力注册 + gap 分析

底层 Logic 引擎与 LLM 网关不重写，仅作可观测与编排层。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable

from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────────
# 公共工具
# ────────────────────────────────────────────────────────────────

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


class AIPExtrasError(Exception):
    """W2-V AIP 智能层错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════════════════════════════════════════════════
# #78 调试器
# ════════════════════════════════════════════════════════════════

class DebugStep(BaseModel):
    """调试步骤。"""

    index: int
    block_id: str
    block_type: str                # input / create_var / get_attr / use_llm / transform / apply_action / execute
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    variables_after: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"        # pending / running / completed / failed / skipped
    error: str = ""
    started_at: float = 0.0
    duration_ms: int = 0


class DebugSession(BaseModel):
    """调试会话。"""

    id: str = Field(default_factory=lambda: _uid("dbg"))
    logic_id: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"        # pending / running / paused / completed / failed
    current_step: int = 0
    steps: list[DebugStep] = Field(default_factory=list)
    started_at: float = 0.0
    ended_at: float = 0.0
    error: str = ""


class ProposedChange(BaseModel):
    """单条提议变更。"""

    object_type: str
    object_id: str
    field_path: str
    old_value: Any = None
    new_value: Any = None
    change_type: str = "update"    # create / update / delete
    rationale: str = ""


class ProposalPreview(BaseModel):
    """提议预览。"""

    id: str = Field(default_factory=lambda: _uid("pp"))
    logic_id: str
    debug_session_id: str
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    applied: bool = False
    created_at: float = Field(default_factory=_now_ts)


_VALID_BLOCK_TYPES = {
    "input", "create_var", "get_attr", "use_llm",
    "transform", "apply_action", "execute",
}


def _build_mock_steps(inputs: dict[str, Any]) -> list[DebugStep]:
    """根据 inputs 自动构造模拟调试步骤：每个 input key 一步 + 末尾 execute。"""
    steps: list[DebugStep] = []
    for idx, key in enumerate(sorted(inputs.keys())):
        steps.append(DebugStep(
            index=idx,
            block_id=f"input_{key}",
            block_type="input",
            inputs={"key": key, "value": inputs[key]},
        ))
    steps.append(DebugStep(
        index=len(steps),
        block_id="execute",
        block_type="execute",
        inputs=dict(inputs),
    ))
    return steps


class DebuggerEngine:
    """#78 · AIP 调试器引擎。"""

    def __init__(
        self,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, DebugSession] = {}
        self._proposals: dict[str, ProposalPreview] = {}
        self._clock = clock or _now_ts

    def create_session(
        self, logic_id: str, inputs: dict[str, Any] | None = None,
    ) -> DebugSession:
        if not logic_id:
            raise AIPExtrasError("INVALID_LOGIC_ID", "logic_id 不能为空")
        inputs = inputs or {}
        session = DebugSession(
            logic_id=logic_id,
            inputs=inputs,
            status="pending",
            started_at=self._clock(),
            steps=_build_mock_steps(inputs),
        )
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> DebugSession:
        with self._lock:
            s = self._sessions.get(session_id)
        if not s:
            raise AIPExtrasError("NOT_FOUND", f"调试会话 {session_id} 不存在")
        return s

    def list_sessions(
        self, logic_id: str | None = None,
    ) -> list[DebugSession]:
        with self._lock:
            items = list(self._sessions.values())
        if logic_id:
            items = [s for s in items if s.logic_id == logic_id]
        items.sort(key=lambda s: s.started_at)
        return items

    def step_forward(self, session_id: str) -> DebugStep:
        with self._lock:
            s = self._sessions.get(session_id)
            if not s:
                raise AIPExtrasError("NOT_FOUND", f"调试会话 {session_id} 不存在")
            if s.status == "completed":
                raise AIPExtrasError(
                    "SESSION_COMPLETED",
                    f"会话 {session_id} 已完成，无法继续步进",
                )
            if s.status == "failed":
                raise AIPExtrasError(
                    "SESSION_FAILED",
                    f"会话 {session_id} 已失败，无法继续步进",
                )
            if s.current_step >= len(s.steps):
                s.status = "completed"
                s.ended_at = self._clock()
                raise AIPExtrasError(
                    "SESSION_COMPLETED",
                    f"会话 {session_id} 已到达末尾",
                )
            step = s.steps[s.current_step]
            if step.block_type not in _VALID_BLOCK_TYPES:
                raise AIPExtrasError(
                    "INVALID_BLOCK_TYPE",
                    f"未知 block 类型: {step.block_type}",
                )
            # 模拟执行：累积变量上下文
            started = self._clock()
            step.started_at = started
            step.status = "running"
            s.status = "running"

            variables: dict[str, Any] = {}
            if s.current_step > 0:
                prev = s.steps[s.current_step - 1]
                variables = dict(prev.variables_after)
            if step.block_type == "input":
                key = step.inputs.get("key", f"var_{step.index}")
                variables[key] = step.inputs.get("value")
                step.outputs = {key: variables[key]}
            elif step.block_type == "execute":
                step.outputs = {"result": "executed", "inputs": step.inputs}
            else:
                step.outputs = {"echo": step.inputs}

            step.variables_after = variables
            step.status = "completed"
            step.duration_ms = 1
            s.current_step += 1
            if s.current_step >= len(s.steps):
                s.status = "completed"
                s.ended_at = self._clock()
            else:
                s.status = "paused"
            return step

    def step_backward(self, session_id: str) -> DebugStep:
        with self._lock:
            s = self._sessions.get(session_id)
            if not s:
                raise AIPExtrasError("NOT_FOUND", f"调试会话 {session_id} 不存在")
            if s.current_step <= 0:
                raise AIPExtrasError(
                    "AT_BEGINNING",
                    f"会话 {session_id} 已在开头，无法后退",
                )
            s.current_step -= 1
            step = s.steps[s.current_step]
            # 回退后状态：若已在开头则 pending，否则 paused
            s.status = "pending" if s.current_step == 0 else "paused"
            return step

    def run_to_completion(self, session_id: str) -> DebugSession:
        s = self.get_session(session_id)
        # 锁外循环（每次 step_forward 内部加锁）
        while s.status not in ("completed", "failed"):
            self.step_forward(session_id)
            s = self.get_session(session_id)
        return s

    def preview_proposal(
        self,
        session_id: str,
        changes: list[ProposedChange],
    ) -> ProposalPreview:
        s = self.get_session(session_id)
        proposal = ProposalPreview(
            logic_id=s.logic_id,
            debug_session_id=session_id,
            proposed_changes=list(changes),
        )
        with self._lock:
            self._proposals[proposal.id] = proposal
        return proposal

    def list_proposals(
        self, session_id: str | None = None,
    ) -> list[ProposalPreview]:
        with self._lock:
            items = list(self._proposals.values())
        if session_id:
            items = [p for p in items if p.debug_session_id == session_id]
        items.sort(key=lambda p: p.created_at)
        return items

    def get_proposal(self, proposal_id: str) -> ProposalPreview:
        with self._lock:
            p = self._proposals.get(proposal_id)
        if not p:
            raise AIPExtrasError("NOT_FOUND", f"提议 {proposal_id} 不存在")
        return p

    def apply_proposal(self, proposal_id: str) -> ProposalPreview:
        with self._lock:
            p = self._proposals.get(proposal_id)
            if not p:
                raise AIPExtrasError("NOT_FOUND", f"提议 {proposal_id} 不存在")
            if p.applied:
                raise AIPExtrasError(
                    "ALREADY_APPLIED",
                    f"提议 {proposal_id} 已应用",
                )
            p.applied = True
            return p


# ════════════════════════════════════════════════════════════════
# #79 Automate
# ════════════════════════════════════════════════════════════════

class AutomateTrigger(BaseModel):
    """自动化触发器。"""

    id: str = Field(default_factory=lambda: _uid("trg"))
    name: str
    logic_id: str
    event_type: str = "manual"      # object_changed / schedule / manual / webhook / threshold
    condition: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    cooldown_seconds: float = 0.0
    last_triggered_at: float = 0.0
    trigger_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=_now_ts)


class AutomateRun(BaseModel):
    """自动化执行记录。"""

    id: str = Field(default_factory=lambda: _uid("run"))
    trigger_id: str
    logic_id: str
    trigger_event: str = ""
    status: str = "pending"          # pending / running / completed / failed / skipped
    proposal_id: str = ""
    started_at: float = 0.0
    ended_at: float = 0.0
    error: str = ""


_VALID_EVENT_TYPES = {
    "object_changed", "schedule", "manual", "webhook", "threshold",
}


def _eval_condition(condition: dict[str, Any], event: dict[str, Any]) -> bool:
    """简化条件评估：condition 形如 {"field": value}（相等）或
    {"field": {"op": "eq|ne|gt|lt|ge|le", "value": X}}。
    空条件视为满足（与 manual 触发器对齐）。
    """
    if not condition:
        return True
    for field, spec in condition.items():
        actual = event.get(field)
        if isinstance(spec, dict) and "op" in spec:
            op = spec.get("op", "eq")
            target = spec.get("value")
            if not _cmp_op(actual, op, target):
                return False
        else:
            # 直接相等
            if actual != spec:
                return False
    return True


def _cmp_op(actual: Any, op: str, target: Any) -> bool:
    try:
        if op == "eq":
            return actual == target
        if op == "ne":
            return actual != target
        a = float(actual)
        t = float(target)
        if op == "gt":
            return a > t
        if op == "lt":
            return a < t
        if op == "ge":
            return a >= t
        if op == "le":
            return a <= t
    except (TypeError, ValueError):
        return False
    return False


class AutomateEngine:
    """#79 · Automate 自动化引擎。"""

    def __init__(
        self,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._triggers: dict[str, AutomateTrigger] = {}
        self._runs: list[AutomateRun] = []
        self._clock = clock or _now_ts

    def upsert_trigger(self, trigger: AutomateTrigger) -> AutomateTrigger:
        if trigger.event_type not in _VALID_EVENT_TYPES:
            raise AIPExtrasError(
                "INVALID_EVENT_TYPE",
                f"未知事件类型: {trigger.event_type}",
            )
        with self._lock:
            self._triggers[trigger.id] = trigger
        return trigger

    def get_trigger(self, trigger_id: str) -> AutomateTrigger:
        with self._lock:
            t = self._triggers.get(trigger_id)
        if not t:
            raise AIPExtrasError("NOT_FOUND", f"触发器 {trigger_id} 不存在")
        return t

    def list_triggers(
        self, enabled_only: bool = False,
    ) -> list[AutomateTrigger]:
        with self._lock:
            items = list(self._triggers.values())
        if enabled_only:
            items = [t for t in items if t.enabled]
        items.sort(key=lambda t: t.created_at)
        return items

    def delete_trigger(self, trigger_id: str) -> bool:
        with self._lock:
            if trigger_id not in self._triggers:
                raise AIPExtrasError("NOT_FOUND", f"触发器 {trigger_id} 不存在")
            del self._triggers[trigger_id]
            return True

    def evaluate(
        self, trigger_id: str, event: dict[str, Any] | None = None,
    ) -> bool:
        t = self.get_trigger(trigger_id)
        event = event or {}
        return _eval_condition(t.condition, event)

    def fire(
        self,
        trigger_id: str,
        event: dict[str, Any] | None = None,
    ) -> AutomateRun:
        event = event or {}
        with self._lock:
            t = self._triggers.get(trigger_id)
            if not t:
                raise AIPExtrasError("NOT_FOUND", f"触发器 {trigger_id} 不存在")
            if not t.enabled:
                raise AIPExtrasError(
                    "AUTOMATE_DISABLED",
                    f"触发器 {trigger_id} 已禁用",
                )
            now = self._clock()
            if (
                t.cooldown_seconds > 0
                and t.last_triggered_at > 0
                and (now - t.last_triggered_at) < t.cooldown_seconds
            ):
                raise AIPExtrasError(
                    "IN_COOLDOWN",
                    f"触发器 {trigger_id} 处于冷却期",
                )
            # 条件评估（锁外更安全，但简化：锁内同步评估）
            if not _eval_condition(t.condition, event):
                raise AIPExtrasError(
                    "CONDITION_NOT_MET",
                    f"触发器 {trigger_id} 条件不满足",
                )
            # 创建执行记录
            run = AutomateRun(
                trigger_id=trigger_id,
                logic_id=t.logic_id,
                trigger_event=str(event.get("event_type", t.event_type)),
                status="running",
                started_at=now,
            )
            self._runs.append(run)
            # 简化：不实际执行 Logic，标记完成
            run.status = "completed"
            run.ended_at = self._clock()
            run.proposal_id = _uid("prop")
            # 更新 trigger 计数
            t.last_triggered_at = now
            t.trigger_count += 1
            # 保留最近 200 条 run
            if len(self._runs) > 200:
                self._runs = self._runs[-200:]
            return run

    def list_runs(
        self, trigger_id: str | None = None, limit: int = 50,
    ) -> list[AutomateRun]:
        with self._lock:
            items = list(self._runs)
        if trigger_id:
            items = [r for r in items if r.trigger_id == trigger_id]
        return list(reversed(items[-limit:]))

    def get_run(self, run_id: str) -> AutomateRun:
        with self._lock:
            for r in self._runs:
                if r.id == run_id:
                    return r
        raise AIPExtrasError("NOT_FOUND", f"执行记录 {run_id} 不存在")


# ════════════════════════════════════════════════════════════════
# #80 四层成熟度
# ════════════════════════════════════════════════════════════════

class MaturityLevel(BaseModel):
    """成熟度等级定义。"""

    level: str                       # L1 / L2 / L3 / L4
    name: str
    description: str
    required_capabilities: list[str] = Field(default_factory=list)


class MaturityAssessment(BaseModel):
    """成熟度评估结果。"""

    id: str = Field(default_factory=lambda: _uid("asmt"))
    timestamp: float = Field(default_factory=_now_ts)
    current_level: str
    target_level: str = "L4"
    capabilities: dict[str, bool] = Field(default_factory=dict)
    score: float = 0.0
    gaps: list[str] = Field(default_factory=list)
    recommendation: str = ""


DEFAULT_LEVELS: dict[str, MaturityLevel] = {
    "L1": MaturityLevel(
        level="L1", name="基础",
        description="规则驱动 + 人工调用",
        required_capabilities=["rule_engine", "manual_call"],
    ),
    "L2": MaturityLevel(
        level="L2", name="辅助",
        description="LLM 辅助 + 人工审核",
        required_capabilities=["llm_gateway", "prompt_engineering", "evals"],
    ),
    "L3": MaturityLevel(
        level="L3", name="半自动",
        description="Logic 编排 + 自动触发 + 人工审批",
        required_capabilities=["logic_engine", "automate", "debugger", "proposal_preview"],
    ),
    "L4": MaturityLevel(
        level="L4", name="全自动",
        description="端到端自动 + 熔断 + 自愈",
        required_capabilities=["failover", "circuit_breaker", "auto_apply", "monitoring"],
    ),
}

_LEVEL_ORDER = ["L1", "L2", "L3", "L4"]


class MaturityEngine:
    """#80 · 四层成熟度引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._levels: dict[str, MaturityLevel] = {k: v.model_copy() for k, v in DEFAULT_LEVELS.items()}
        self._capabilities: dict[str, bool] = {}
        self._assessments: list[MaturityAssessment] = []
        self._target_level: str = "L4"

    def list_levels(self) -> list[MaturityLevel]:
        with self._lock:
            return [self._levels[lv] for lv in _LEVEL_ORDER if lv in self._levels]

    def get_level(self, level: str) -> MaturityLevel:
        with self._lock:
            lv = self._levels.get(level)
        if not lv:
            raise AIPExtrasError("NOT_FOUND", f"成熟度等级 {level} 不存在")
        return lv

    def upsert_level(self, level: MaturityLevel) -> MaturityLevel:
        if level.level not in {"L1", "L2", "L3", "L4"}:
            raise AIPExtrasError(
                "INVALID_LEVEL",
                f"未知等级: {level.level}（仅支持 L1/L2/L3/L4）",
            )
        with self._lock:
            self._levels[level.level] = level
        return level

    def register_capability(self, name: str, satisfied: bool) -> None:
        if not name:
            raise AIPExtrasError("INVALID_CAPABILITY", "能力名称不能为空")
        with self._lock:
            self._capabilities[name] = satisfied

    def list_capabilities(self) -> dict[str, bool]:
        with self._lock:
            return dict(self._capabilities)

    def assess(self) -> MaturityAssessment:
        with self._lock:
            levels = [self._levels[lv] for lv in _LEVEL_ORDER if lv in self._levels]
            caps = dict(self._capabilities)
            target = self._target_level

        # 找最高满足的等级（楼梯模型：低层不满足则停止向上）
        # current 起始为 "L0"（未达 L1 基线），便于 gap 从 L1 起算
        current = "L0"
        for lv in levels:
            if all(caps.get(c, False) for c in lv.required_capabilities):
                current = lv.level
            else:
                break

        # 计算 score
        total = 0
        satisfied = 0
        for lv in levels:
            for c in lv.required_capabilities:
                total += 1
                if caps.get(c, False):
                    satisfied += 1
        score = (satisfied / total) if total > 0 else 0.0

        # gap 分析：从 current+1 到 target 之间缺失能力
        # current 为 "L0" 时从 L1 起算
        gaps: list[str] = []
        scan_keys = _LEVEL_ORDER
        try:
            if current in _LEVEL_ORDER:
                start_idx = _LEVEL_ORDER.index(current) + 1
            else:
                start_idx = 0  # L0 → 从 L1 开始
            end_idx = _LEVEL_ORDER.index(target) + 1
            for i in range(start_idx, end_idx):
                lv_key = scan_keys[i]
                lv_def = self._levels.get(lv_key)
                if not lv_def:
                    continue
                for c in lv_def.required_capabilities:
                    if not caps.get(c, False):
                        gaps.append(f"{lv_key}:{c}")
        except ValueError:
            pass

        # 文案
        recommendation = (
            f"当前 {current}，目标 {target}。"
            + ("已达到目标等级。" if current == target
               else f"需补齐 {len(gaps)} 项能力：{', '.join(gaps[:5])}{'…' if len(gaps) > 5 else ''}")
        )

        asmt = MaturityAssessment(
            current_level=current,
            target_level=target,
            capabilities=caps,
            score=score,
            gaps=gaps,
            recommendation=recommendation,
        )
        with self._lock:
            self._assessments.append(asmt)
            if len(self._assessments) > 200:
                self._assessments = self._assessments[-200:]
        return asmt

    def list_assessments(self, limit: int = 20) -> list[MaturityAssessment]:
        with self._lock:
            items = list(self._assessments)
        return list(reversed(items[-limit:]))

    def set_target_level(self, level: str) -> None:
        if level not in {"L1", "L2", "L3", "L4"}:
            raise AIPExtrasError(
                "INVALID_LEVEL",
                f"未知等级: {level}（仅支持 L1/L2/L3/L4）",
            )
        with self._lock:
            self._target_level = level

    def get_target_level(self) -> str:
        with self._lock:
            return self._target_level


# ────────────────────────────────────────────────────────────────
# 单例 getters（双重检查锁）
# ────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_debugger_engine: DebuggerEngine | None = None
_automate_engine: AutomateEngine | None = None
_maturity_engine: MaturityEngine | None = None


def get_debugger_engine() -> DebuggerEngine:
    global _debugger_engine
    if _debugger_engine is None:
        with _lock:
            if _debugger_engine is None:
                _debugger_engine = DebuggerEngine()
    return _debugger_engine


def get_automate_engine() -> AutomateEngine:
    global _automate_engine
    if _automate_engine is None:
        with _lock:
            if _automate_engine is None:
                _automate_engine = AutomateEngine()
    return _automate_engine


def get_maturity_engine() -> MaturityEngine:
    global _maturity_engine
    if _maturity_engine is None:
        with _lock:
            if _maturity_engine is None:
                _maturity_engine = MaturityEngine()
    return _maturity_engine
