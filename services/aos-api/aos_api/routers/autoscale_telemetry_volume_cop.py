"""W2-BN · Autoscale / Telemetry / Volume / COP 路由（#22 #23 #24 #25）."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from aos_api.auth import require_principal
from aos_api.autoscale_telemetry_volume_cop import (
    AutoscaleTelemetryError,
    CopAlert,
    CopMetric,
    LoadPrediction,
    LogSource,
    TelemetryConfig,
    VolumeAttachment,
    VolumeMount,
    WarmupSchedule,
    get_cop_realtime_engine,
    get_predictive_autoscale_engine,
    get_telemetry_format_engine,
    get_volume_mount_engine,
)

router = APIRouter(
    prefix="/autoscale-telemetry-volume-cop",
    tags=["autoscale-telemetry-volume-cop"],
)


def _map_err(err: AutoscaleTelemetryError) -> HTTPException:
    code = getattr(err, "code", "") or ""
    if code == "NOT_FOUND":
        status = 404
    elif code.startswith("INVALID_") or code == "ALREADY_EXECUTED":
        status = 400
    else:
        status = 500
    payload = (
        err.error_payload()
        if hasattr(err, "error_payload")
        else {"code": code, "message": str(err)}
    )
    return HTTPException(status_code=status, detail=payload)


# ════════════════════ #22 Autoscale request bodies ════════════════════

class CreatePredictionBody(BaseModel):
    resource_id: str
    predicted_load: float
    target_time: float
    confidence: float = 0.0
    reason: str = ""


class CreateWarmupBody(BaseModel):
    resource_id: str
    target_replicas: int
    warmup_time: float


# ════════════════════ #23 Telemetry request bodies ════════════════════

class SetTelemetryConfigBody(BaseModel):
    resource_id: str
    enabled: bool = True
    format: str = "json"
    sample_rate: float = 1.0
    log_source: str = "stdout"
    destinations: list[str] = Field(default_factory=list)


class RegisterLogSourceBody(BaseModel):
    resource_id: str
    source_type: str
    path: str = ""
    format: str = "json"


# ════════════════════ #24 Volume request bodies ════════════════════

class CreateVolumeBody(BaseModel):
    name: str
    mount_path: str
    storage_type: str = "emptydir"
    size_gb: float = 0
    read_only: bool = False
    shared: bool = False
    access_mode: str = "readwrite"


class CreateAttachmentBody(BaseModel):
    volume_id: str
    target_id: str
    sub_path: str = ""
    mount_path: str = ""
    read_only: bool = False


# ════════════════════ #25 COP request bodies ════════════════════

class SetThresholdBody(BaseModel):
    resource_id: str
    metric_name: str
    warning: float
    critical: float


class RecordMetricBody(BaseModel):
    resource_id: str
    metric_name: str
    value: float
    unit: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ════════════════════ #22 Autoscale endpoints ════════════════════

@router.post("/autoscale/predictions", response_model=LoadPrediction)
def create_prediction(body: CreatePredictionBody, _=require_principal):
    try:
        return get_predictive_autoscale_engine().record_prediction(
            resource_id=body.resource_id,
            predicted_load=body.predicted_load,
            target_time=body.target_time,
            confidence=body.confidence,
            reason=body.reason,
        )
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/autoscale/predictions/{prediction_id}", response_model=LoadPrediction)
def get_prediction(prediction_id: str, _=require_principal):
    try:
        return get_predictive_autoscale_engine().get_prediction(prediction_id)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/autoscale/predictions", response_model=list[LoadPrediction])
def list_predictions(
    resource_id: str | None = Query(None),
    action: str | None = Query(None),
    _=require_principal,
):
    return get_predictive_autoscale_engine().list_predictions(
        resource_id=resource_id, action=action
    )


@router.delete("/autoscale/predictions/{prediction_id}")
def delete_prediction(prediction_id: str, _=require_principal):
    return {
        "deleted": get_predictive_autoscale_engine().delete_prediction(prediction_id)
    }


@router.post("/autoscale/warmups", response_model=WarmupSchedule)
def create_warmup(body: CreateWarmupBody, _=require_principal):
    try:
        return get_predictive_autoscale_engine().schedule_warmup(
            resource_id=body.resource_id,
            target_replicas=body.target_replicas,
            warmup_time=body.warmup_time,
        )
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/autoscale/warmups/{warmup_id}", response_model=WarmupSchedule)
def get_warmup(warmup_id: str, _=require_principal):
    try:
        return get_predictive_autoscale_engine().get_warmup(warmup_id)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/autoscale/warmups", response_model=list[WarmupSchedule])
def list_warmups(
    resource_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_predictive_autoscale_engine().list_warmups(
        resource_id=resource_id, status=status
    )


@router.post("/autoscale/warmups/{warmup_id}/execute", response_model=WarmupSchedule)
def execute_warmup(warmup_id: str, _=require_principal):
    try:
        return get_predictive_autoscale_engine().execute_warmup(warmup_id)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.post("/autoscale/warmups/{warmup_id}/cancel", response_model=WarmupSchedule)
def cancel_warmup(warmup_id: str, _=require_principal):
    try:
        return get_predictive_autoscale_engine().cancel_warmup(warmup_id)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.delete("/autoscale/warmups/{warmup_id}")
def delete_warmup(warmup_id: str, _=require_principal):
    return {"deleted": get_predictive_autoscale_engine().delete_warmup(warmup_id)}


# ════════════════════ #23 Telemetry endpoints ════════════════════

@router.post("/telemetry/configs", response_model=TelemetryConfig)
def set_telemetry_config(body: SetTelemetryConfigBody, _=require_principal):
    try:
        return get_telemetry_format_engine().set_config(
            resource_id=body.resource_id,
            enabled=body.enabled,
            format=body.format,
            sample_rate=body.sample_rate,
            log_source=body.log_source,
            destinations=body.destinations,
        )
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/telemetry/configs/{resource_id}", response_model=TelemetryConfig)
def get_telemetry_config(resource_id: str, _=require_principal):
    try:
        return get_telemetry_format_engine().get_config(resource_id)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/telemetry/configs", response_model=list[TelemetryConfig])
def list_telemetry_configs(
    enabled_only: bool = Query(False),
    _=require_principal,
):
    return get_telemetry_format_engine().list_configs(enabled_only=enabled_only)


@router.put("/telemetry/configs/{resource_id}", response_model=TelemetryConfig)
def update_telemetry_config(
    resource_id: str, updates: dict[str, Any], _=require_principal
):
    try:
        return get_telemetry_format_engine().update_config(resource_id, updates)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.delete("/telemetry/configs/{resource_id}")
def delete_telemetry_config(resource_id: str, _=require_principal):
    return {"deleted": get_telemetry_format_engine().delete_config(resource_id)}


@router.post("/telemetry/sources", response_model=LogSource)
def register_log_source(body: RegisterLogSourceBody, _=require_principal):
    try:
        return get_telemetry_format_engine().register_source(
            resource_id=body.resource_id,
            source_type=body.source_type,
            path=body.path,
            format=body.format,
        )
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/telemetry/sources/{source_id}", response_model=LogSource)
def get_log_source(source_id: str, _=require_principal):
    try:
        return get_telemetry_format_engine().get_source(source_id)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/telemetry/sources", response_model=list[LogSource])
def list_log_sources(
    resource_id: str | None = Query(None),
    source_type: str | None = Query(None),
    _=require_principal,
):
    return get_telemetry_format_engine().list_sources(
        resource_id=resource_id, source_type=source_type
    )


@router.post("/telemetry/sources/{source_id}/collect", response_model=LogSource)
def collect_log_source(source_id: str, _=require_principal):
    try:
        return get_telemetry_format_engine().collect_from_source(source_id)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.delete("/telemetry/sources/{source_id}")
def delete_log_source(source_id: str, _=require_principal):
    return {"deleted": get_telemetry_format_engine().delete_source(source_id)}


# ════════════════════ #24 Volume endpoints ════════════════════

@router.post("/volume/volumes", response_model=VolumeMount)
def create_volume(body: CreateVolumeBody, _=require_principal):
    try:
        return get_volume_mount_engine().create_volume(
            name=body.name,
            mount_path=body.mount_path,
            storage_type=body.storage_type,
            size_gb=body.size_gb,
            read_only=body.read_only,
            shared=body.shared,
            access_mode=body.access_mode,
        )
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/volume/volumes/{volume_id}", response_model=VolumeMount)
def get_volume(volume_id: str, _=require_principal):
    try:
        return get_volume_mount_engine().get_volume(volume_id)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/volume/volumes", response_model=list[VolumeMount])
def list_volumes(
    storage_type: str | None = Query(None),
    shared_only: bool = Query(False),
    _=require_principal,
):
    return get_volume_mount_engine().list_volumes(
        storage_type=storage_type, shared_only=shared_only
    )


@router.put("/volume/volumes/{volume_id}", response_model=VolumeMount)
def update_volume(volume_id: str, updates: dict[str, Any], _=require_principal):
    try:
        return get_volume_mount_engine().update_volume(volume_id, updates)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.delete("/volume/volumes/{volume_id}")
def delete_volume(volume_id: str, _=require_principal):
    return {"deleted": get_volume_mount_engine().delete_volume(volume_id)}


@router.post("/volume/attachments", response_model=VolumeAttachment)
def create_attachment(body: CreateAttachmentBody, _=require_principal):
    try:
        return get_volume_mount_engine().attach_volume(
            volume_id=body.volume_id,
            target_id=body.target_id,
            sub_path=body.sub_path,
            mount_path=body.mount_path,
            read_only=body.read_only,
        )
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/volume/attachments/{attachment_id}", response_model=VolumeAttachment)
def get_attachment(attachment_id: str, _=require_principal):
    try:
        return get_volume_mount_engine().get_attachment(attachment_id)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/volume/attachments", response_model=list[VolumeAttachment])
def list_attachments(
    volume_id: str | None = Query(None),
    target_id: str | None = Query(None),
    _=require_principal,
):
    return get_volume_mount_engine().list_attachments(
        volume_id=volume_id, target_id=target_id
    )


@router.delete("/volume/attachments/{attachment_id}")
def delete_attachment(attachment_id: str, _=require_principal):
    return {"deleted": get_volume_mount_engine().detach_volume(attachment_id)}


@router.get("/volume/shared", response_model=list[VolumeMount])
def get_shared_volumes(_=require_principal):
    return get_volume_mount_engine().get_shared_volumes()


# ════════════════════ #25 COP endpoints ════════════════════

@router.post("/cop/thresholds")
def set_threshold(body: SetThresholdBody, _=require_principal):
    try:
        return get_cop_realtime_engine().set_threshold(
            resource_id=body.resource_id,
            metric_name=body.metric_name,
            warning=body.warning,
            critical=body.critical,
        )
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/cop/thresholds")
def get_thresholds(
    resource_id: str | None = Query(None),
    _=require_principal,
):
    return get_cop_realtime_engine().get_thresholds(resource_id=resource_id)


@router.delete("/cop/thresholds")
def delete_threshold(
    resource_id: str = Query(...),
    metric_name: str = Query(...),
    _=require_principal,
):
    return {
        "deleted": get_cop_realtime_engine().delete_threshold(
            resource_id=resource_id, metric_name=metric_name
        )
    }


@router.post("/cop/metrics", response_model=CopMetric)
def record_metric(body: RecordMetricBody, _=require_principal):
    try:
        return get_cop_realtime_engine().record_metric(
            resource_id=body.resource_id,
            metric_name=body.metric_name,
            value=body.value,
            unit=body.unit,
            metadata=body.metadata,
        )
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/cop/metrics/{metric_id}", response_model=CopMetric)
def get_metric(metric_id: str, _=require_principal):
    try:
        return get_cop_realtime_engine().get_metric(metric_id)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/cop/metrics", response_model=list[CopMetric])
def list_metrics(
    resource_id: str | None = Query(None),
    severity: str | None = Query(None),
    _=require_principal,
):
    return get_cop_realtime_engine().list_metrics(
        resource_id=resource_id, severity=severity
    )


@router.get("/cop/alerts/{alert_id}", response_model=CopAlert)
def get_alert(alert_id: str, _=require_principal):
    try:
        return get_cop_realtime_engine().get_alert(alert_id)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/cop/alerts", response_model=list[CopAlert])
def list_alerts(
    resource_id: str | None = Query(None),
    severity: str | None = Query(None),
    acknowledged: bool | None = Query(None),
    _=require_principal,
):
    return get_cop_realtime_engine().list_alerts(
        resource_id=resource_id,
        severity=severity,
        acknowledged=acknowledged,
    )


@router.post("/cop/alerts/{alert_id}/acknowledge", response_model=CopAlert)
def acknowledge_alert(alert_id: str, _=require_principal):
    try:
        return get_cop_realtime_engine().acknowledge_alert(alert_id)
    except AutoscaleTelemetryError as e:
        raise _map_err(e) from e


@router.get("/cop/dashboard")
def get_cop_dashboard(_=require_principal):
    return get_cop_realtime_engine().get_dashboard()


@router.delete("/cop/metrics/{metric_id}")
def delete_metric(metric_id: str, _=require_principal):
    return {"deleted": get_cop_realtime_engine().delete_metric(metric_id)}
