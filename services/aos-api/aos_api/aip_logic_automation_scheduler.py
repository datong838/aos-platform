"""Tenant-rebound minute scheduler for internal-only Logic automation runs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable

from aos_api.aip_logic_automation_cron import cron_matches
from aos_api.aip_logic_automation_store import LogicAutomationStore
from aos_api.aip_task_service import AipTaskService
from aos_api.aip_task_store import AipTaskStore
from aos_api.auth import Principal
from aos_api.routers.aip_logic_automations import dispatch_logic_automation


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
