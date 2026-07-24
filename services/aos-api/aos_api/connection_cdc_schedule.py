"""W2-AY · Connection CDC & Schedule 引擎。

包含三个引擎：
- ConnectionCdcEngine: CDC配置管理
- ScheduleTriggerEngine: 调度触发机制
- StorageRouteGuideEngine: 存储路由向导
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


class ConnectionCdcScheduleError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class CdcConfigError(ConnectionCdcScheduleError):
    pass


class ScheduleTriggerError(ConnectionCdcScheduleError):
    pass


class StorageRouteError(ConnectionCdcScheduleError):
    pass


_CDC_CAPTURE_MODES = {"full", "incremental", "snapshot"}
_CDC_STATUS_VALUES = {"running", "stopped", "paused", "error"}

_SCHEDULE_TARGET_TYPES = {"pipeline", "workflow", "function"}
_SCHEDULE_STATUS_VALUES = {"active", "inactive", "paused"}

_STORAGE_ROUTE_TYPES = {"copy", "move", "sync", "mirror"}
_STORAGE_SCHEDULE_TYPES = {"on_demand", "periodic", "event"}
_STORAGE_ROUTE_STATUS_VALUES = {"active", "inactive", "running", "completed", "failed"}


class CdcConfig(BaseModel):
    cdc_id: str
    connection_id: str
    enabled: bool
    capture_mode: str
    snapshot_interval_hours: int
    max_backlog_records: int
    last_capture_at: Optional[datetime] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ScheduleTrigger(BaseModel):
    trigger_id: str
    name: str
    cron_expression: str
    timezone: str
    enabled: bool
    target_type: str
    target_id: str
    last_triggered_at: Optional[datetime] = None
    next_trigger_at: Optional[datetime] = None
    status: str
    created_at: datetime
    updated_at: datetime


class StorageRoute(BaseModel):
    route_id: str
    name: str
    source_path: str
    target_path: str
    route_type: str
    schedule_type: str
    schedule_cron: Optional[str] = None
    enabled: bool
    status: str
    last_run_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ConnectionCdcEngine:
    _instance: Optional[ConnectionCdcEngine] = None
    _lock: threading.Lock = threading.Lock()
    _max_records: int = 200

    def __new__(cls) -> ConnectionCdcEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._cdc_configs: dict[str, CdcConfig] = {}
        return cls._instance

    def _evict_oldest(self) -> None:
        if len(self._cdc_configs) <= self._max_records:
            return
        oldest = min(
            self._cdc_configs.values(),
            key=lambda x: x.updated_at or datetime.min
        )
        del self._cdc_configs[oldest.cdc_id]

    def configure_cdc(
        self,
        connection_id: str,
        capture_mode: str = "incremental",
        snapshot_interval_hours: int = 24,
        max_backlog_records: int = 10000,
        enabled: bool = True,
    ) -> CdcConfig:
        if not connection_id:
            raise CdcConfigError("MISSING_CONNECTION", "connection_id 不可为空", 400)
        if capture_mode not in _CDC_CAPTURE_MODES:
            raise CdcConfigError(
                "INVALID_CAPTURE_MODE",
                f"capture_mode 必须是 {', '.join(_CDC_CAPTURE_MODES)}",
                400
            )
        cdc = CdcConfig(
            cdc_id=_new_id("cdc"),
            connection_id=connection_id,
            enabled=enabled,
            capture_mode=capture_mode,
            snapshot_interval_hours=snapshot_interval_hours,
            max_backlog_records=max_backlog_records,
            status="running" if enabled else "stopped",
            created_at=_now(),
            updated_at=_now(),
        )
        self._cdc_configs[cdc.cdc_id] = cdc
        self._evict_oldest()
        return cdc

    def get_cdc(self, cdc_id: str) -> CdcConfig:
        cdc = self._cdc_configs.get(cdc_id)
        if cdc is None:
            raise CdcConfigError("NOT_FOUND", f"CDC配置 {cdc_id} 不存在", 404)
        return cdc

    def list_cdc(
        self,
        connection_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[CdcConfig]:
        results = list(self._cdc_configs.values())
        if connection_id:
            results = [c for c in results if c.connection_id == connection_id]
        if status:
            if status not in _CDC_STATUS_VALUES:
                raise CdcConfigError(
                    "INVALID_STATUS",
                    f"status 必须是 {', '.join(_CDC_STATUS_VALUES)}",
                    400
                )
            results = [c for c in results if c.status == status]
        return results

    def update_cdc(
        self,
        cdc_id: str,
        enabled: Optional[bool] = None,
        capture_mode: Optional[str] = None,
        snapshot_interval_hours: Optional[int] = None,
        max_backlog_records: Optional[int] = None,
    ) -> CdcConfig:
        cdc = self._cdc_configs.get(cdc_id)
        if cdc is None:
            raise CdcConfigError("NOT_FOUND", f"CDC配置 {cdc_id} 不存在", 404)
        if capture_mode is not None:
            if capture_mode not in _CDC_CAPTURE_MODES:
                raise CdcConfigError(
                    "INVALID_CAPTURE_MODE",
                    f"capture_mode 必须是 {', '.join(_CDC_CAPTURE_MODES)}",
                    400
                )
            cdc.capture_mode = capture_mode
        if enabled is not None:
            cdc.enabled = enabled
            cdc.status = "running" if enabled else "stopped"
        if snapshot_interval_hours is not None:
            cdc.snapshot_interval_hours = snapshot_interval_hours
        if max_backlog_records is not None:
            cdc.max_backlog_records = max_backlog_records
        cdc.updated_at = _now()
        return cdc

    def delete_cdc(self, cdc_id: str) -> bool:
        return self._cdc_configs.pop(cdc_id, None) is not None

    def toggle_cdc(self, cdc_id: str, enabled: bool) -> CdcConfig:
        return self.update_cdc(cdc_id, enabled=enabled)


class ScheduleTriggerEngine:
    _instance: Optional[ScheduleTriggerEngine] = None
    _lock: threading.Lock = threading.Lock()
    _max_records: int = 200

    def __new__(cls) -> ScheduleTriggerEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._triggers: dict[str, ScheduleTrigger] = {}
        return cls._instance

    def _evict_oldest(self) -> None:
        if len(self._triggers) <= self._max_records:
            return
        oldest = min(
            self._triggers.values(),
            key=lambda x: x.updated_at or datetime.min
        )
        del self._triggers[oldest.trigger_id]

    def _validate_cron(self, cron: str) -> None:
        parts = cron.strip().split()
        if len(parts) != 5:
            raise ScheduleTriggerError("INVALID_CRON", "cron表达式需要5个字段", 400)

    def create_trigger(
        self,
        name: str,
        cron_expression: str,
        timezone: str = "Asia/Shanghai",
        enabled: bool = True,
        target_type: str = "pipeline",
        target_id: str = "",
    ) -> ScheduleTrigger:
        if not name:
            raise ScheduleTriggerError("MISSING_NAME", "name 不可为空", 400)
        self._validate_cron(cron_expression)
        if target_type not in _SCHEDULE_TARGET_TYPES:
            raise ScheduleTriggerError(
                "INVALID_TARGET_TYPE",
                f"target_type 必须是 {', '.join(_SCHEDULE_TARGET_TYPES)}",
                400
            )
        trigger = ScheduleTrigger(
            trigger_id=_new_id("str"),
            name=name,
            cron_expression=cron_expression,
            timezone=timezone,
            enabled=enabled,
            target_type=target_type,
            target_id=target_id,
            status="active" if enabled else "inactive",
            created_at=_now(),
            updated_at=_now(),
        )
        self._triggers[trigger.trigger_id] = trigger
        self._evict_oldest()
        return trigger

    def get_trigger(self, trigger_id: str) -> ScheduleTrigger:
        trigger = self._triggers.get(trigger_id)
        if trigger is None:
            raise ScheduleTriggerError("NOT_FOUND", f"触发器 {trigger_id} 不存在", 404)
        return trigger

    def list_triggers(
        self,
        name: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[ScheduleTrigger]:
        results = list(self._triggers.values())
        if name:
            results = [t for t in results if t.name == name]
        if target_type:
            if target_type not in _SCHEDULE_TARGET_TYPES:
                raise ScheduleTriggerError(
                    "INVALID_TARGET_TYPE",
                    f"target_type 必须是 {', '.join(_SCHEDULE_TARGET_TYPES)}",
                    400
                )
            results = [t for t in results if t.target_type == target_type]
        if target_id:
            results = [t for t in results if t.target_id == target_id]
        if status:
            if status not in _SCHEDULE_STATUS_VALUES:
                raise ScheduleTriggerError(
                    "INVALID_STATUS",
                    f"status 必须是 {', '.join(_SCHEDULE_STATUS_VALUES)}",
                    400
                )
            results = [t for t in results if t.status == status]
        return results

    def update_trigger(
        self,
        trigger_id: str,
        name: Optional[str] = None,
        cron_expression: Optional[str] = None,
        timezone: Optional[str] = None,
        enabled: Optional[bool] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
    ) -> ScheduleTrigger:
        trigger = self._triggers.get(trigger_id)
        if trigger is None:
            raise ScheduleTriggerError("NOT_FOUND", f"触发器 {trigger_id} 不存在", 404)
        if name is not None:
            if not name:
                raise ScheduleTriggerError("MISSING_NAME", "name 不可为空", 400)
            trigger.name = name
        if cron_expression is not None:
            self._validate_cron(cron_expression)
            trigger.cron_expression = cron_expression
        if timezone is not None:
            trigger.timezone = timezone
        if enabled is not None:
            trigger.enabled = enabled
            trigger.status = "active" if enabled else "inactive"
        if target_type is not None:
            if target_type not in _SCHEDULE_TARGET_TYPES:
                raise ScheduleTriggerError(
                    "INVALID_TARGET_TYPE",
                    f"target_type 必须是 {', '.join(_SCHEDULE_TARGET_TYPES)}",
                    400
                )
            trigger.target_type = target_type
        if target_id is not None:
            trigger.target_id = target_id
        trigger.updated_at = _now()
        return trigger

    def delete_trigger(self, trigger_id: str) -> bool:
        return self._triggers.pop(trigger_id, None) is not None

    def toggle_trigger(self, trigger_id: str, enabled: bool) -> ScheduleTrigger:
        return self.update_trigger(trigger_id, enabled=enabled)


class StorageRouteGuideEngine:
    _instance: Optional[StorageRouteGuideEngine] = None
    _lock: threading.Lock = threading.Lock()
    _max_records: int = 200

    def __new__(cls) -> StorageRouteGuideEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._routes: dict[str, StorageRoute] = {}
        return cls._instance

    def _evict_oldest(self) -> None:
        if len(self._routes) <= self._max_records:
            return
        oldest = min(
            self._routes.values(),
            key=lambda x: x.updated_at or datetime.min
        )
        del self._routes[oldest.route_id]

    def create_route(
        self,
        name: str,
        source_path: str,
        target_path: str,
        route_type: str = "copy",
        schedule_type: str = "on_demand",
        schedule_cron: Optional[str] = None,
        enabled: bool = True,
    ) -> StorageRoute:
        if not name:
            raise StorageRouteError("MISSING_NAME", "name 不可为空", 400)
        if not source_path:
            raise StorageRouteError("MISSING_SOURCE_PATH", "source_path 不可为空", 400)
        if not target_path:
            raise StorageRouteError("MISSING_TARGET_PATH", "target_path 不可为空", 400)
        if route_type not in _STORAGE_ROUTE_TYPES:
            raise StorageRouteError(
                "INVALID_ROUTE_TYPE",
                f"route_type 必须是 {', '.join(_STORAGE_ROUTE_TYPES)}",
                400
            )
        if schedule_type not in _STORAGE_SCHEDULE_TYPES:
            raise StorageRouteError(
                "INVALID_SCHEDULE_TYPE",
                f"schedule_type 必须是 {', '.join(_STORAGE_SCHEDULE_TYPES)}",
                400
            )
        route = StorageRoute(
            route_id=_new_id("srg"),
            name=name,
            source_path=source_path,
            target_path=target_path,
            route_type=route_type,
            schedule_type=schedule_type,
            schedule_cron=schedule_cron,
            enabled=enabled,
            status="active" if enabled else "inactive",
            created_at=_now(),
            updated_at=_now(),
        )
        self._routes[route.route_id] = route
        self._evict_oldest()
        return route

    def get_route(self, route_id: str) -> StorageRoute:
        route = self._routes.get(route_id)
        if route is None:
            raise StorageRouteError("NOT_FOUND", f"存储路由 {route_id} 不存在", 404)
        return route

    def list_routes(
        self,
        name: Optional[str] = None,
        route_type: Optional[str] = None,
        schedule_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[StorageRoute]:
        results = list(self._routes.values())
        if name:
            results = [r for r in results if r.name == name]
        if route_type:
            if route_type not in _STORAGE_ROUTE_TYPES:
                raise StorageRouteError(
                    "INVALID_ROUTE_TYPE",
                    f"route_type 必须是 {', '.join(_STORAGE_ROUTE_TYPES)}",
                    400
                )
            results = [r for r in results if r.route_type == route_type]
        if schedule_type:
            if schedule_type not in _STORAGE_SCHEDULE_TYPES:
                raise StorageRouteError(
                    "INVALID_SCHEDULE_TYPE",
                    f"schedule_type 必须是 {', '.join(_STORAGE_SCHEDULE_TYPES)}",
                    400
                )
            results = [r for r in results if r.schedule_type == schedule_type]
        if status:
            if status not in _STORAGE_ROUTE_STATUS_VALUES:
                raise StorageRouteError(
                    "INVALID_STATUS",
                    f"status 必须是 {', '.join(_STORAGE_ROUTE_STATUS_VALUES)}",
                    400
                )
            results = [r for r in results if r.status == status]
        return results

    def update_route(
        self,
        route_id: str,
        name: Optional[str] = None,
        source_path: Optional[str] = None,
        target_path: Optional[str] = None,
        route_type: Optional[str] = None,
        schedule_type: Optional[str] = None,
        schedule_cron: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> StorageRoute:
        route = self._routes.get(route_id)
        if route is None:
            raise StorageRouteError("NOT_FOUND", f"存储路由 {route_id} 不存在", 404)
        if name is not None:
            if not name:
                raise StorageRouteError("MISSING_NAME", "name 不可为空", 400)
            route.name = name
        if source_path is not None:
            if not source_path:
                raise StorageRouteError("MISSING_SOURCE_PATH", "source_path 不可为空", 400)
            route.source_path = source_path
        if target_path is not None:
            if not target_path:
                raise StorageRouteError("MISSING_TARGET_PATH", "target_path 不可为空", 400)
            route.target_path = target_path
        if route_type is not None:
            if route_type not in _STORAGE_ROUTE_TYPES:
                raise StorageRouteError(
                    "INVALID_ROUTE_TYPE",
                    f"route_type 必须是 {', '.join(_STORAGE_ROUTE_TYPES)}",
                    400
                )
            route.route_type = route_type
        if schedule_type is not None:
            if schedule_type not in _STORAGE_SCHEDULE_TYPES:
                raise StorageRouteError(
                    "INVALID_SCHEDULE_TYPE",
                    f"schedule_type 必须是 {', '.join(_STORAGE_SCHEDULE_TYPES)}",
                    400
                )
            route.schedule_type = schedule_type
        if schedule_cron is not None:
            route.schedule_cron = schedule_cron
        if enabled is not None:
            route.enabled = enabled
            route.status = "active" if enabled else "inactive"
        route.updated_at = _now()
        return route

    def delete_route(self, route_id: str) -> bool:
        return self._routes.pop(route_id, None) is not None

    def execute_route(self, route_id: str) -> StorageRoute:
        route = self._routes.get(route_id)
        if route is None:
            raise StorageRouteError("NOT_FOUND", f"存储路由 {route_id} 不存在", 404)
        route.status = "running"
        route.updated_at = _now()
        route.status = "completed"
        route.last_run_at = _now()
        return route