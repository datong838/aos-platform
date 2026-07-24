"""W2-AB · Data Health 检查组路由：#133 检查类型 + #134 检查计划 + #135 检查分组."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.data_health import (
    DataHealthError,
    HealthCheckGroup,
    HealthCheckType,
    HealthSchedule,
    get_health_check_group_engine,
    get_health_check_type_engine,
    get_health_schedule_engine,
)
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["data-health"])
log = get_logger("aos-api.data-health")


def _map_err(err: DataHealthError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #133 Check Type ════════════════════

class CheckTypeIn(BaseModel):
    name: str = Field(min_length=1)
    check_kind: str = Field(min_length=1)
    target_dataset_rid: str = Field(min_length=1)
    configuration: dict[str, Any] = Field(default_factory=dict)
    severity: str = "warning"
    enabled: bool = True


class CheckTypeUpdateIn(BaseModel):
    name: str | None = None
    check_kind: str | None = None
    target_dataset_rid: str | None = None
    configuration: dict[str, Any] | None = None
    severity: str | None = None
    enabled: bool | None = None


class RunCheckIn(BaseModel):
    measured_value: Any | None = None


@router.post("/v1/data-health/checks")
def register_check(
    body: CheckTypeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#133 · 注册检查类型。"""
    _ = principal
    try:
        c = get_health_check_type_engine().register(HealthCheckType(**body.model_dump()))
    except DataHealthError as exc:
        raise _map_err(exc) from exc
    return {"item": c.model_dump()}


@router.get("/v1/data-health/checks")
def list_checks(
    check_kind: str | None = None,
    enabled_only: bool = False,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#133 · 检查类型列表。"""
    _ = principal
    items = get_health_check_type_engine().list(check_kind=check_kind, enabled_only=enabled_only)
    return {"items": [c.model_dump() for c in items], "count": len(items)}


@router.get("/v1/data-health/checks/{check_id}")
def get_check(
    check_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#133 · 单条检查类型。"""
    _ = principal
    try:
        return {"item": get_health_check_type_engine().get(check_id).model_dump()}
    except DataHealthError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/data-health/checks/{check_id}")
def update_check(
    check_id: str,
    body: CheckTypeUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#133 · 更新检查类型。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        c = get_health_check_type_engine().update(check_id, updates)
    except DataHealthError as exc:
        raise _map_err(exc) from exc
    return {"item": c.model_dump()}


@router.delete("/v1/data-health/checks/{check_id}")
def delete_check(
    check_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#133 · 删除检查类型。"""
    _ = principal
    ok = get_health_check_type_engine().delete(check_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"检查 {check_id} 不存在", status_code=404)
    return {"id": check_id, "deleted": True}


@router.post("/v1/data-health/checks/{check_id}/run")
def run_check(
    check_id: str,
    body: RunCheckIn | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#133 · 执行检查。"""
    _ = principal
    measured = body.measured_value if body else None
    try:
        r = get_health_check_type_engine().run(check_id, measured)
    except DataHealthError as exc:
        raise _map_err(exc) from exc
    return {"item": r.model_dump()}


@router.get("/v1/data-health/check-results")
def list_check_results(
    check_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#133 · 检查结果列表。"""
    _ = principal
    items = get_health_check_type_engine().list_results(
        check_id=check_id, status=status, limit=limit,
    )
    return {"items": [r.model_dump() for r in items], "count": len(items)}


# ════════════════════ #134 Check Schedule ════════════════════

class ScheduleIn(BaseModel):
    check_id: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    cron_expression: str = ""
    trigger_dataset_rid: str = ""
    enabled: bool = True


class ScheduleUpdateIn(BaseModel):
    cron_expression: str | None = None
    trigger_dataset_rid: str | None = None
    enabled: bool | None = None


@router.post("/v1/data-health/schedules")
def register_schedule(
    body: ScheduleIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#134 · 注册检查计划。"""
    _ = principal
    try:
        s = get_health_schedule_engine().register(HealthSchedule(**body.model_dump()))
    except DataHealthError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.get("/v1/data-health/schedules")
def list_schedules(
    check_id: str | None = None,
    mode: str | None = None,
    enabled_only: bool = False,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#134 · 检查计划列表。"""
    _ = principal
    items = get_health_schedule_engine().list(
        check_id=check_id, mode=mode, enabled_only=enabled_only,
    )
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/v1/data-health/schedules/{schedule_id}")
def get_schedule(
    schedule_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#134 · 单条检查计划。"""
    _ = principal
    try:
        return {"item": get_health_schedule_engine().get(schedule_id).model_dump()}
    except DataHealthError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/data-health/schedules/{schedule_id}")
def update_schedule(
    schedule_id: str,
    body: ScheduleUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#134 · 更新检查计划。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        s = get_health_schedule_engine().update(schedule_id, updates)
    except DataHealthError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.delete("/v1/data-health/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#134 · 删除检查计划。"""
    _ = principal
    ok = get_health_schedule_engine().delete(schedule_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"计划 {schedule_id} 不存在", status_code=404)
    return {"id": schedule_id, "deleted": True}


@router.post("/v1/data-health/schedules/{schedule_id}/trigger")
def trigger_schedule(
    schedule_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#134 · 触发计划执行。"""
    _ = principal
    try:
        result = get_health_schedule_engine().trigger(schedule_id)
    except DataHealthError as exc:
        raise _map_err(exc) from exc
    return {"item": result}


@router.get("/v1/data-health/schedules/{schedule_id}/next-run")
def next_run_schedule(
    schedule_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#134 · 下次运行时间。"""
    _ = principal
    try:
        ts = get_health_schedule_engine().compute_next_run(schedule_id)
    except DataHealthError as exc:
        raise _map_err(exc) from exc
    return {"schedule_id": schedule_id, "next_run_at": ts}


# ════════════════════ #135 Check Group ════════════════════

class GroupIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    check_ids: list[str] = Field(default_factory=list)
    notification_config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class GroupUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    check_ids: list[str] | None = None
    notification_config: dict[str, Any] | None = None
    enabled: bool | None = None


class NotifyIn(BaseModel):
    event: dict[str, Any] = Field(default_factory=dict)


@router.post("/v1/data-health/groups")
def register_group(
    body: GroupIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#135 · 注册检查分组。"""
    _ = principal
    try:
        g = get_health_check_group_engine().register(HealthCheckGroup(**body.model_dump()))
    except DataHealthError as exc:
        raise _map_err(exc) from exc
    return {"item": g.model_dump()}


@router.get("/v1/data-health/groups")
def list_groups(
    enabled_only: bool = False,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#135 · 检查分组列表。"""
    _ = principal
    items = get_health_check_group_engine().list(enabled_only=enabled_only)
    return {"items": [g.model_dump() for g in items], "count": len(items)}


@router.get("/v1/data-health/groups/{group_id}")
def get_group(
    group_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#135 · 单条检查分组。"""
    _ = principal
    try:
        return {"item": get_health_check_group_engine().get(group_id).model_dump()}
    except DataHealthError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/data-health/groups/{group_id}")
def update_group(
    group_id: str,
    body: GroupUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#135 · 更新检查分组。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        g = get_health_check_group_engine().update(group_id, updates)
    except DataHealthError as exc:
        raise _map_err(exc) from exc
    return {"item": g.model_dump()}


@router.delete("/v1/data-health/groups/{group_id}")
def delete_group(
    group_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#135 · 删除检查分组。"""
    _ = principal
    ok = get_health_check_group_engine().delete(group_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"分组 {group_id} 不存在", status_code=404)
    return {"id": group_id, "deleted": True}


@router.post("/v1/data-health/groups/{group_id}/attach/{check_id}")
def attach_check_to_group(
    group_id: str,
    check_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#135 · 挂载检查到分组。"""
    _ = principal
    try:
        g = get_health_check_group_engine().attach_check(group_id, check_id)
    except DataHealthError as exc:
        raise _map_err(exc) from exc
    return {"item": g.model_dump()}


@router.post("/v1/data-health/groups/{group_id}/detach/{check_id}")
def detach_check_from_group(
    group_id: str,
    check_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#135 · 从分组卸载检查。"""
    _ = principal
    try:
        g = get_health_check_group_engine().detach_check(group_id, check_id)
    except DataHealthError as exc:
        raise _map_err(exc) from exc
    return {"item": g.model_dump()}


@router.get("/v1/data-health/groups/{group_id}/monitor")
def monitor_group(
    group_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#135 · 分组监控概览。"""
    _ = principal
    try:
        summary = get_health_check_group_engine().monitor(group_id)
    except DataHealthError as exc:
        raise _map_err(exc) from exc
    return {"item": summary.model_dump()}


@router.post("/v1/data-health/groups/{group_id}/notify")
def notify_group(
    group_id: str,
    body: NotifyIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#135 · 发送通知。"""
    _ = principal
    try:
        record = get_health_check_group_engine().send_notification(group_id, body.event)
    except DataHealthError as exc:
        raise _map_err(exc) from exc
    return {"item": record}
