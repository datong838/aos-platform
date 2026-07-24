"""W2-BN · Autoscale / Telemetry / Volume / COP 引擎组（#22 #23 #24 #25）.

本模块提供 W2+ 低优先级批次的 4 个内存态引擎：
    - PredictiveAutoscaleEngine  #22 预测扩缩 Predictive Auto-scaling
    - TelemetryFormatEngine      #23 Telemetry / Format / Container log source
    - VolumeMountEngine          #24 Volume mounts 副本内共享卷
    - CopRealtimeEngine          #25 COP 实时态势

所有引擎均线程安全（threading.Lock），容量上限 200，FIFO 按时间戳淘汰。
"""
from __future__ import annotations

import random  # noqa: F401  保留以供调用方扩展使用（与批次约定一致）
import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────────
# 公共工具
# ────────────────────────────────────────────────────────────────

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


class AutoscaleTelemetryError(Exception):
    """Autoscale / Telemetry / Volume / COP 引擎统一错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def error_payload(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


# ════════════════════ #22 Predictive Autoscale ════════════════════

class LoadPrediction(BaseModel):
    id: str = Field(default_factory=lambda: _uid("pred"))
    resource_id: str
    predicted_load: float
    confidence: float = 0.0
    prediction_time: float = Field(default_factory=_now_ts)
    target_time: float
    action: str  # scale_up / scale_down / no_action
    reason: str = ""


class WarmupSchedule(BaseModel):
    id: str = Field(default_factory=lambda: _uid("warm"))
    resource_id: str
    target_replicas: int
    warmup_time: float
    status: str  # scheduled / executed / cancelled
    created_at: float = Field(default_factory=_now_ts)


class PredictiveAutoscaleEngine:
    """#22 预测扩缩引擎。"""

    _MAX_PREDICTIONS = 200
    _MAX_WARMUPS = 200

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._predictions: dict[str, LoadPrediction] = {}
        self._warmups: dict[str, WarmupSchedule] = {}

    # ── predictions ──────────────────────────────────────────────
    def record_prediction(
        self,
        resource_id: str,
        predicted_load: float,
        target_time: float,
        confidence: float = 0.0,
        reason: str = "",
    ) -> LoadPrediction:
        if predicted_load > 0.8:
            action = "scale_up"
        elif predicted_load < 0.3:
            action = "scale_down"
        else:
            action = "no_action"
        pred = LoadPrediction(
            resource_id=resource_id,
            predicted_load=predicted_load,
            target_time=target_time,
            confidence=confidence,
            action=action,
            reason=reason,
        )
        with self._lock:
            if len(self._predictions) >= self._MAX_PREDICTIONS:
                oldest_id = min(
                    self._predictions,
                    key=lambda pid: self._predictions[pid].prediction_time,
                )
                del self._predictions[oldest_id]
            self._predictions[pred.id] = pred
        return pred

    def get_prediction(self, prediction_id: str) -> LoadPrediction:
        with self._lock:
            pred = self._predictions.get(prediction_id)
        if pred is None:
            raise AutoscaleTelemetryError(
                "NOT_FOUND", f"prediction {prediction_id} not found"
            )
        return pred

    def list_predictions(
        self,
        resource_id: str | None = None,
        action: str | None = None,
    ) -> list[LoadPrediction]:
        with self._lock:
            results = list(self._predictions.values())
        if resource_id is not None:
            results = [p for p in results if p.resource_id == resource_id]
        if action is not None:
            results = [p for p in results if p.action == action]
        return sorted(results, key=lambda p: p.prediction_time)

    def delete_prediction(self, prediction_id: str) -> bool:
        with self._lock:
            return self._predictions.pop(prediction_id, None) is not None

    # ── warmups ──────────────────────────────────────────────────
    def schedule_warmup(
        self,
        resource_id: str,
        target_replicas: int,
        warmup_time: float,
    ) -> WarmupSchedule:
        if target_replicas <= 0:
            raise AutoscaleTelemetryError(
                "INVALID_REPLICAS", "target_replicas must be > 0"
            )
        warmup = WarmupSchedule(
            resource_id=resource_id,
            target_replicas=target_replicas,
            warmup_time=warmup_time,
            status="scheduled",
        )
        with self._lock:
            if len(self._warmups) >= self._MAX_WARMUPS:
                oldest_id = min(
                    self._warmups,
                    key=lambda wid: self._warmups[wid].created_at,
                )
                del self._warmups[oldest_id]
            self._warmups[warmup.id] = warmup
        return warmup

    def get_warmup(self, warmup_id: str) -> WarmupSchedule:
        with self._lock:
            warmup = self._warmups.get(warmup_id)
        if warmup is None:
            raise AutoscaleTelemetryError(
                "NOT_FOUND", f"warmup {warmup_id} not found"
            )
        return warmup

    def list_warmups(
        self,
        resource_id: str | None = None,
        status: str | None = None,
    ) -> list[WarmupSchedule]:
        with self._lock:
            results = list(self._warmups.values())
        if resource_id is not None:
            results = [w for w in results if w.resource_id == resource_id]
        if status is not None:
            results = [w for w in results if w.status == status]
        return sorted(results, key=lambda w: w.created_at)

    def execute_warmup(self, warmup_id: str) -> WarmupSchedule:
        with self._lock:
            warmup = self._warmups.get(warmup_id)
            if warmup is None:
                raise AutoscaleTelemetryError(
                    "NOT_FOUND", f"warmup {warmup_id} not found"
                )
            updated = warmup.model_copy(update={"status": "executed"})
            self._warmups[warmup_id] = updated
        return updated

    def cancel_warmup(self, warmup_id: str) -> WarmupSchedule:
        with self._lock:
            warmup = self._warmups.get(warmup_id)
            if warmup is None:
                raise AutoscaleTelemetryError(
                    "NOT_FOUND", f"warmup {warmup_id} not found"
                )
            if warmup.status != "scheduled":
                raise AutoscaleTelemetryError(
                    "ALREADY_EXECUTED",
                    f"warmup {warmup_id} status {warmup.status} cannot be cancelled",
                )
            updated = warmup.model_copy(update={"status": "cancelled"})
            self._warmups[warmup_id] = updated
        return updated

    def delete_warmup(self, warmup_id: str) -> bool:
        with self._lock:
            return self._warmups.pop(warmup_id, None) is not None


# ════════════════════ #23 Telemetry / Format / Log source ════════════════════

class TelemetryConfig(BaseModel):
    id: str = Field(default_factory=lambda: _uid("tel"))
    resource_id: str
    enabled: bool = True
    format: str  # json / otel / plain
    sample_rate: float = 1.0
    log_source: str  # stdout / stderr / file / container
    destinations: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=_now_ts)


class LogSource(BaseModel):
    id: str = Field(default_factory=lambda: _uid("log"))
    resource_id: str
    source_type: str  # stdout / stderr / file / container
    path: str = ""
    format: str = "json"
    last_collected_at: float = 0
    created_at: float = Field(default_factory=_now_ts)


class TelemetryFormatEngine:
    """#23 Telemetry / Format / Container log source 引擎。"""

    _MAX_CONFIGS = 200
    _MAX_SOURCES = 200
    _VALID_FORMATS = {"json", "otel", "plain"}
    _VALID_LOG_SOURCES = {"stdout", "stderr", "file", "container"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._configs: dict[str, TelemetryConfig] = {}  # resource_id -> config
        self._sources: dict[str, LogSource] = {}

    # ── configs ──────────────────────────────────────────────────
    def set_config(
        self,
        resource_id: str,
        enabled: bool = True,
        format: str = "json",
        sample_rate: float = 1.0,
        log_source: str = "stdout",
        destinations: list[str] | None = None,
    ) -> TelemetryConfig:
        if format not in self._VALID_FORMATS:
            raise AutoscaleTelemetryError(
                "INVALID_FORMAT", f"format must be one of {sorted(self._VALID_FORMATS)}"
            )
        if log_source not in self._VALID_LOG_SOURCES:
            raise AutoscaleTelemetryError(
                "INVALID_LOG_SOURCE",
                f"log_source must be one of {sorted(self._VALID_LOG_SOURCES)}",
            )
        if sample_rate < 0 or sample_rate > 1:
            raise AutoscaleTelemetryError(
                "INVALID_SAMPLE_RATE", "sample_rate must be in [0, 1]"
            )
        with self._lock:
            existing = self._configs.get(resource_id)
            config = TelemetryConfig(
                id=existing.id if existing is not None else _uid("tel"),
                resource_id=resource_id,
                enabled=enabled,
                format=format,
                sample_rate=sample_rate,
                log_source=log_source,
                destinations=destinations if destinations is not None else [],
                created_at=existing.created_at if existing is not None else _now_ts(),
            )
            self._configs[resource_id] = config
        return config

    def get_config(self, resource_id: str) -> TelemetryConfig:
        with self._lock:
            config = self._configs.get(resource_id)
        if config is None:
            raise AutoscaleTelemetryError(
                "NOT_FOUND", f"telemetry config for resource {resource_id} not found"
            )
        return config

    def list_configs(self, enabled_only: bool = False) -> list[TelemetryConfig]:
        with self._lock:
            results = list(self._configs.values())
        if enabled_only:
            results = [c for c in results if c.enabled]
        return sorted(results, key=lambda c: c.created_at)

    def update_config(
        self, resource_id: str, updates: dict[str, Any]
    ) -> TelemetryConfig:
        with self._lock:
            config = self._configs.get(resource_id)
            if config is None:
                raise AutoscaleTelemetryError(
                    "NOT_FOUND",
                    f"telemetry config for resource {resource_id} not found",
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k != "resource_id" and k in type(config).model_fields
            }
            # 校验可枚举字段
            if "format" in applicable and applicable["format"] not in self._VALID_FORMATS:
                raise AutoscaleTelemetryError(
                    "INVALID_FORMAT",
                    f"format must be one of {sorted(self._VALID_FORMATS)}",
                )
            if (
                "log_source" in applicable
                and applicable["log_source"] not in self._VALID_LOG_SOURCES
            ):
                raise AutoscaleTelemetryError(
                    "INVALID_LOG_SOURCE",
                    f"log_source must be one of {sorted(self._VALID_LOG_SOURCES)}",
                )
            if "sample_rate" in applicable and not (
                0 <= applicable["sample_rate"] <= 1
            ):
                raise AutoscaleTelemetryError(
                    "INVALID_SAMPLE_RATE", "sample_rate must be in [0, 1]"
                )
            updated = config.model_copy(update=applicable)
            self._configs[resource_id] = updated
        return updated

    def delete_config(self, resource_id: str) -> bool:
        with self._lock:
            return self._configs.pop(resource_id, None) is not None

    # ── sources ──────────────────────────────────────────────────
    def register_source(
        self,
        resource_id: str,
        source_type: str,
        path: str = "",
        format: str = "json",
    ) -> LogSource:
        if source_type not in self._VALID_LOG_SOURCES:
            raise AutoscaleTelemetryError(
                "INVALID_SOURCE_TYPE",
                f"source_type must be one of {sorted(self._VALID_LOG_SOURCES)}",
            )
        source = LogSource(
            resource_id=resource_id,
            source_type=source_type,
            path=path,
            format=format,
        )
        with self._lock:
            if len(self._sources) >= self._MAX_SOURCES:
                oldest_id = min(
                    self._sources,
                    key=lambda sid: self._sources[sid].created_at,
                )
                del self._sources[oldest_id]
            self._sources[source.id] = source
        return source

    def get_source(self, source_id: str) -> LogSource:
        with self._lock:
            source = self._sources.get(source_id)
        if source is None:
            raise AutoscaleTelemetryError(
                "NOT_FOUND", f"log source {source_id} not found"
            )
        return source

    def list_sources(
        self,
        resource_id: str | None = None,
        source_type: str | None = None,
    ) -> list[LogSource]:
        with self._lock:
            results = list(self._sources.values())
        if resource_id is not None:
            results = [s for s in results if s.resource_id == resource_id]
        if source_type is not None:
            results = [s for s in results if s.source_type == source_type]
        return sorted(results, key=lambda s: s.created_at)

    def collect_from_source(self, source_id: str) -> LogSource:
        with self._lock:
            source = self._sources.get(source_id)
            if source is None:
                raise AutoscaleTelemetryError(
                    "NOT_FOUND", f"log source {source_id} not found"
                )
            updated = source.model_copy(update={"last_collected_at": _now_ts()})
            self._sources[source_id] = updated
        return updated

    def delete_source(self, source_id: str) -> bool:
        with self._lock:
            return self._sources.pop(source_id, None) is not None


# ════════════════════ #24 Volume mounts ════════════════════

class VolumeMount(BaseModel):
    id: str = Field(default_factory=lambda: _uid("vol"))
    name: str
    mount_path: str
    storage_type: str  # emptydir / pvc / configmap / secret
    size_gb: float = 0
    read_only: bool = False
    shared: bool = False
    access_mode: str  # readwrite / readonly / many
    targets: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=_now_ts)


class VolumeAttachment(BaseModel):
    id: str = Field(default_factory=lambda: _uid("att"))
    volume_id: str
    target_id: str
    sub_path: str = ""
    mount_path: str = ""
    read_only: bool = False
    created_at: float = Field(default_factory=_now_ts)


class VolumeMountEngine:
    """#24 Volume mounts 副本内共享卷引擎。"""

    _MAX_VOLUMES = 200
    _MAX_ATTACHMENTS = 200
    _VALID_STORAGE_TYPES = {"emptydir", "pvc", "configmap", "secret"}
    _VALID_ACCESS_MODES = {"readwrite", "readonly", "many"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._volumes: dict[str, VolumeMount] = {}
        self._attachments: dict[str, VolumeAttachment] = {}

    # ── volumes ──────────────────────────────────────────────────
    def create_volume(
        self,
        name: str,
        mount_path: str,
        storage_type: str = "emptydir",
        size_gb: float = 0,
        read_only: bool = False,
        shared: bool = False,
        access_mode: str = "readwrite",
    ) -> VolumeMount:
        if storage_type not in self._VALID_STORAGE_TYPES:
            raise AutoscaleTelemetryError(
                "INVALID_STORAGE_TYPE",
                f"storage_type must be one of {sorted(self._VALID_STORAGE_TYPES)}",
            )
        if access_mode not in self._VALID_ACCESS_MODES:
            raise AutoscaleTelemetryError(
                "INVALID_ACCESS_MODE",
                f"access_mode must be one of {sorted(self._VALID_ACCESS_MODES)}",
            )
        volume = VolumeMount(
            name=name,
            mount_path=mount_path,
            storage_type=storage_type,
            size_gb=size_gb,
            read_only=read_only,
            shared=shared,
            access_mode=access_mode,
        )
        with self._lock:
            if len(self._volumes) >= self._MAX_VOLUMES:
                oldest_id = min(
                    self._volumes,
                    key=lambda vid: self._volumes[vid].created_at,
                )
                del self._volumes[oldest_id]
            self._volumes[volume.id] = volume
        return volume

    def get_volume(self, volume_id: str) -> VolumeMount:
        with self._lock:
            volume = self._volumes.get(volume_id)
        if volume is None:
            raise AutoscaleTelemetryError(
                "NOT_FOUND", f"volume {volume_id} not found"
            )
        return volume

    def list_volumes(
        self,
        storage_type: str | None = None,
        shared_only: bool = False,
    ) -> list[VolumeMount]:
        with self._lock:
            results = list(self._volumes.values())
        if storage_type is not None:
            results = [v for v in results if v.storage_type == storage_type]
        if shared_only:
            results = [v for v in results if v.shared]
        return sorted(results, key=lambda v: v.created_at)

    def update_volume(
        self, volume_id: str, updates: dict[str, Any]
    ) -> VolumeMount:
        with self._lock:
            volume = self._volumes.get(volume_id)
            if volume is None:
                raise AutoscaleTelemetryError(
                    "NOT_FOUND", f"volume {volume_id} not found"
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(volume).model_fields
            }
            if (
                "storage_type" in applicable
                and applicable["storage_type"] not in self._VALID_STORAGE_TYPES
            ):
                raise AutoscaleTelemetryError(
                    "INVALID_STORAGE_TYPE",
                    f"storage_type must be one of {sorted(self._VALID_STORAGE_TYPES)}",
                )
            if (
                "access_mode" in applicable
                and applicable["access_mode"] not in self._VALID_ACCESS_MODES
            ):
                raise AutoscaleTelemetryError(
                    "INVALID_ACCESS_MODE",
                    f"access_mode must be one of {sorted(self._VALID_ACCESS_MODES)}",
                )
            updated = volume.model_copy(update=applicable)
            self._volumes[volume_id] = updated
        return updated

    def delete_volume(self, volume_id: str) -> bool:
        with self._lock:
            return self._volumes.pop(volume_id, None) is not None

    # ── attachments ──────────────────────────────────────────────
    def attach_volume(
        self,
        volume_id: str,
        target_id: str,
        sub_path: str = "",
        mount_path: str = "",
        read_only: bool = False,
    ) -> VolumeAttachment:
        with self._lock:
            if volume_id not in self._volumes:
                raise AutoscaleTelemetryError(
                    "NOT_FOUND", f"volume {volume_id} not found"
                )
            attachment = VolumeAttachment(
                volume_id=volume_id,
                target_id=target_id,
                sub_path=sub_path,
                mount_path=mount_path,
                read_only=read_only,
            )
            if len(self._attachments) >= self._MAX_ATTACHMENTS:
                oldest_id = min(
                    self._attachments,
                    key=lambda aid: self._attachments[aid].created_at,
                )
                del self._attachments[oldest_id]
            self._attachments[attachment.id] = attachment
        return attachment

    def get_attachment(self, attachment_id: str) -> VolumeAttachment:
        with self._lock:
            attachment = self._attachments.get(attachment_id)
        if attachment is None:
            raise AutoscaleTelemetryError(
                "NOT_FOUND", f"attachment {attachment_id} not found"
            )
        return attachment

    def list_attachments(
        self,
        volume_id: str | None = None,
        target_id: str | None = None,
    ) -> list[VolumeAttachment]:
        with self._lock:
            results = list(self._attachments.values())
        if volume_id is not None:
            results = [a for a in results if a.volume_id == volume_id]
        if target_id is not None:
            results = [a for a in results if a.target_id == target_id]
        return sorted(results, key=lambda a: a.created_at)

    def detach_volume(self, attachment_id: str) -> bool:
        with self._lock:
            return self._attachments.pop(attachment_id, None) is not None

    def get_shared_volumes(self) -> list[VolumeMount]:
        with self._lock:
            results = [v for v in self._volumes.values() if v.shared]
        return sorted(results, key=lambda v: v.created_at)


# ════════════════════ #25 COP Realtime ════════════════════

class CopMetric(BaseModel):
    id: str = Field(default_factory=lambda: _uid("cop"))
    resource_id: str
    metric_name: str
    value: float
    unit: str = ""
    timestamp: float = Field(default_factory=_now_ts)
    severity: str  # normal / warning / critical
    metadata: dict[str, Any] = Field(default_factory=dict)


class CopAlert(BaseModel):
    id: str = Field(default_factory=lambda: _uid("copalert"))
    metric_id: str
    resource_id: str
    metric_name: str
    value: float
    threshold: float
    severity: str  # warning / critical
    message: str = ""
    acknowledged: bool = False
    created_at: float = Field(default_factory=_now_ts)


class CopRealtimeEngine:
    """#25 COP 实时态势引擎。"""

    _MAX_METRICS = 200
    _MAX_ALERTS = 200

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics: dict[str, CopMetric] = {}
        self._alerts: dict[str, CopAlert] = {}
        # (resource_id, metric_name) -> (warning, critical)
        self._thresholds: dict[tuple[str, str], tuple[float, float]] = {}

    # ── thresholds ───────────────────────────────────────────────
    def set_threshold(
        self,
        resource_id: str,
        metric_name: str,
        warning: float,
        critical: float,
    ) -> dict[str, Any]:
        if warning >= critical:
            raise AutoscaleTelemetryError(
                "INVALID_THRESHOLD", "warning must be < critical"
            )
        with self._lock:
            self._thresholds[(resource_id, metric_name)] = (warning, critical)
        return {
            "resource_id": resource_id,
            "metric_name": metric_name,
            "warning": warning,
            "critical": critical,
        }

    def get_thresholds(
        self, resource_id: str | None = None
    ) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._thresholds.items())
        results: list[dict[str, Any]] = []
        for (rid, mname), (warn, crit) in items:
            if resource_id is not None and rid != resource_id:
                continue
            results.append(
                {
                    "resource_id": rid,
                    "metric_name": mname,
                    "warning": warn,
                    "critical": crit,
                }
            )
        return results

    def delete_threshold(self, resource_id: str, metric_name: str) -> bool:
        with self._lock:
            return self._thresholds.pop((resource_id, metric_name), None) is not None

    # ── metrics ──────────────────────────────────────────────────
    def record_metric(
        self,
        resource_id: str,
        metric_name: str,
        value: float,
        unit: str = "",
        metadata: dict | None = None,
    ) -> CopMetric:
        with self._lock:
            warn, crit = self._thresholds.get(
                (resource_id, metric_name), (None, None)
            )
            if crit is not None and value >= crit:
                severity = "critical"
            elif warn is not None and value >= warn:
                severity = "warning"
            else:
                severity = "normal"
            metric = CopMetric(
                resource_id=resource_id,
                metric_name=metric_name,
                value=value,
                unit=unit,
                severity=severity,
                metadata=metadata if metadata is not None else {},
            )
            if len(self._metrics) >= self._MAX_METRICS:
                oldest_id = min(
                    self._metrics,
                    key=lambda mid: self._metrics[mid].timestamp,
                )
                del self._metrics[oldest_id]
            self._metrics[metric.id] = metric

            alert: CopAlert | None = None
            if severity in ("warning", "critical"):
                threshold_value = crit if severity == "critical" else warn
                alert = CopAlert(
                    metric_id=metric.id,
                    resource_id=resource_id,
                    metric_name=metric_name,
                    value=value,
                    threshold=threshold_value if threshold_value is not None else 0.0,
                    severity=severity,
                    message=f"{metric_name}={value} {unit}".strip(),
                )
                if len(self._alerts) >= self._MAX_ALERTS:
                    oldest_aid = min(
                        self._alerts,
                        key=lambda aid: self._alerts[aid].created_at,
                    )
                    del self._alerts[oldest_aid]
                self._alerts[alert.id] = alert
        return metric

    def get_metric(self, metric_id: str) -> CopMetric:
        with self._lock:
            metric = self._metrics.get(metric_id)
        if metric is None:
            raise AutoscaleTelemetryError(
                "NOT_FOUND", f"metric {metric_id} not found"
            )
        return metric

    def list_metrics(
        self,
        resource_id: str | None = None,
        severity: str | None = None,
    ) -> list[CopMetric]:
        with self._lock:
            results = list(self._metrics.values())
        if resource_id is not None:
            results = [m for m in results if m.resource_id == resource_id]
        if severity is not None:
            results = [m for m in results if m.severity == severity]
        return sorted(results, key=lambda m: m.timestamp)

    def delete_metric(self, metric_id: str) -> bool:
        with self._lock:
            return self._metrics.pop(metric_id, None) is not None

    # ── alerts ───────────────────────────────────────────────────
    def get_alert(self, alert_id: str) -> CopAlert:
        with self._lock:
            alert = self._alerts.get(alert_id)
        if alert is None:
            raise AutoscaleTelemetryError(
                "NOT_FOUND", f"alert {alert_id} not found"
            )
        return alert

    def list_alerts(
        self,
        resource_id: str | None = None,
        severity: str | None = None,
        acknowledged: bool | None = None,
    ) -> list[CopAlert]:
        with self._lock:
            results = list(self._alerts.values())
        if resource_id is not None:
            results = [a for a in results if a.resource_id == resource_id]
        if severity is not None:
            results = [a for a in results if a.severity == severity]
        if acknowledged is not None:
            results = [a for a in results if a.acknowledged == acknowledged]
        return sorted(results, key=lambda a: a.created_at)

    def acknowledge_alert(self, alert_id: str) -> CopAlert:
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                raise AutoscaleTelemetryError(
                    "NOT_FOUND", f"alert {alert_id} not found"
                )
            updated = alert.model_copy(update={"acknowledged": True})
            self._alerts[alert_id] = updated
        return updated

    # ── dashboard ────────────────────────────────────────────────
    def get_dashboard(self) -> dict[str, Any]:
        with self._lock:
            metrics = list(self._metrics.values())
            alerts = list(self._alerts.values())
            total_metrics = len(metrics)
            total_alerts = len(alerts)
            active_alerts = sum(1 for a in alerts if not a.acknowledged)
            critical_alerts = sum(1 for a in alerts if a.severity == "critical")
            warning_alerts = sum(1 for a in alerts if a.severity == "warning")
            resources_monitored = len({m.resource_id for m in metrics})
        return {
            "total_metrics": total_metrics,
            "total_alerts": total_alerts,
            "active_alerts": active_alerts,
            "critical_alerts": critical_alerts,
            "warning_alerts": warning_alerts,
            "resources_monitored": resources_monitored,
        }


# ────────────────────────────────────────────────────────────────
# 单例 getter（双重检查锁）
# ────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_autoscale_engine: PredictiveAutoscaleEngine | None = None
_telemetry_engine: TelemetryFormatEngine | None = None
_volume_engine: VolumeMountEngine | None = None
_cop_engine: CopRealtimeEngine | None = None


def get_predictive_autoscale_engine() -> PredictiveAutoscaleEngine:
    global _autoscale_engine
    if _autoscale_engine is None:
        with _lock:
            if _autoscale_engine is None:
                _autoscale_engine = PredictiveAutoscaleEngine()
    return _autoscale_engine


def get_telemetry_format_engine() -> TelemetryFormatEngine:
    global _telemetry_engine
    if _telemetry_engine is None:
        with _lock:
            if _telemetry_engine is None:
                _telemetry_engine = TelemetryFormatEngine()
    return _telemetry_engine


def get_volume_mount_engine() -> VolumeMountEngine:
    global _volume_engine
    if _volume_engine is None:
        with _lock:
            if _volume_engine is None:
                _volume_engine = VolumeMountEngine()
    return _volume_engine


def get_cop_realtime_engine() -> CopRealtimeEngine:
    global _cop_engine
    if _cop_engine is None:
        with _lock:
            if _cop_engine is None:
                _cop_engine = CopRealtimeEngine()
    return _cop_engine
