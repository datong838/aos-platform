"""W2-AM · Data Health Plus 路由（#136 #137 #138）."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.data_health_plus import (
    HealthDiagnosticsError,
    HealthMonitoringOptionsError,
    HealthNotificationError,
    FailedCheckDetail,
    HealthDiagnosticsReport,
    HealthMonitoringOptions,
    HealthNotification,
    get_health_diagnostics_engine,
    get_health_monitoring_options_engine,
    get_health_notification_engine,
)
from aos_api.errors import ApiError

router = APIRouter(prefix="/health", tags=["Data Health Plus"])


def _map_diagnostics_err(e: HealthDiagnosticsError) -> HTTPException:
    mapping = {
        "MISSING_GROUP": (400, "缺少 group_id"),
        "INVALID_GROUPING": (400, "分组策略无效"),
        "INVALID_SEVERITY": (400, "严重级无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(status_code=status, detail=ApiError(code=e.code, message=msg).model_dump())


def _map_monitoring_err(e: HealthMonitoringOptionsError) -> HTTPException:
    mapping = {
        "MISSING_DATASET": (400, "缺少 dataset_rid"),
        "INVALID_NOTIFICATION_MODE": (400, "通知模式无效"),
        "INVALID_CHANNEL": (400, "渠道无效"),
        "INVALID_INTERVAL": (400, "提醒间隔无效"),
        "NOT_FOUND": (404, "资源不存在"),
        "CHANNEL_NOT_FOUND": (404, "渠道不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(status_code=status, detail=ApiError(code=e.code, message=msg).model_dump())


def _map_notification_err(e: HealthNotificationError) -> HTTPException:
    mapping = {
        "MISSING_USER": (400, "缺少 user_id"),
        "MISSING_DATASET": (400, "缺少 dataset_rid"),
        "INVALID_SEVERITY": (400, "严重级无效"),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(status_code=status, detail=ApiError(code=e.code, message=msg).model_dump())


# ════════════════════ #136 Health Diagnostics ════════════════════

class GenerateDiagnosticsBody(BaseModel):
    grouping_strategy: str = "by_severity"


@router.post("/diagnostics/groups/{group_id}/report", response_model=HealthDiagnosticsReport)
def generate_diagnostics_report(group_id: str, body: GenerateDiagnosticsBody, _=require_principal):
    try:
        return get_health_diagnostics_engine().generate_diagnostics(
            group_id=group_id,
            grouping_strategy=body.grouping_strategy,
        )
    except HealthDiagnosticsError as e:
        raise _map_diagnostics_err(e) from e


@router.get("/diagnostics/reports/{report_id}", response_model=HealthDiagnosticsReport)
def get_diagnostics_report(report_id: str, _=require_principal):
    try:
        return get_health_diagnostics_engine().get_report(report_id)
    except HealthDiagnosticsError as e:
        raise _map_diagnostics_err(e) from e


@router.get("/diagnostics/reports", response_model=list[HealthDiagnosticsReport])
def list_diagnostics_reports(
    group_id: str = Query(...),
    limit: int = Query(20, ge=1, le=200),
    _=require_principal,
):
    return get_health_diagnostics_engine().list_reports(group_id=group_id, limit=limit)


@router.get("/diagnostics/groups/{group_id}/failed-checks", response_model=list[FailedCheckDetail])
def get_failed_checks(
    group_id: str,
    severity_filter: str | None = Query(None),
    _=require_principal,
):
    try:
        return get_health_diagnostics_engine().get_failed_checks(
            group_id=group_id,
            severity_filter=severity_filter,
        )
    except HealthDiagnosticsError as e:
        raise _map_diagnostics_err(e) from e


@router.get("/diagnostics/groups/{group_id}/focus-summary")
def get_focus_summary(group_id: str, _=require_principal):
    try:
        summary = get_health_diagnostics_engine().get_focus_summary(group_id)
        return {"group_id": group_id, "focus_summary": summary}
    except HealthDiagnosticsError as e:
        raise _map_diagnostics_err(e) from e


@router.get("/diagnostics/groups/{group_id}/checks")
def list_checks_by_group(group_id: str, _=require_principal):
    try:
        return get_health_diagnostics_engine().list_checks_by_group(group_id)
    except HealthDiagnosticsError as e:
        raise _map_diagnostics_err(e) from e


# ════════════════════ #137 Health Monitoring Options ════════════════════

@router.post("/monitoring-options", response_model=HealthMonitoringOptions)
def register_monitoring_options(options: HealthMonitoringOptions, _=require_principal):
    try:
        return get_health_monitoring_options_engine().register(options)
    except HealthMonitoringOptionsError as e:
        raise _map_monitoring_err(e) from e


@router.get("/monitoring-options/{options_id}", response_model=HealthMonitoringOptions)
def get_monitoring_options(options_id: str, _=require_principal):
    try:
        return get_health_monitoring_options_engine().get(options_id)
    except HealthMonitoringOptionsError as e:
        raise _map_monitoring_err(e) from e


@router.get("/monitoring-options/dataset/{dataset_rid}", response_model=HealthMonitoringOptions)
def get_monitoring_options_by_dataset(dataset_rid: str, _=require_principal):
    try:
        return get_health_monitoring_options_engine().get_by_dataset(dataset_rid)
    except HealthMonitoringOptionsError as e:
        raise _map_monitoring_err(e) from e


@router.get("/monitoring-options", response_model=list[HealthMonitoringOptions])
def list_monitoring_options(
    dataset_rid: str | None = Query(None),
    _=require_principal,
):
    return get_health_monitoring_options_engine().list(dataset_rid=dataset_rid)


@router.put("/monitoring-options/{options_id}", response_model=HealthMonitoringOptions)
def update_monitoring_options(options_id: str, updates: dict, _=require_principal):
    try:
        return get_health_monitoring_options_engine().update(options_id, updates)
    except HealthMonitoringOptionsError as e:
        raise _map_monitoring_err(e) from e


@router.delete("/monitoring-options/{options_id}")
def delete_monitoring_options(options_id: str, _=require_principal):
    try:
        get_health_monitoring_options_engine().delete(options_id)
        return {"deleted": True}
    except HealthMonitoringOptionsError as e:
        raise _map_monitoring_err(e) from e


class SetModeBody(BaseModel):
    mode: str


@router.post("/monitoring-options/{options_id}/mode", response_model=HealthMonitoringOptions)
def set_notification_mode(options_id: str, body: SetModeBody, _=require_principal):
    try:
        return get_health_monitoring_options_engine().set_notification_mode(options_id, body.mode)
    except HealthMonitoringOptionsError as e:
        raise _map_monitoring_err(e) from e


class AddChannelBody(BaseModel):
    channel: str


@router.post("/monitoring-options/{options_id}/channels", response_model=HealthMonitoringOptions)
def add_channel(options_id: str, body: AddChannelBody, _=require_principal):
    try:
        return get_health_monitoring_options_engine().add_channel(options_id, body.channel)
    except HealthMonitoringOptionsError as e:
        raise _map_monitoring_err(e) from e


@router.delete("/monitoring-options/{options_id}/channels/{channel}", response_model=HealthMonitoringOptions)
def remove_channel(options_id: str, channel: str, _=require_principal):
    try:
        return get_health_monitoring_options_engine().remove_channel(options_id, channel)
    except HealthMonitoringOptionsError as e:
        raise _map_monitoring_err(e) from e


# ════════════════════ #138 Health Notifications ════════════════════

class CreateNotificationBody(BaseModel):
    dataset_rid: str
    check_id: str
    check_name: str
    severity: str
    title: str
    message: str
    user_id: str


@router.post("/notifications", response_model=HealthNotification)
def create_notification(body: CreateNotificationBody, _=require_principal):
    try:
        return get_health_notification_engine().create(
            dataset_rid=body.dataset_rid,
            check_id=body.check_id,
            check_name=body.check_name,
            severity=body.severity,
            title=body.title,
            message=body.message,
            user_id=body.user_id,
        )
    except HealthNotificationError as e:
        raise _map_notification_err(e) from e


@router.get("/notifications/{notification_id}", response_model=HealthNotification)
def get_notification(notification_id: str, _=require_principal):
    try:
        return get_health_notification_engine().get(notification_id)
    except HealthNotificationError as e:
        raise _map_notification_err(e) from e


@router.get("/notifications", response_model=list[HealthNotification])
def list_notifications(
    user_id: str = Query(...),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _=require_principal,
):
    try:
        return get_health_notification_engine().list(
            user_id=user_id,
            status=status,
            severity=severity,
            limit=limit,
        )
    except HealthNotificationError as e:
        raise _map_notification_err(e) from e


@router.post("/notifications/{notification_id}/read", response_model=HealthNotification)
def mark_notification_read(notification_id: str, _=require_principal):
    try:
        return get_health_notification_engine().mark_read(notification_id)
    except HealthNotificationError as e:
        raise _map_notification_err(e) from e


class UserIdBody(BaseModel):
    user_id: str


@router.post("/notifications/read-all")
def mark_all_notifications_read(body: UserIdBody, _=require_principal):
    try:
        count = get_health_notification_engine().mark_all_read(body.user_id)
        return {"marked_read": count}
    except HealthNotificationError as e:
        raise _map_notification_err(e) from e


@router.post("/notifications/{notification_id}/clear", response_model=HealthNotification)
def clear_notification(notification_id: str, _=require_principal):
    try:
        return get_health_notification_engine().clear(notification_id)
    except HealthNotificationError as e:
        raise _map_notification_err(e) from e


@router.post("/notifications/clear-all")
def clear_all_notifications(body: UserIdBody, _=require_principal):
    try:
        count = get_health_notification_engine().clear_all(body.user_id)
        return {"cleared": count}
    except HealthNotificationError as e:
        raise _map_notification_err(e) from e


@router.get("/notifications/unread/count")
def get_unread_count(
    user_id: str = Query(...),
    severity: str | None = Query(None),
    _=require_principal,
):
    try:
        return get_health_notification_engine().get_unread_count(user_id, severity)
    except HealthNotificationError as e:
        raise _map_notification_err(e) from e


@router.get("/notifications/dataset/{dataset_rid}", response_model=list[HealthNotification])
def list_notifications_by_dataset(
    dataset_rid: str,
    limit: int = Query(20, ge=1, le=200),
    _=require_principal,
):
    try:
        return get_health_notification_engine().list_by_dataset(dataset_rid, limit=limit)
    except HealthNotificationError as e:
        raise _map_notification_err(e) from e
