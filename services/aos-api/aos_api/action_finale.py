"""W2-S · Action 收尾组：#67 日志对象类型 + #68 平台集成 + #70 Saga 事务回滚."""
from __future__ import annotations

import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ─────────────── #67 Action 日志对象类型 ───────────────

class ActionLog(BaseModel):
    id: str = Field(default_factory=lambda: _uid("log"))
    action_id: str
    operation_rid: str = Field(default_factory=lambda: _uid("rid"))
    version: int = 0  # 0=自动自增
    timestamp: str = Field(default_factory=_now)
    actor: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    submission_id: str = ""
    status: str = "submitted"   # submitted / succeeded / failed / reverted
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionLogError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_VALID_LOG_STATUSES = {"submitted", "succeeded", "failed", "reverted"}


class ActionLogEngine:
    """Action 日志对象类型引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._logs: dict[str, ActionLog] = {}
        # action_id → 已有日志数量（用于版本号自增）
        self._version_counter: dict[str, int] = {}

    def create(self, log: ActionLog) -> ActionLog:
        if log.status not in _VALID_LOG_STATUSES:
            raise ActionLogError(
                "INVALID_STATUS",
                f"未知日志状态: {log.status}",
            )
        with self._lock:
            # 版本号自增
            if log.version <= 0:
                log.version = self._version_counter.get(log.action_id, 0) + 1
            self._version_counter[log.action_id] = max(
                self._version_counter.get(log.action_id, 0), log.version
            )
            # ID 命名约定：LOG-{action_id}-{seq}
            if not log.id.startswith("log-"):
                log.id = f"log-{log.action_id}-{log.version}-{uuid.uuid4().hex[:4]}"
            self._logs[log.id] = log
        return log

    def get(self, log_id: str) -> ActionLog:
        log = self._logs.get(log_id)
        if not log:
            raise ActionLogError("NOT_FOUND", f"日志 {log_id} 不存在")
        return log

    def list(
        self,
        *,
        action_id: str | None = None,
        status: str | None = None,
    ) -> list[ActionLog]:
        with self._lock:
            items = list(self._logs.values())
        if action_id:
            items = [l for l in items if l.action_id == action_id]
        if status:
            items = [l for l in items if l.status == status]
        items.sort(key=lambda l: (l.action_id, l.version))
        return items

    def update_status(self, log_id: str, new_status: str) -> ActionLog:
        if new_status not in _VALID_LOG_STATUSES:
            raise ActionLogError("INVALID_STATUS", f"未知日志状态: {new_status}")
        with self._lock:
            log = self._logs.get(log_id)
            if not log:
                raise ActionLogError("NOT_FOUND", f"日志 {log_id} 不存在")
            log.status = new_status
            return log

    def delete(self, log_id: str) -> bool:
        with self._lock:
            if log_id not in self._logs:
                raise ActionLogError("NOT_FOUND", f"日志 {log_id} 不存在")
            del self._logs[log_id]
            return True

    def get_log_type(self, action_id: str) -> dict[str, Any]:
        """生成/获取 [LOG]ActionName 对象类型定义。"""
        type_name = f"[LOG]{action_id}"
        return {
            "object_type": type_name,
            "display_name": f"{action_id} 执行日志",
            "title_key": "operation_rid",
            "primary_key": "id",
            "properties": [
                {"name": "id", "type": "String", "required": True},
                {"name": "action_id", "type": "String", "required": True},
                {"name": "operation_rid", "type": "String", "required": True},
                {"name": "version", "type": "Integer"},
                {"name": "timestamp", "type": "Timestamp"},
                {"name": "actor", "type": "String"},
                {"name": "parameters", "type": "JSON"},
                {"name": "submission_id", "type": "String"},
                {"name": "status", "type": "String"},
            ],
            "description": f"自动生成的 {action_id} Action 执行日志类型",
        }

    def reset(self) -> None:
        with self._lock:
            self._logs.clear()
            self._version_counter.clear()


# ─────────────── #68 Action 平台集成 ───────────────

class ActionBinding(BaseModel):
    id: str = Field(default_factory=lambda: _uid("bnd"))
    action_id: str
    integration_type: str            # object_view / object_explorer / workshop
    target_type: str                 # object_type / workshop_module
    target_id: str
    button_label: str
    button_location: str = "primary"  # primary / secondary / overflow
    visibility_condition: str = ""
    order: int = 0
    enabled: bool = True
    created_at: str = Field(default_factory=_now)


class WorkshopButtonGroup(BaseModel):
    id: str = Field(default_factory=lambda: _uid("wbg"))
    workshop_module: str
    name: str
    action_bindings: list[str] = Field(default_factory=list)
    layout: str = "horizontal"   # horizontal / vertical
    order: int = 0
    created_at: str = Field(default_factory=_now)


class ActionBindingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_VALID_INTEGRATION_TYPES = {"object_view", "object_explorer", "workshop"}
_VALID_BUTTON_LOCATIONS = {"primary", "secondary", "overflow"}
_VALID_LAYOUTS = {"horizontal", "vertical"}


class ActionBindingEngine:
    """Action 平台集成引擎（绑定 + 按钮组）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bindings: dict[str, ActionBinding] = {}
        self._button_groups: dict[str, WorkshopButtonGroup] = {}

    # ── 绑定 CRUD ──

    def create_binding(self, binding: ActionBinding) -> ActionBinding:
        if binding.integration_type not in _VALID_INTEGRATION_TYPES:
            raise ActionBindingError(
                "INVALID_INTEGRATION_TYPE",
                f"未知集成类型: {binding.integration_type}",
            )
        if binding.button_location not in _VALID_BUTTON_LOCATIONS:
            raise ActionBindingError(
                "INVALID_BUTTON_LOCATION",
                f"未知按钮位置: {binding.button_location}",
            )
        with self._lock:
            self._bindings[binding.id] = binding
        return binding

    def get_binding(self, binding_id: str) -> ActionBinding:
        b = self._bindings.get(binding_id)
        if not b:
            raise ActionBindingError("NOT_FOUND", f"绑定 {binding_id} 不存在")
        return b

    def list_bindings(
        self,
        *,
        action_id: str | None = None,
        integration_type: str | None = None,
        target_id: str | None = None,
    ) -> list[ActionBinding]:
        with self._lock:
            items = list(self._bindings.values())
        if action_id:
            items = [b for b in items if b.action_id == action_id]
        if integration_type:
            items = [b for b in items if b.integration_type == integration_type]
        if target_id:
            items = [b for b in items if b.target_id == target_id]
        items.sort(key=lambda b: (b.target_id, b.order))
        return items

    def update_binding(
        self, binding_id: str, updates: dict[str, Any],
    ) -> ActionBinding:
        with self._lock:
            b = self._bindings.get(binding_id)
            if not b:
                raise ActionBindingError("NOT_FOUND", f"绑定 {binding_id} 不存在")
            if "integration_type" in updates and updates["integration_type"] not in _VALID_INTEGRATION_TYPES:
                raise ActionBindingError(
                    "INVALID_INTEGRATION_TYPE",
                    f"未知集成类型: {updates['integration_type']}",
                )
            if "button_location" in updates and updates["button_location"] not in _VALID_BUTTON_LOCATIONS:
                raise ActionBindingError(
                    "INVALID_BUTTON_LOCATION",
                    f"未知按钮位置: {updates['button_location']}",
                )
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(b, k, v)
            return b

    def delete_binding(self, binding_id: str) -> bool:
        with self._lock:
            if binding_id not in self._bindings:
                raise ActionBindingError("NOT_FOUND", f"绑定 {binding_id} 不存在")
            # 同时从按钮组中移除
            for grp in self._button_groups.values():
                if binding_id in grp.action_bindings:
                    grp.action_bindings.remove(binding_id)
            del self._bindings[binding_id]
            return True

    def evaluate_binding(
        self, binding_id: str, context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        b = self.get_binding(binding_id)
        context = context or {}
        visible = True
        if b.visibility_condition:
            visible = self._eval_condition(b.visibility_condition, context)
        return {
            "binding_id": binding_id,
            "action_id": b.action_id,
            "visible": visible and b.enabled,
            "enabled": b.enabled,
            "button_label": b.button_label,
            "button_location": b.button_location,
        }

    # ── 按钮组 CRUD ──

    def create_button_group(self, group: WorkshopButtonGroup) -> WorkshopButtonGroup:
        if group.layout not in _VALID_LAYOUTS:
            raise ActionBindingError(
                "INVALID_LAYOUT",
                f"未知布局: {group.layout}",
            )
        with self._lock:
            self._button_groups[group.id] = group
        return group

    def get_button_group(self, group_id: str) -> WorkshopButtonGroup:
        g = self._button_groups.get(group_id)
        if not g:
            raise ActionBindingError("NOT_FOUND", f"按钮组 {group_id} 不存在")
        return g

    def list_button_groups(
        self, *, workshop_module: str | None = None,
    ) -> list[WorkshopButtonGroup]:
        with self._lock:
            items = list(self._button_groups.values())
        if workshop_module:
            items = [g for g in items if g.workshop_module == workshop_module]
        items.sort(key=lambda g: (g.workshop_module, g.order))
        return items

    def update_button_group(
        self, group_id: str, updates: dict[str, Any],
    ) -> WorkshopButtonGroup:
        with self._lock:
            g = self._button_groups.get(group_id)
            if not g:
                raise ActionBindingError("NOT_FOUND", f"按钮组 {group_id} 不存在")
            if "layout" in updates and updates["layout"] not in _VALID_LAYOUTS:
                raise ActionBindingError(
                    "INVALID_LAYOUT", f"未知布局: {updates['layout']}",
                )
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(g, k, v)
            return g

    def delete_button_group(self, group_id: str) -> bool:
        with self._lock:
            if group_id not in self._button_groups:
                raise ActionBindingError("NOT_FOUND", f"按钮组 {group_id} 不存在")
            del self._button_groups[group_id]
            return True

    def attach_binding(self, group_id: str, binding_id: str) -> WorkshopButtonGroup:
        with self._lock:
            g = self._button_groups.get(group_id)
            if not g:
                raise ActionBindingError("NOT_FOUND", f"按钮组 {group_id} 不存在")
            if binding_id not in self._bindings:
                raise ActionBindingError("NOT_FOUND", f"绑定 {binding_id} 不存在")
            if binding_id not in g.action_bindings:
                g.action_bindings.append(binding_id)
            return g

    def detach_binding(self, group_id: str, binding_id: str) -> WorkshopButtonGroup:
        with self._lock:
            g = self._button_groups.get(group_id)
            if not g:
                raise ActionBindingError("NOT_FOUND", f"按钮组 {group_id} 不存在")
            if binding_id in g.action_bindings:
                g.action_bindings.remove(binding_id)
            return g

    # ── 条件评估（与 SectionEngine 同风格） ──

    def _eval_condition(self, condition: str, context: dict[str, Any]) -> bool:
        condition = condition.strip()
        if not condition:
            return True
        for op in ("!=", ">=", "<=", "==", "=", ">", "<"):
            if op in condition:
                parts = condition.split(op, 1)
                if len(parts) != 2:
                    continue
                field = parts[0].strip()
                target = parts[1].strip().strip("'\"")
                actual = context.get(field)
                if op in ("=", "=="):
                    return str(actual) == target
                elif op == "!=":
                    return str(actual) != target
                else:
                    try:
                        actual_n = float(actual)
                        target_n = float(target)
                    except (ValueError, TypeError):
                        return False
                    if op == ">":
                        return actual_n > target_n
                    elif op == "<":
                        return actual_n < target_n
                    elif op == ">=":
                        return actual_n >= target_n
                    elif op == "<=":
                        return actual_n <= target_n
        return False

    def reset(self) -> None:
        with self._lock:
            self._bindings.clear()
            self._button_groups.clear()


# ─────────────── #70 Action 事务回滚（Saga） ───────────────

class CompensationStep(BaseModel):
    step_id: str
    action_id: str
    order: int
    parameters: dict[str, Any] = Field(default_factory=dict)


class SagaTransaction(BaseModel):
    id: str = Field(default_factory=lambda: _uid("saga"))
    name: str
    forward_steps: list[dict[str, Any]] = Field(default_factory=list)
    compensation_steps: list[CompensationStep] = Field(default_factory=list)
    status: str = "pending"  # pending / running / completed / compensating / compensated / failed
    started_at: str = ""
    completed_at: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)


class SagaStepRecord(BaseModel):
    id: str = Field(default_factory=lambda: _uid("sgr"))
    saga_id: str
    step_id: str
    direction: str   # forward / compensation
    status: str = "pending"  # pending / running / succeeded / failed / skipped
    started_at: str = Field(default_factory=_now)
    completed_at: str = ""
    result: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class SagaError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_VALID_SAGA_STATUSES = {
    "pending", "running", "completed", "compensating", "compensated", "failed",
}
_VALID_STEP_STATUSES = {"pending", "running", "succeeded", "failed", "skipped"}
_SAGA_TRANSITIONS = {
    "pending": {"running"},
    "running": {"completed", "compensating", "failed"},
    "completed": set(),
    "compensating": {"compensated", "failed"},
    "compensated": set(),
    "failed": set(),
}


class SagaEngine:
    """Action Saga 事务回滚引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sagas: dict[str, SagaTransaction] = {}
        self._records: dict[str, SagaStepRecord] = {}

    def create(self, saga: SagaTransaction) -> SagaTransaction:
        # 校验补偿步骤 order 唯一性
        orders = [c.order for c in saga.compensation_steps]
        if len(orders) != len(set(orders)):
            raise SagaError("DUPLICATE_ORDER", "补偿步骤 order 重复")
        with self._lock:
            self._sagas[saga.id] = saga
        return saga

    def get(self, saga_id: str) -> SagaTransaction:
        s = self._sagas.get(saga_id)
        if not s:
            raise SagaError("NOT_FOUND", f"Saga {saga_id} 不存在")
        return s

    def list(self, *, status: str | None = None) -> list[SagaTransaction]:
        with self._lock:
            items = list(self._sagas.values())
        if status:
            items = [s for s in items if s.status == status]
        items.sort(key=lambda s: s.created_at)
        return items

    def update(self, saga_id: str, updates: dict[str, Any]) -> SagaTransaction:
        with self._lock:
            s = self._sagas.get(saga_id)
            if not s:
                raise SagaError("NOT_FOUND", f"Saga {saga_id} 不存在")
            for k, v in updates.items():
                if k == "compensation_steps" and isinstance(v, list):
                    s.compensation_steps = [
                        CompensationStep(**c) if isinstance(c, dict) else c
                        for c in v
                    ]
                elif k not in ("id", "created_at"):
                    setattr(s, k, v)
            return s

    def delete(self, saga_id: str) -> bool:
        with self._lock:
            if saga_id not in self._sagas:
                raise SagaError("NOT_FOUND", f"Saga {saga_id} 不存在")
            # 级联删除步骤记录
            to_remove = [rid for rid, r in self._records.items() if r.saga_id == saga_id]
            for rid in to_remove:
                del self._records[rid]
            del self._sagas[saga_id]
            return True

    def start(self, saga_id: str) -> SagaTransaction:
        """启动 Saga：pending → running，并为每个正向步骤创建 StepRecord。"""
        with self._lock:
            s = self._sagas.get(saga_id)
            if not s:
                raise SagaError("NOT_FOUND", f"Saga {saga_id} 不存在")
            if s.status != "pending":
                raise SagaError(
                    "INVALID_TRANSITION",
                    f"Saga 状态 {s.status} 不允许 start",
                )
            s.status = "running"
            s.started_at = _now()
            # 为正向步骤创建记录
            for step in s.forward_steps:
                step_id = step.get("step_id", step.get("action_id", ""))
                rec = SagaStepRecord(
                    saga_id=saga_id,
                    step_id=step_id,
                    direction="forward",
                    status="pending",
                )
                self._records[rec.id] = rec
            return s

    def compensate(self, saga_id: str) -> SagaTransaction:
        """触发补偿：running/failed → compensating，按 order 倒序创建补偿记录。"""
        with self._lock:
            s = self._sagas.get(saga_id)
            if not s:
                raise SagaError("NOT_FOUND", f"Saga {saga_id} 不存在")
            if s.status not in ("running", "failed"):
                raise SagaError(
                    "INVALID_TRANSITION",
                    f"Saga 状态 {s.status} 不允许 compensate",
                )
            s.status = "compensating"
            # 按 order 倒序创建补偿记录
            sorted_steps = sorted(s.compensation_steps, key=lambda c: -c.order)
            for step in sorted_steps:
                rec = SagaStepRecord(
                    saga_id=saga_id,
                    step_id=step.step_id,
                    direction="compensation",
                    status="pending",
                )
                self._records[rec.id] = rec
            return s

    def list_records(
        self, saga_id: str, *, direction: str | None = None,
    ) -> list[SagaStepRecord]:
        with self._lock:
            items = [r for r in self._records.values() if r.saga_id == saga_id]
        if direction:
            items = [r for r in items if r.direction == direction]
        items.sort(key=lambda r: r.started_at)
        return items

    def update_record_status(
        self, saga_id: str, record_id: str, new_status: str,
    ) -> SagaStepRecord:
        if new_status not in _VALID_STEP_STATUSES:
            raise SagaError("INVALID_STATUS", f"未知步骤状态: {new_status}")
        with self._lock:
            rec = self._records.get(record_id)
            if not rec:
                raise SagaError("NOT_FOUND", f"步骤记录 {record_id} 不存在")
            if rec.saga_id != saga_id:
                raise SagaError("MISMATCH", f"记录 {record_id} 不属于 Saga {saga_id}")
            rec.status = new_status
            if new_status in ("succeeded", "failed", "skipped"):
                rec.completed_at = _now()
            # 检查是否所有 forward 步骤完成 → 自动转 completed
            s = self._sagas.get(saga_id)
            if s and s.status == "running":
                forward_recs = [
                    r for r in self._records.values()
                    if r.saga_id == saga_id and r.direction == "forward"
                ]
                if forward_recs and all(r.status == "succeeded" for r in forward_recs):
                    s.status = "completed"
                    s.completed_at = _now()
            # 检查是否所有 compensation 步骤完成 → 自动转 compensated
            if s and s.status == "compensating":
                comp_recs = [
                    r for r in self._records.values()
                    if r.saga_id == saga_id and r.direction == "compensation"
                ]
                if comp_recs and all(
                    r.status in ("succeeded", "skipped") for r in comp_recs
                ):
                    s.status = "compensated"
                    s.completed_at = _now()
                elif any(r.status == "failed" for r in comp_recs):
                    s.status = "failed"
                    s.completed_at = _now()
            return rec

    def get_state(self, saga_id: str) -> dict[str, Any]:
        s = self.get(saga_id)
        records = self.list_records(saga_id)
        forward_recs = [r for r in records if r.direction == "forward"]
        comp_recs = [r for r in records if r.direction == "compensation"]
        return {
            "saga_id": saga_id,
            "name": s.name,
            "status": s.status,
            "started_at": s.started_at,
            "completed_at": s.completed_at,
            "total_forward_steps": len(s.forward_steps),
            "total_compensation_steps": len(s.compensation_steps),
            "forward_progress": {
                "succeeded": sum(1 for r in forward_recs if r.status == "succeeded"),
                "failed": sum(1 for r in forward_recs if r.status == "failed"),
                "pending": sum(1 for r in forward_recs if r.status == "pending"),
                "running": sum(1 for r in forward_recs if r.status == "running"),
            },
            "compensation_progress": {
                "succeeded": sum(1 for r in comp_recs if r.status == "succeeded"),
                "failed": sum(1 for r in comp_recs if r.status == "failed"),
                "pending": sum(1 for r in comp_recs if r.status == "pending"),
                "skipped": sum(1 for r in comp_recs if r.status == "skipped"),
            },
        }

    def reset(self) -> None:
        with self._lock:
            self._sagas.clear()
            self._records.clear()


# ─────────────── 单例 ───────────────

_log_engine: ActionLogEngine | None = None
_binding_engine: ActionBindingEngine | None = None
_saga_engine: SagaEngine | None = None
_lock = threading.Lock()


def get_action_log_engine() -> ActionLogEngine:
    global _log_engine
    if _log_engine is None:
        with _lock:
            if _log_engine is None:
                _log_engine = ActionLogEngine()
    return _log_engine


def get_action_binding_engine() -> ActionBindingEngine:
    global _binding_engine
    if _binding_engine is None:
        with _lock:
            if _binding_engine is None:
                _binding_engine = ActionBindingEngine()
    return _binding_engine


def get_saga_engine() -> SagaEngine:
    global _saga_engine
    if _saga_engine is None:
        with _lock:
            if _saga_engine is None:
                _saga_engine = SagaEngine()
    return _saga_engine
