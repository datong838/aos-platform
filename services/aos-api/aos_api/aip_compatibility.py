"""Explicit AIP v1 legacy compatibility and sunset decisions."""
from __future__ import annotations

from dataclasses import dataclass

from aos_api.aip_contracts import StepRunStatus, TaskRunStatus
from aos_api.public_contracts import ContractViolation, TaskStatus, normalize_task_status


@dataclass(frozen=True)
class RouteCompatibility:
    method: str
    path: str
    authority: str
    removed_authority: str
    disposition: str


ROUTE_COMPATIBILITY = (
    RouteCompatibility("GET", "/v1/aip/capabilities", "wave_ext", "phase3_aip_capabilities", "removed-duplicate"),
    RouteCompatibility("POST", "/v1/aip/circuit/trip", "wave_ext", "phase3_aip_tools", "removed-duplicate"),
    RouteCompatibility("GET", "/v1/aip/drafts", "routers.drafts", "phase3_aip_drafts", "removed-duplicate"),
    RouteCompatibility("GET", "/v1/aip/drafts/{draft_id}", "routers.drafts", "phase3_aip_drafts", "removed-duplicate"),
    RouteCompatibility("POST", "/v1/aip/drafts/{draft_id}/approve", "runtime_write", "phase3_aip_drafts", "removed-duplicate"),
    RouteCompatibility("POST", "/v1/aip/drafts/{draft_id}/reject", "routers.drafts", "phase3_aip_drafts", "removed-duplicate"),
    RouteCompatibility("GET", "/v1/aip/evals", "wave_ext", "phase3_aip_tools", "removed-duplicate"),
    RouteCompatibility("GET", "/v1/aip/insights", "decision_audit", "wave_ext", "removed-duplicate"),
    RouteCompatibility("GET", "/v1/aip/tools", "wave_ext", "phase3_aip_tools", "removed-duplicate"),
    RouteCompatibility("POST", "/v1/aip/drafts/{draft_id}/transition", "none", "phase3_aip_drafts", "removed-unsafe"),
)


LEGACY_TASK_RUN_STATUS: dict[str, TaskRunStatus] = {
    "pending": TaskRunStatus.QUEUED,
    "executing": TaskRunStatus.RUNNING,
    "completed": TaskRunStatus.SUCCEEDED,
    "failed": TaskRunStatus.FAILED,
    "cancelled": TaskRunStatus.CANCELLED,
    "unknown": TaskRunStatus.UNKNOWN,
}
LEGACY_STEP_RUN_STATUS: dict[str, StepRunStatus] = {
    "pending": StepRunStatus.QUEUED,
    "running": StepRunStatus.RUNNING,
    "completed": StepRunStatus.SUCCEEDED,
    "failed": StepRunStatus.FAILED,
    "skipped": StepRunStatus.SKIPPED,
    "unknown": StepRunStatus.UNKNOWN,
}


def map_legacy_task_status(value: str) -> TaskStatus:
    return normalize_task_status(value)


def map_legacy_task_run_status(value: str) -> TaskRunStatus:
    try:
        return LEGACY_TASK_RUN_STATUS[value.strip().lower()]
    except KeyError as exc:
        raise ContractViolation("AIP_LEGACY_STATUS_UNMAPPABLE", "legacy task-run status is not mappable") from exc


def map_legacy_step_run_status(value: str) -> StepRunStatus:
    try:
        return LEGACY_STEP_RUN_STATUS[value.strip().lower()]
    except KeyError as exc:
        raise ContractViolation("AIP_LEGACY_STATUS_UNMAPPABLE", "legacy step-run status is not mappable") from exc

