"""AIP Task Model — Task + Artifact + Action + Checkpoint 数据模型.

Phase 1 TAOR 循环的基础数据模型。
遵循现有 Pydantic + Singleton 模式。
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from aos_api.public_contracts import TaskStatus, normalize_task_status, transition_task_status


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now() -> float:
    return time.time()


# ── Artifact ──

class Artifact(BaseModel):
    """任务产出物。"""
    id: str = Field(default_factory=lambda: _uid("art"))
    task_id: str = ""
    type: str = "text"  # text | diff | json | table | chart
    content: str = ""
    diff: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=_now)


# ── Action ──

class ActionRequest(BaseModel):
    """动作请求。好的接口设计自带权限提示。"""
    action_type: str = "llm_call"  # llm_call | tool_call | ontology_query | action_writeback
    params: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "low"  # low | medium | high
    requires_approval: bool = False
    side_effect: bool = False
    max_retries: int = 3

    @model_validator(mode="after")
    def enforce_server_risk_floor(self) -> "ActionRequest":
        # Legacy TAOR does not yet have the UA2 ActionType policy service. Until
        # it does, fail closed: only known read-only kinds may remain low risk.
        if self.action_type not in {"llm_call", "ontology_query"}:
            self.risk_level = "high"
            self.requires_approval = True
            self.side_effect = True
        elif self.side_effect:
            self.risk_level = "medium" if self.risk_level == "low" else self.risk_level
            self.requires_approval = True
        return self


# ── Checkpoint ──

class Checkpoint(BaseModel):
    """任务检查点 — 支持回滚。"""
    id: str = Field(default_factory=lambda: _uid("ckpt"))
    task_id: str = ""
    step_index: int = 0
    step_name: str = ""
    state: str = "pending"  # pending | running | completed | failed
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[Artifact] = Field(default_factory=list)
    timestamp: float = Field(default_factory=_now)


# ── Task Step ──

class TaskStep(BaseModel):
    """执行计划中的单步。"""
    id: str = Field(default_factory=lambda: _uid("step"))
    name: str = ""
    action: ActionRequest = Field(default_factory=ActionRequest)
    action_config: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # pending | running | completed | failed | skipped
    retry_count: int = 0
    max_retries: int = 3
    think_output: str = ""
    act_output: str = ""
    verify_passed: bool = False
    verify_issues: list[str] = Field(default_factory=list)
    tokens_used: int = 0
    elapsed_ms: int = 0
    artifacts: list[Artifact] = Field(default_factory=list)


# ── Execution Plan ──

class ExecutionPlan(BaseModel):
    """执行计划 — Plan Mode 的产出。"""
    id: str = Field(default_factory=lambda: _uid("plan"))
    task_id: str = ""
    steps: list[TaskStep] = Field(default_factory=list)
    status: str = "draft"  # draft | approved | executing | completed | failed
    approved_by: str = ""
    approved_at: float | None = None
    created_at: float = Field(default_factory=_now)


# ── Task ──

class Task(BaseModel):
    """任务 — TAOR 循环的顶层容器。"""
    id: str = Field(default_factory=lambda: _uid("task"))
    type: str = "generic"  # generic | customer_onboarding | product_recommendation | ...
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    plan: ExecutionPlan | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[Artifact] = Field(default_factory=list)
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    total_tokens: int = 0
    total_elapsed_ms: int = 0
    error: str | None = None
    created_at: float = Field(default_factory=_now)
    updated_at: float = Field(default_factory=_now)

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value):
        return normalize_task_status(value)

    def touch(self) -> None:
        self.updated_at = _now()

    def transition(self, target: str | TaskStatus) -> TaskStatus:
        self.status = transition_task_status(self.status, target)
        self.touch()
        return self.status



# ── TAOR 阶段结果 ──

class ThinkResult(BaseModel):
    """Think 阶段结果。"""
    instruction: str = ""
    memory_used: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    tokens_used: int = 0


class ActResult(BaseModel):
    """Act 阶段结果。"""
    output: str = ""
    artifacts: list[Artifact] = Field(default_factory=list)
    tokens_used: int = 0
    elapsed_ms: int = 0
    success: bool = True
    error: str | None = None


class VerifyResult(BaseModel):
    """Verify 阶段结果。"""
    passed: bool = True
    should_retry: bool = False
    is_fatal: bool = False
    issues: list[str] = Field(default_factory=list)
    auto_fixed: bool = False


class TaskResult(BaseModel):
    """任务最终结果。"""
    task_id: str = ""
    status: str = "completed"  # completed | failed
    artifacts: list[Artifact] = Field(default_factory=list)
    total_tokens: int = 0
    total_elapsed_ms: int = 0
    steps_completed: int = 0
    steps_failed: int = 0
    error: str | None = None
