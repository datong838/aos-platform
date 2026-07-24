"""W2-#10 · Dynamic Scheduling 甘特图测试。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aos_api.gantt import (
    ALLOCATION_BEHAVIORS,
    GanttEngine,
    GanttError,
    list_allocation_behaviors,
)
from aos_api.scheduling_engine import (
    Schedule,
    ScheduledResource,
    SchedulingEngine,
)


@pytest.fixture
def engine_with_data() -> SchedulingEngine:
    eng = SchedulingEngine(executor=lambda s: None)
    s1 = eng.create_schedule(Schedule(
        id="sch-1", name="每小时任务", cron="0 * * * *", scope="project",
    ))
    eng.assign_resource(ScheduledResource(
        id="res-1", schedule_id="sch-1", resource_type="dataset",
        resource_id="ds-core", allocation="exclusive",
    ))
    eng.create_schedule(Schedule(
        id="sch-2", name="每日任务", cron="0 2 * * *", scope="org",
    ))
    return eng


def _force_history(eng: SchedulingEngine, sched_id: str, minutes_ago: int = 30, duration: int = 10):
    from aos_api.scheduling_engine import ScheduleExecution
    start = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    exe = ScheduleExecution(
        id="exe-x", schedule_id=sched_id, started_at=start.isoformat(),
        finished_at=(start + timedelta(minutes=duration)).isoformat(),
        status="succeeded",
    )
    eng._executions.append(exe)
    return exe


# ---------- 视图构建 ----------


def test_build_view_returns_bars(engine_with_data: SchedulingEngine):
    gantt = GanttEngine(engine_with_data)
    view = gantt.build_view(scope="all", horizon_hours=24)
    assert view.total_bars > 0
    planned = [b for b in sum((l.bars for l in view.lanes), []) if b.kind == "planned"]
    assert len(planned) > 0


def test_build_view_scope_filter(engine_with_data: SchedulingEngine):
    gantt = GanttEngine(engine_with_data)
    project_view = gantt.build_view(scope="project", horizon_hours=24)
    org_view = gantt.build_view(scope="org", horizon_hours=24)
    project_schedules = {b.schedule_id for l in project_view.lanes for b in l.bars}
    org_schedules = {b.schedule_id for l in org_view.lanes for b in l.bars}
    assert "sch-1" in project_schedules
    assert "sch-2" in org_schedules


def test_build_view_includes_historical(engine_with_data: SchedulingEngine):
    _force_history(engine_with_data, "sch-1")
    gantt = GanttEngine(engine_with_data)
    view = gantt.build_view(scope="all", horizon_hours=24)
    all_bars = [b for l in view.lanes for b in l.bars]
    historical = [b for b in all_bars if b.kind == "historical"]
    assert len(historical) >= 1
    assert historical[0].status == "succeeded"


def test_invalid_horizon_raises(engine_with_data: SchedulingEngine):
    gantt = GanttEngine(engine_with_data)
    with pytest.raises(GanttError) as exc:
        gantt.build_view(horizon_hours=99999)
    assert exc.value.code == "INVALID_HORIZON"


def test_build_for_schedule(engine_with_data: SchedulingEngine):
    gantt = GanttEngine(engine_with_data)
    view = gantt.build_for_schedule("sch-1", horizon_hours=48)
    assert view.total_bars > 0
    schedule_ids = {b.schedule_id for l in view.lanes for b in l.bars}
    assert schedule_ids == {"sch-1"}


def test_build_for_schedule_unknown_raises(engine_with_data: SchedulingEngine):
    gantt = GanttEngine(engine_with_data)
    with pytest.raises(GanttError) as exc:
        gantt.build_for_schedule("ghost")
    assert exc.value.code == "NOT_FOUND"


# ---------- 违规检测 ----------


def test_resource_overlap_violation():
    eng = SchedulingEngine(executor=lambda s: None)
    s1 = eng.create_schedule(Schedule(id="s1", name="任务A", cron="0 * * * *"))
    s2 = eng.create_schedule(Schedule(id="s2", name="任务B", cron="0 * * * *"))
    for sid in ("s1", "s2"):
        eng.assign_resource(ScheduledResource(
            id=f"r-{sid}", schedule_id=sid, resource_type="dataset",
            resource_id="shared-ds", allocation="exclusive",
        ))
    gantt = GanttEngine(eng)
    view = gantt.build_view(scope="all", horizon_hours=2)
    overlaps = [v for v in view.violations if v.type == "resource_overlap"]
    assert len(overlaps) > 0


def test_disabled_schedule_violation():
    eng = SchedulingEngine(executor=lambda s: None)
    s1 = eng.create_schedule(Schedule(
        id="s1", name="禁用任务", cron="0 * * * *", enabled=False,
    ))
    gantt = GanttEngine(eng)
    view = gantt.build_view(scope="all", horizon_hours=2, include_disabled=True)
    disabled_violations = [v for v in view.violations if v.type == "disabled"]
    assert len(disabled_violations) > 0


def test_overtime_violation():
    eng = SchedulingEngine(executor=lambda s: None)
    eng.create_schedule(Schedule(id="s1", name="任务", cron="0 * * * *"))
    from aos_api.scheduling_engine import ScheduleExecution
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    eng._executions.append(ScheduleExecution(
        id="exe-ot", schedule_id="s1", started_at=start.isoformat(),
        finished_at=datetime.now(timezone.utc).isoformat(),
        status="succeeded",
    ))
    gantt = GanttEngine(eng)
    view = gantt.build_view(scope="all", horizon_hours=1, duration_minutes=60)
    overtime = [v for v in view.violations if v.type == "overtime"]
    assert len(overtime) >= 1


def test_no_violations_for_non_overlapping():
    eng = SchedulingEngine(executor=lambda s: None)
    eng.create_schedule(Schedule(id="s1", name="任务", cron="0 0 1 1 *"))
    gantt = GanttEngine(eng)
    view = gantt.build_view(scope="all", horizon_hours=2)
    assert view.violations == [] or all(v.type != "resource_overlap" for v in view.violations)


# ---------- 分配行为目录 ----------


def test_allocation_behaviors_has_five():
    behaviors = list_allocation_behaviors()
    assert len(behaviors) == 5
    names = {b["behavior"] for b in behaviors}
    assert names == {"none", "split", "share", "overtime", "reassign"}


def test_allocation_behaviors_descriptions_present():
    for item in list_allocation_behaviors():
        assert item["description"]


# ---------- 边界 ----------


def test_empty_engine_returns_empty_view():
    eng = SchedulingEngine(executor=lambda s: None)
    gantt = GanttEngine(eng)
    view = gantt.build_view(scope="all", horizon_hours=24)
    assert view.total_bars == 0
    assert view.lanes == []
    assert view.violations == []
