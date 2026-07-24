"""W2-#10 · Dynamic Scheduling 甘特图。

纯只读视图引擎：聚合 schedule/resource/execution，派生 violations。
不改 scheduling_engine.py（最小更改原则）。

详见 docs/palantier/20_tech/220tech_w2-d-gantt-tx.md §2/§3。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from .scheduling_engine import Schedule, SchedulingEngine, get_engine, next_run_time


BarKind = Literal["planned", "historical"]
ViolationType = Literal["resource_overlap", "overtime", "disabled"]
AllocationBehavior = Literal[
    "none",
    "split",
    "share",
    "overtime",
    "reassign",
]


class GanttBar(BaseModel):
    schedule_id: str
    schedule_name: str
    bar_id: str = Field(default_factory=lambda: "bar-" + uuid.uuid4().hex[:8])
    start: str
    end: str
    kind: BarKind
    status: str = ""
    resources: list[dict[str, Any]] = Field(default_factory=list)


class GanttViolation(BaseModel):
    type: ViolationType
    bar_ids: list[str]
    message: str


class GanttLane(BaseModel):
    resource_type: str
    resource_id: str
    bars: list[GanttBar] = Field(default_factory=list)


class GanttView(BaseModel):
    scope: str
    horizon_start: str
    horizon_end: str
    lanes: list[GanttLane] = Field(default_factory=list)
    violations: list[GanttViolation] = Field(default_factory=list)
    total_bars: int = 0


class GanttError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_MAX_HORIZON_HOURS = 720
_DEFAULT_DURATION_MINUTES = 60
_MAX_PROJECTION = 1000


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _project_future_runs(
    schedule: Schedule, horizon_end: datetime, duration_minutes: int, include_disabled: bool = True
) -> list[GanttBar]:
    bars: list[GanttBar] = []
    if not schedule.enabled and not include_disabled:
        return bars
    try:
        cursor = next_run_time(schedule.cron, _now_utc() - timedelta(minutes=1))
    except Exception:
        return bars
    for _ in range(_MAX_PROJECTION):
        if cursor > horizon_end:
            break
        end = cursor + timedelta(minutes=duration_minutes)
        bars.append(GanttBar(
            schedule_id=schedule.id,
            schedule_name=schedule.name,
            start=cursor.isoformat(),
            end=end.isoformat(),
            kind="planned",
            resources=[],
        ))
        try:
            cursor = next_run_time(schedule.cron, cursor)
        except Exception:
            break
    return bars


def _historical_bars(
    schedule: Schedule, executions: list[Any]
) -> list[GanttBar]:
    bars: list[GanttBar] = []
    for exe in executions:
        if exe.schedule_id != schedule.id:
            continue
        start = _parse_iso(exe.started_at) if exe.started_at else _now_utc()
        end = _parse_iso(exe.finished_at) if exe.finished_at else _now_utc()
        bars.append(GanttBar(
            schedule_id=schedule.id,
            schedule_name=schedule.name,
            start=start.isoformat(),
            end=end.isoformat(),
            kind="historical",
            status=exe.status,
            resources=[],
        ))
    return bars


def _attach_resources(bars: list[GanttBar], resources: list[Any]) -> list[GanttBar]:
    if not resources:
        default_res = [{"resource_type": "default", "resource_id": "default", "allocation": "share"}]
        return [b.model_copy(update={"resources": default_res}) for b in bars]
    res_dicts = [
        {"resource_type": r.resource_type, "resource_id": r.resource_id, "allocation": r.allocation}
        for r in resources
    ]
    return [b.model_copy(update={"resources": res_dicts}) for b in bars]


def _detect_violations(
    all_bars: list[GanttBar],
    schedule_enabled_map: dict[str, bool],
    planned_duration_minutes: int,
) -> list[GanttViolation]:
    violations: list[GanttViolation] = []

    exclusive_pairs: dict[tuple[str, str], list[GanttBar]] = {}
    for bar in all_bars:
        for res in bar.resources:
            if res.get("allocation") == "exclusive":
                key = (res["resource_type"], res["resource_id"])
                exclusive_pairs.setdefault(key, []).append(bar)
    for (rtype, rid), group in exclusive_pairs.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a_start = _parse_iso(group[i].start)
                a_end = _parse_iso(group[i].end)
                b_start = _parse_iso(group[j].start)
                b_end = _parse_iso(group[j].end)
                if a_start < b_end and b_start < a_end:
                    violations.append(GanttViolation(
                        type="resource_overlap",
                        bar_ids=[group[i].bar_id, group[j].bar_id],
                        message=f"资源 {rtype}/{rid} 独占分配冲突：{group[i].schedule_name} 与 {group[j].schedule_name} 时间重叠",
                    ))

    overtime_limit = planned_duration_minutes * 2
    for bar in all_bars:
        if bar.kind != "historical":
            continue
        try:
            duration = (_parse_iso(bar.end) - _parse_iso(bar.start)).total_seconds() / 60
        except Exception:
            continue
        if duration > overtime_limit and overtime_limit > 0:
            violations.append(GanttViolation(
                type="overtime",
                bar_ids=[bar.bar_id],
                message=f"{bar.schedule_name} 执行超时：实际 {int(duration)} 分钟 > 计划 {overtime_limit} 分钟",
            ))

    for bar in all_bars:
        if bar.kind == "planned" and not schedule_enabled_map.get(bar.schedule_id, True):
            violations.append(GanttViolation(
                type="disabled",
                bar_ids=[bar.bar_id],
                message=f"{bar.schedule_name} 已禁用但仍出现在计划视图中",
            ))

    return violations


class GanttEngine:
    """甘特图视图引擎：只读组装，派生违规。"""

    def __init__(self, engine: SchedulingEngine | None = None) -> None:
        self._engine = engine or get_engine()

    def build_view(
        self,
        scope: str = "project",
        horizon_hours: int = 168,
        duration_minutes: int = _DEFAULT_DURATION_MINUTES,
        include_disabled: bool = True,
    ) -> GanttView:
        if horizon_hours < 1 or horizon_hours > _MAX_HORIZON_HOURS:
            raise GanttError("INVALID_HORIZON", f"horizon_hours 须在 1-{_MAX_HORIZON_HOURS} 之间")
        now = _now_utc()
        horizon_end = now + timedelta(hours=horizon_hours)
        schedules = self._engine.list_schedules(enabled_only=False)
        scoped = [s for s in schedules if scope == "all" or s.scope == scope]
        all_bars: list[GanttBar] = []
        resource_index: dict[tuple[str, str], list[GanttBar]] = {}
        executions = self._engine.history()
        enabled_map: dict[str, bool] = {}

        for sched in scoped:
            enabled_map[sched.id] = sched.enabled
            planned = _project_future_runs(sched, horizon_end, duration_minutes, include_disabled=include_disabled)
            historical = _historical_bars(sched, executions)
            resources = self._engine.get_resources(sched.id)
            bars = _attach_resources(planned + historical, resources)
            if not include_disabled and not sched.enabled:
                bars = [b for b in bars if b.kind == "historical"]
            all_bars.extend(bars)
            for bar in bars:
                for res in bar.resources:
                    key = (res["resource_type"], res["resource_id"])
                    resource_index.setdefault(key, []).append(bar)

        lanes = [
            GanttLane(resource_type=rtype, resource_id=rid, bars=bars)
            for (rtype, rid), bars in resource_index.items()
        ]
        violations = _detect_violations(all_bars, enabled_map, duration_minutes)
        return GanttView(
            scope=scope,
            horizon_start=now.isoformat(),
            horizon_end=horizon_end.isoformat(),
            lanes=lanes,
            violations=violations,
            total_bars=len(all_bars),
        )

    def build_for_schedule(
        self,
        sched_id: str,
        horizon_hours: int = 168,
        duration_minutes: int = _DEFAULT_DURATION_MINUTES,
    ) -> GanttView:
        sched = self._engine.get_schedule(sched_id)
        if sched is None:
            raise GanttError("NOT_FOUND", f"调度 {sched_id!r} 不存在")
        now = _now_utc()
        horizon_end = now + timedelta(hours=horizon_hours)
        executions = self._engine.history(sched_id)
        resources = self._engine.get_resources(sched_id)
        planned = _project_future_runs(sched, horizon_end, duration_minutes)
        historical = _historical_bars(sched, executions)
        bars = _attach_resources(planned + historical, resources)
        violations = _detect_violations(bars, {sched.id: sched.enabled}, duration_minutes)
        lanes = [
            GanttLane(resource_type=res["resource_type"], resource_id=res["resource_id"],
                      bars=[b for b in bars if any(r["resource_id"] == res["resource_id"] for r in b.resources)])
            for res in ({(r["resource_type"], r["resource_id"]): r for b in bars for r in b.resources}).values()
        ]
        return GanttView(
            scope=sched.scope,
            horizon_start=now.isoformat(),
            horizon_end=horizon_end.isoformat(),
            lanes=lanes,
            violations=violations,
            total_bars=len(bars),
        )


_engine = GanttEngine()


def get_engine() -> GanttEngine:
    return _engine


ALLOCATION_BEHAVIORS: list[dict[str, Any]] = [
    {"behavior": "none", "description": "不允许冲突，直接报错"},
    {"behavior": "split", "description": "拆分时间段"},
    {"behavior": "share", "description": "共享资源（并行）"},
    {"behavior": "overtime", "description": "允许超时占用"},
    {"behavior": "reassign", "description": "重新分配到其他资源"},
]


def list_allocation_behaviors() -> list[dict[str, Any]]:
    return [dict(item) for item in ALLOCATION_BEHAVIORS]
