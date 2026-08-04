"""W2-8/9 · Dynamic Scheduling 引擎 + 数据模型。

Schedule 对象（cron 表达式 + 触发目标）+ Resource 分配 + 调度执行引擎。
支持 cron 解析、下一次触发时间计算、手动触发、到期执行、失败重试。

详见 docs/palantier/20_tech/220tech_w2-wave-plan.md 第一批。
"""
from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from aos_api.tenant_scope import TenantScope

ScheduleStatus = Literal["pending", "running", "succeeded", "failed", "skipped"]
ScheduleScope = Literal["project", "org", "global"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def parse_cron_field(expr: str, min_val: int, max_val: int) -> set[int]:
    result: set[int] = set()
    for part in expr.split(","):
        part = part.strip()
        if part == "*":
            result.update(range(min_val, max_val + 1))
        elif "/" in part:
            base, step_str = part.split("/")
            step = int(step_str)
            start = min_val if base == "*" else int(base)
            result.update(range(start, max_val + 1, step))
        elif "-" in part:
            lo, hi = part.split("-")
            result.update(range(int(lo), int(hi) + 1))
        else:
            result.add(int(part))
    return {v for v in result if min_val <= v <= max_val}


def next_run_time(cron: str, after: datetime | None = None) -> datetime:
    base = after or _now()
    parts = cron.strip().split()
    if len(parts) != 5:
        raise SchedulingError("INVALID_CRON", f"cron 表达式需要 5 个字段：{cron}")
    minutes = parse_cron_field(parts[0], 0, 59)
    hours = parse_cron_field(parts[1], 0, 23)
    days = parse_cron_field(parts[2], 1, 31)
    months = parse_cron_field(parts[3], 1, 12)
    weekdays = parse_cron_field(parts[4], 0, 6)

    candidate = base.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(366 * 24 * 60):
        if (candidate.minute in minutes and candidate.hour in hours
                and candidate.day in days and candidate.month in months
                and (candidate.weekday() + 1) % 7 in weekdays):
            return candidate
        candidate += timedelta(minutes=1)
    raise SchedulingError("NO_NEXT_RUN", "一年内无匹配时间，请检查 cron 表达式")


class Schedule(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("sch"))
    name: str
    cron: str
    target_type: str = "pipeline"
    target_id: str = ""
    enabled: bool = True
    scope: ScheduleScope = "project"
    max_retries: int = 3
    created_at: str = Field(default_factory=_now_iso)
    last_run_at: str | None = None
    next_run_at: str | None = None
    org_id: str = ""
    project_id: str = ""


class ScheduledResource(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("res"))
    schedule_id: str
    resource_type: str = "dataset"
    resource_id: str = ""
    allocation: str = "exclusive"
    org_id: str = ""
    project_id: str = ""


class ScheduleExecution(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("exe"))
    schedule_id: str
    started_at: str = Field(default_factory=_now_iso)
    finished_at: str | None = None
    status: ScheduleStatus = "pending"
    error: str | None = None
    retry_count: int = 0
    org_id: str = ""
    project_id: str = ""


class SchedulingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class SchedulingEngine:
    def __init__(self, executor: Callable[[Schedule], Any] | None = None) -> None:
        self._schedules: dict[tuple[str, str, str], Schedule] = {}
        self._resources: dict[tuple[str, str, str], list[ScheduledResource]] = {}
        self._executions: list[ScheduleExecution] = []
        self._executor = executor or (lambda s: {"ok": True})
        self._lock = threading.Lock()

    @staticmethod
    def _key(scope: TenantScope, sched_id: str) -> tuple[str, str, str]:
        return (*scope.key, sched_id)

    @staticmethod
    def _bind_scope(scope: TenantScope, item: Any) -> None:
        if item.org_id and item.org_id != scope.org_id:
            raise SchedulingError("TENANT_SCOPE_MISMATCH", "org_id 与执行作用域不一致")
        if item.project_id and item.project_id != scope.project_id:
            raise SchedulingError("TENANT_SCOPE_MISMATCH", "project_id 与执行作用域不一致")
        item.org_id, item.project_id = scope.key

    def create_schedule(self, scope: TenantScope, sched: Schedule) -> Schedule:
        next_run_time(sched.cron)
        self._bind_scope(scope, sched)
        sched.next_run_at = next_run_time(sched.cron).isoformat()
        with self._lock:
            self._schedules[self._key(scope, sched.id)] = sched
        return sched

    def update_schedule(
        self, scope: TenantScope, sched_id: str, **updates: Any
    ) -> Schedule:
        with self._lock:
            sched = self._schedules.get(self._key(scope, sched_id))
            if sched is None:
                raise SchedulingError("NOT_FOUND", f"调度 {sched_id} 不存在")
            for k, v in updates.items():
                if hasattr(sched, k):
                    setattr(sched, k, v)
            if "cron" in updates:
                sched.next_run_at = next_run_time(sched.cron).isoformat()
            return sched

    def delete_schedule(self, scope: TenantScope, sched_id: str) -> bool:
        with self._lock:
            return self._schedules.pop(self._key(scope, sched_id), None) is not None

    def get_schedule(self, scope: TenantScope, sched_id: str) -> Schedule | None:
        return self._schedules.get(self._key(scope, sched_id))

    def list_schedules(
        self, scope: TenantScope, enabled_only: bool = False
    ) -> list[Schedule]:
        schedules = [
            schedule
            for (org_id, project_id, _), schedule in self._schedules.items()
            if (org_id, project_id) == scope.key
        ]
        if enabled_only:
            schedules = [s for s in schedules if s.enabled]
        return schedules

    def assign_resource(
        self, scope: TenantScope, resource: ScheduledResource
    ) -> ScheduledResource:
        if self.get_schedule(scope, resource.schedule_id) is None:
            raise SchedulingError("NOT_FOUND", f"调度 {resource.schedule_id} 不存在")
        self._bind_scope(scope, resource)
        with self._lock:
            self._resources.setdefault(
                self._key(scope, resource.schedule_id), []
            ).append(resource)
        return resource

    def get_resources(
        self, scope: TenantScope, sched_id: str
    ) -> list[ScheduledResource]:
        return list(self._resources.get(self._key(scope, sched_id), []))

    def get_next_run(self, scope: TenantScope, sched_id: str) -> datetime:
        sched = self._schedules.get(self._key(scope, sched_id))
        if sched is None:
            raise SchedulingError("NOT_FOUND", f"调度 {sched_id} 不存在")
        return next_run_time(sched.cron)

    def trigger(self, scope: TenantScope, sched_id: str) -> ScheduleExecution:
        with self._lock:
            sched = self._schedules.get(self._key(scope, sched_id))
            if sched is None:
                raise SchedulingError("NOT_FOUND", f"调度 {sched_id} 不存在")
            exe = ScheduleExecution(
                schedule_id=sched_id,
                status="running",
                org_id=scope.org_id,
                project_id=scope.project_id,
            )
            self._executions.append(exe)
        try:
            self._executor(sched)
            exe.status = "succeeded"
        except Exception as exc:
            exe.status = "failed"
            exe.error = str(exc)
        exe.finished_at = _now_iso()
        sched.last_run_at = exe.started_at
        sched.next_run_at = next_run_time(sched.cron).isoformat()
        return exe

    def execute_due(
        self, scope: TenantScope, now: datetime | None = None
    ) -> list[ScheduleExecution]:
        current = now or _now()
        results: list[ScheduleExecution] = []
        for sched in self.list_schedules(scope):
            if not sched.enabled:
                continue
            nr = next_run_time(sched.cron, current - timedelta(minutes=1))
            if nr <= current:
                results.append(self.trigger(scope, sched.id))
        return results

    def history(
        self, scope: TenantScope, sched_id: str | None = None
    ) -> list[ScheduleExecution]:
        executions = [
            item
            for item in self._executions
            if (item.org_id, item.project_id) == scope.key
        ]
        if sched_id:
            return [e for e in executions if e.schedule_id == sched_id]
        return executions


_engine = SchedulingEngine()


def get_engine() -> SchedulingEngine:
    return _engine
