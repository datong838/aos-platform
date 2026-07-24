"""W2-AY · Connection CDC & Schedule API 路由。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.connection_cdc_schedule import (
    ConnectionCdcEngine,
    CdcConfigError,
    ScheduleTriggerEngine,
    ScheduleTriggerError,
    StorageRouteGuideEngine,
    StorageRouteError,
)
from aos_api.errors import ApiError

router = APIRouter(prefix="/connection-cdc-schedule", tags=["Connection CDC & Schedule"])


def _map_cdc_err(err: CdcConfigError) -> ApiError:
    return ApiError(
        code=err.code,
        message=err.message,
        status_code=err.status_code,
    )


def _map_schedule_err(err: ScheduleTriggerError) -> ApiError:
    return ApiError(
        code=err.code,
        message=err.message,
        status_code=err.status_code,
    )


def _map_storage_route_err(err: StorageRouteError) -> ApiError:
    return ApiError(
        code=err.code,
        message=err.message,
        status_code=err.status_code,
    )


class ConfigureCdcRequest(BaseModel):
    connection_id: str
    capture_mode: str = "incremental"
    snapshot_interval_hours: int = 24
    max_backlog_records: int = 10000
    enabled: bool = True


class UpdateCdcRequest(BaseModel):
    enabled: Optional[bool] = None
    capture_mode: Optional[str] = None
    snapshot_interval_hours: Optional[int] = None
    max_backlog_records: Optional[int] = None


class ToggleRequest(BaseModel):
    enabled: bool


@router.post("/cdc-configs")
def configure_cdc(
    req: ConfigureCdcRequest,
    principal: Principal = Depends(require_principal),
):
    try:
        return ConnectionCdcEngine().configure_cdc(
            connection_id=req.connection_id,
            capture_mode=req.capture_mode,
            snapshot_interval_hours=req.snapshot_interval_hours,
            max_backlog_records=req.max_backlog_records,
            enabled=req.enabled,
        )
    except CdcConfigError as err:
        raise _map_cdc_err(err) from err


@router.get("/cdc-configs")
def list_cdc(
    connection_id: Optional[str] = None,
    status: Optional[str] = None,
    principal: Principal = Depends(require_principal),
):
    try:
        return ConnectionCdcEngine().list_cdc(
            connection_id=connection_id,
            status=status,
        )
    except CdcConfigError as err:
        raise _map_cdc_err(err) from err


@router.get("/cdc-configs/{cdc_id}")
def get_cdc(
    cdc_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return ConnectionCdcEngine().get_cdc(cdc_id=cdc_id)
    except CdcConfigError as err:
        raise _map_cdc_err(err) from err


@router.put("/cdc-configs/{cdc_id}")
def update_cdc(
    cdc_id: str,
    req: UpdateCdcRequest,
    principal: Principal = Depends(require_principal),
):
    try:
        return ConnectionCdcEngine().update_cdc(
            cdc_id=cdc_id,
            enabled=req.enabled,
            capture_mode=req.capture_mode,
            snapshot_interval_hours=req.snapshot_interval_hours,
            max_backlog_records=req.max_backlog_records,
        )
    except CdcConfigError as err:
        raise _map_cdc_err(err) from err


@router.delete("/cdc-configs/{cdc_id}")
def delete_cdc(
    cdc_id: str,
    principal: Principal = Depends(require_principal),
):
    ok = ConnectionCdcEngine().delete_cdc(cdc_id=cdc_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"CDC配置 {cdc_id} 不存在", status_code=404)
    return {"deleted": True, "cdc_id": cdc_id}


@router.post("/cdc-configs/{cdc_id}/toggle")
def toggle_cdc(
    cdc_id: str,
    req: ToggleRequest,
    principal: Principal = Depends(require_principal),
):
    try:
        return ConnectionCdcEngine().toggle_cdc(cdc_id=cdc_id, enabled=req.enabled)
    except CdcConfigError as err:
        raise _map_cdc_err(err) from err


class CreateTriggerRequest(BaseModel):
    name: str
    cron_expression: str
    timezone: str = "Asia/Shanghai"
    enabled: bool = True
    target_type: str = "pipeline"
    target_id: str = ""


class UpdateTriggerRequest(BaseModel):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    enabled: Optional[bool] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None


@router.post("/schedule-triggers")
def create_trigger(
    req: CreateTriggerRequest,
    principal: Principal = Depends(require_principal),
):
    try:
        return ScheduleTriggerEngine().create_trigger(
            name=req.name,
            cron_expression=req.cron_expression,
            timezone=req.timezone,
            enabled=req.enabled,
            target_type=req.target_type,
            target_id=req.target_id,
        )
    except ScheduleTriggerError as err:
        raise _map_schedule_err(err) from err


@router.get("/schedule-triggers")
def list_triggers(
    name: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    status: Optional[str] = None,
    principal: Principal = Depends(require_principal),
):
    try:
        return ScheduleTriggerEngine().list_triggers(
            name=name,
            target_type=target_type,
            target_id=target_id,
            status=status,
        )
    except ScheduleTriggerError as err:
        raise _map_schedule_err(err) from err


@router.get("/schedule-triggers/{trigger_id}")
def get_trigger(
    trigger_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return ScheduleTriggerEngine().get_trigger(trigger_id=trigger_id)
    except ScheduleTriggerError as err:
        raise _map_schedule_err(err) from err


@router.put("/schedule-triggers/{trigger_id}")
def update_trigger(
    trigger_id: str,
    req: UpdateTriggerRequest,
    principal: Principal = Depends(require_principal),
):
    try:
        return ScheduleTriggerEngine().update_trigger(
            trigger_id=trigger_id,
            name=req.name,
            cron_expression=req.cron_expression,
            timezone=req.timezone,
            enabled=req.enabled,
            target_type=req.target_type,
            target_id=req.target_id,
        )
    except ScheduleTriggerError as err:
        raise _map_schedule_err(err) from err


@router.delete("/schedule-triggers/{trigger_id}")
def delete_trigger(
    trigger_id: str,
    principal: Principal = Depends(require_principal),
):
    ok = ScheduleTriggerEngine().delete_trigger(trigger_id=trigger_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"触发器 {trigger_id} 不存在", status_code=404)
    return {"deleted": True, "trigger_id": trigger_id}


@router.post("/schedule-triggers/{trigger_id}/toggle")
def toggle_trigger(
    trigger_id: str,
    req: ToggleRequest,
    principal: Principal = Depends(require_principal),
):
    try:
        return ScheduleTriggerEngine().toggle_trigger(trigger_id=trigger_id, enabled=req.enabled)
    except ScheduleTriggerError as err:
        raise _map_schedule_err(err) from err


class CreateRouteRequest(BaseModel):
    name: str
    source_path: str
    target_path: str
    route_type: str = "copy"
    schedule_type: str = "on_demand"
    schedule_cron: Optional[str] = None
    enabled: bool = True


class UpdateRouteRequest(BaseModel):
    name: Optional[str] = None
    source_path: Optional[str] = None
    target_path: Optional[str] = None
    route_type: Optional[str] = None
    schedule_type: Optional[str] = None
    schedule_cron: Optional[str] = None
    enabled: Optional[bool] = None


@router.post("/storage-routes")
def create_route(
    req: CreateRouteRequest,
    principal: Principal = Depends(require_principal),
):
    try:
        return StorageRouteGuideEngine().create_route(
            name=req.name,
            source_path=req.source_path,
            target_path=req.target_path,
            route_type=req.route_type,
            schedule_type=req.schedule_type,
            schedule_cron=req.schedule_cron,
            enabled=req.enabled,
        )
    except StorageRouteError as err:
        raise _map_storage_route_err(err) from err


@router.get("/storage-routes")
def list_routes(
    name: Optional[str] = None,
    route_type: Optional[str] = None,
    schedule_type: Optional[str] = None,
    status: Optional[str] = None,
    principal: Principal = Depends(require_principal),
):
    try:
        return StorageRouteGuideEngine().list_routes(
            name=name,
            route_type=route_type,
            schedule_type=schedule_type,
            status=status,
        )
    except StorageRouteError as err:
        raise _map_storage_route_err(err) from err


@router.get("/storage-routes/{route_id}")
def get_route(
    route_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return StorageRouteGuideEngine().get_route(route_id=route_id)
    except StorageRouteError as err:
        raise _map_storage_route_err(err) from err


@router.put("/storage-routes/{route_id}")
def update_route(
    route_id: str,
    req: UpdateRouteRequest,
    principal: Principal = Depends(require_principal),
):
    try:
        return StorageRouteGuideEngine().update_route(
            route_id=route_id,
            name=req.name,
            source_path=req.source_path,
            target_path=req.target_path,
            route_type=req.route_type,
            schedule_type=req.schedule_type,
            schedule_cron=req.schedule_cron,
            enabled=req.enabled,
        )
    except StorageRouteError as err:
        raise _map_storage_route_err(err) from err


@router.delete("/storage-routes/{route_id}")
def delete_route(
    route_id: str,
    principal: Principal = Depends(require_principal),
):
    ok = StorageRouteGuideEngine().delete_route(route_id=route_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"存储路由 {route_id} 不存在", status_code=404)
    return {"deleted": True, "route_id": route_id}


@router.post("/storage-routes/{route_id}/execute")
def execute_route(
    route_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return StorageRouteGuideEngine().execute_route(route_id=route_id)
    except StorageRouteError as err:
        raise _map_storage_route_err(err) from err