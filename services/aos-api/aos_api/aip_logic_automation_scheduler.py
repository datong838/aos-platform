"""Tenant-rebound minute scheduler for internal-only Logic automation runs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from aos_api.automation_occurrence_store import AutomationOccurrenceStore, ScheduleBinding
from aos_api.aip_logic_automation_cron import cron_matches
from aos_api.aip_logic_automation_store import LogicAutomationStore
from aos_api.aip_task_service import AipTaskService
from aos_api.aip_task_store import AipTaskStore
from aos_api.auth import Principal
from aos_api.routers.aip_logic_automations import dispatch_logic_automation
from aos_api.tenant_scope import TenantScope


def run_due_logic_automations(
    *,
    now: datetime | None = None,
    store: LogicAutomationStore | None = None,
    task_service_factory: Callable[[], AipTaskService] | None = None,
) -> dict[str, int]:
    moment = (now or datetime.now(UTC)).astimezone(UTC).replace(second=0, microsecond=0)
    authority = store or LogicAutomationStore()
    make_tasks = task_service_factory or (lambda: AipTaskService(AipTaskStore()))
    matched = accepted = failed = 0
    for org_id, project_id, policy in authority.list_active_cron_targets():
        try:
            if not cron_matches(policy.schedule, moment):
                continue
            matched += 1
            principal = Principal(
                subject="system:logic-automation-scheduler",
                org_id=org_id,
                project_id=project_id,
                roles=["system"],
                markings=["internal"],
                token_kind="system",
            )
            request_key = f"cron:{moment.strftime('%Y%m%d%H%M')}"
            dispatch_logic_automation(
                principal,
                policy,
                authority,
                make_tasks(),
                request_key=request_key,
                trigger="cron",
            )
            accepted += 1
        except Exception:
            failed += 1
    return {"matched": matched, "accepted": accepted, "failed": failed}


def run_due_schedule_binding(
    scope: TenantScope,
    binding: ScheduleBinding,
    *,
    watermark: datetime | None,
    now: datetime,
    store: AutomationOccurrenceStore | None = None,
) -> dict[str, int]:
    """Enumerate a once or weekly binding and persist its due slots atomically."""
    if binding.cadence not in {"once", "weekly"}:
        raise ValueError("natural-slot scheduler requires a once or weekly binding")
    if now.utcoffset() is None:
        raise ValueError("scheduler time must include timezone")
    moment = now.astimezone(UTC).replace(microsecond=0)
    if binding.cadence == "once":
        return _run_due_once_schedule_binding(
            scope, binding, watermark=watermark, moment=moment, store=store,
        )
    if binding.weekly_day is None or binding.local_time is None:
        raise ValueError("weekly binding requires weekday and local time")
    start = (watermark or binding.effective_from).astimezone(UTC).replace(microsecond=0)
    if moment < start or (watermark is not None and moment == start):
        return {"due": 0, "pending": 0, "missed": 0}
    timezone = ZoneInfo("Asia/Shanghai")
    hour, minute = (int(part) for part in binding.local_time.split(":"))
    local_day = start.astimezone(timezone).date()
    final_day = moment.astimezone(timezone).date()
    due: list[datetime] = []
    while local_day <= final_day:
        local_slot = datetime(
            local_day.year, local_day.month, local_day.day, hour, minute, tzinfo=timezone
        )
        scheduled = local_slot.astimezone(UTC)
        if (
            local_day.isoweekday() == binding.weekly_day
            and (scheduled >= start if watermark is None else scheduled > start)
            and scheduled <= moment
            and scheduled >= binding.effective_from.astimezone(UTC)
            and (
                binding.effective_until is None
                or scheduled < binding.effective_until.astimezone(UTC)
            )
        ):
            due.append(scheduled)
        local_day += timedelta(days=1)
    most_recent_recoverable = next(
        (slot for slot in reversed(due) if moment - slot <= timedelta(hours=24)), None
    )
    slots = []
    for slot in due:
        status = "pending" if slot == most_recent_recoverable else "missed"
        local_slot = slot.astimezone(timezone).strftime("%Y-%m-%dT%H:%M%z")
        slots.append((slot, local_slot, max(moment, slot) + timedelta(hours=24), status))
    (store or AutomationOccurrenceStore()).record_due_batch(
        scope,
        binding,
        expected_watermark=watermark,
        new_watermark=moment,
        slots=slots,
    )
    return {
        "due": len(slots),
        "pending": sum(item[3] == "pending" for item in slots),
        "missed": sum(item[3] == "missed" for item in slots),
    }


def _run_due_once_schedule_binding(
    scope: TenantScope,
    binding: ScheduleBinding,
    *,
    watermark: datetime | None,
    moment: datetime,
    store: AutomationOccurrenceStore | None,
) -> dict[str, int]:
    """Persist the single effective-from slot once; restarts cannot create another."""
    slot = binding.effective_from.astimezone(UTC).replace(microsecond=0)
    if watermark is not None or moment < slot:
        return {"due": 0, "pending": 0, "missed": 0}
    if binding.effective_until is not None and slot >= binding.effective_until.astimezone(UTC):
        raise ValueError("once slot is outside the binding effective interval")
    status = "pending" if moment - slot <= timedelta(hours=24) else "missed"
    local_slot = slot.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%dT%H:%M%z")
    (store or AutomationOccurrenceStore()).record_due_batch(
        scope,
        binding,
        expected_watermark=None,
        new_watermark=moment,
        slots=[(slot, local_slot, max(moment, slot) + timedelta(hours=24), status)],
    )
    return {
        "due": 1,
        "pending": int(status == "pending"),
        "missed": int(status == "missed"),
    }
