"""W2-AX · Dataset Preview Health 引擎（ColumnStats / PreviewViews / DataHealthCheck）."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

# ════════════════════ 常量 ════════════════════

_MAX_STATS = 200
_MAX_VIEWS = 200
_MAX_CHECKS = 200

_VALID_VIEW_TYPES = {"table", "chart", "profile", "comparison"}
_VALID_CHECK_TYPES = {"freshness", "volume", "schema", "nulls", "uniqueness", "range"}
_VALID_STATUSES = {"pending", "running", "passed", "failed", "errored"}
_VALID_SEVERITIES = {"critical", "warning", "info"}


# ════════════════════ 错误类 ════════════════════

class ColumnStatsError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class PreviewViewError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class DataHealthCheckError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════ 数据模型 ════════════════════

class ColumnStats(BaseModel):
    stats_id: str = Field(default_factory=lambda: "cs-" + uuid.uuid4().hex[:10])
    dataset_rid: str
    column_name: str
    null_count: int = 0
    null_percent: float = 0.0
    distinct_count: int = 0
    distinct_percent: float = 0.0
    min_value: Optional[str] = None
    max_value: Optional[str] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std_dev: Optional[float] = None
    sample_values: list[Any] = Field(default_factory=list)
    data_type: str = ""
    total_rows: int = 0
    last_computed_at: float = Field(default_factory=lambda: time.time())


class PreviewView(BaseModel):
    view_id: str = Field(default_factory=lambda: "pv-" + uuid.uuid4().hex[:10])
    dataset_rid: str
    view_type: str
    config_data: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class DataHealthCheck(BaseModel):
    check_id: str = Field(default_factory=lambda: "hc-" + uuid.uuid4().hex[:10])
    dataset_rid: str
    check_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    last_run_at: Optional[float] = None
    last_result: Optional[dict[str, Any]] = None
    severity: str = "warning"
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


# ════════════════════ Engine 1: ColumnStatsEngine ════════════════════

class ColumnStatsEngine:
    _instance: Optional[ColumnStatsEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._stats: list[ColumnStats] = []
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ColumnStatsEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def compute_stats(self, stats: ColumnStats) -> ColumnStats:
        if not stats.dataset_rid:
            raise ColumnStatsError("MISSING_DATASET", "dataset_rid is required")
        if not stats.column_name:
            raise ColumnStatsError("MISSING_COLUMN", "column_name is required")
        with self._lock:
            if len(self._stats) >= _MAX_STATS:
                self._stats.pop(0)
            self._stats.append(stats)
        return stats

    def get_stats(self, stats_id: str) -> ColumnStats:
        for s in self._stats:
            if s.stats_id == stats_id:
                return s
        raise ColumnStatsError("NOT_FOUND", f"stats {stats_id} not found")

    def list_stats(
        self,
        dataset_rid: Optional[str] = None,
        column_name: Optional[str] = None,
        data_type: Optional[str] = None,
    ) -> list[ColumnStats]:
        items = list(self._stats)
        if dataset_rid is not None:
            items = [s for s in items if s.dataset_rid == dataset_rid]
        if column_name is not None:
            items = [s for s in items if s.column_name == column_name]
        if data_type is not None:
            items = [s for s in items if s.data_type == data_type]
        return items

    def delete_stats(self, stats_id: str) -> bool:
        for i, s in enumerate(self._stats):
            if s.stats_id == stats_id:
                with self._lock:
                    if i < len(self._stats) and self._stats[i].stats_id == stats_id:
                        self._stats.pop(i)
                        return True
                return True
        return False


# ════════════════════ Engine 2: DatasetPreviewViewsEngine ════════════════════

class DatasetPreviewViewsEngine:
    _instance: Optional[DatasetPreviewViewsEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._views: list[PreviewView] = []
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> DatasetPreviewViewsEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_view(self, view: PreviewView) -> PreviewView:
        if not view.dataset_rid:
            raise PreviewViewError("MISSING_DATASET", "dataset_rid is required")
        if view.view_type not in _VALID_VIEW_TYPES:
            raise PreviewViewError("INVALID_VIEW_TYPE", f"view_type must be one of {_VALID_VIEW_TYPES}")
        with self._lock:
            if len(self._views) >= _MAX_VIEWS:
                self._views.pop(0)
            self._views.append(view)
        return view

    def get_view(self, view_id: str) -> PreviewView:
        for v in self._views:
            if v.view_id == view_id:
                return v
        raise PreviewViewError("NOT_FOUND", f"view {view_id} not found")

    def list_views(
        self,
        dataset_rid: Optional[str] = None,
        view_type: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> list[PreviewView]:
        items = list(self._views)
        if dataset_rid is not None:
            items = [v for v in items if v.dataset_rid == dataset_rid]
        if view_type is not None:
            items = [v for v in items if v.view_type == view_type]
        if enabled is not None:
            items = [v for v in items if v.enabled == enabled]
        return items

    def update_view(self, view_id: str, updates: dict[str, Any]) -> PreviewView:
        view = self.get_view(view_id)
        if "view_type" in updates and updates["view_type"] not in _VALID_VIEW_TYPES:
            raise PreviewViewError("INVALID_VIEW_TYPE", f"view_type must be one of {_VALID_VIEW_TYPES}")
        for k, v in updates.items():
            if hasattr(view, k) and k != "view_id":
                setattr(view, k, v)
        view.updated_at = time.time()
        return view

    def delete_view(self, view_id: str) -> bool:
        for i, v in enumerate(self._views):
            if v.view_id == view_id:
                with self._lock:
                    if i < len(self._views) and self._views[i].view_id == view_id:
                        self._views.pop(i)
                        return True
                return True
        return False


# ════════════════════ Engine 3: DataHealthCheckEngine ════════════════════

class DataHealthCheckEngine:
    _instance: Optional[DataHealthCheckEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._checks: list[DataHealthCheck] = []
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> DataHealthCheckEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_check(self, check: DataHealthCheck) -> DataHealthCheck:
        if not check.dataset_rid:
            raise DataHealthCheckError("MISSING_DATASET", "dataset_rid is required")
        if check.check_type not in _VALID_CHECK_TYPES:
            raise DataHealthCheckError("INVALID_CHECK_TYPE", f"check_type must be one of {_VALID_CHECK_TYPES}")
        if check.status not in _VALID_STATUSES:
            raise DataHealthCheckError("INVALID_STATUS", f"status must be one of {_VALID_STATUSES}")
        if check.severity not in _VALID_SEVERITIES:
            raise DataHealthCheckError("INVALID_SEVERITY", f"severity must be one of {_VALID_SEVERITIES}")
        with self._lock:
            if len(self._checks) >= _MAX_CHECKS:
                self._checks.pop(0)
            self._checks.append(check)
        return check

    def get_check(self, check_id: str) -> DataHealthCheck:
        for c in self._checks:
            if c.check_id == check_id:
                return c
        raise DataHealthCheckError("NOT_FOUND", f"check {check_id} not found")

    def list_checks(
        self,
        dataset_rid: Optional[str] = None,
        check_type: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> list[DataHealthCheck]:
        items = list(self._checks)
        if dataset_rid is not None:
            items = [c for c in items if c.dataset_rid == dataset_rid]
        if check_type is not None:
            items = [c for c in items if c.check_type == check_type]
        if status is not None:
            items = [c for c in items if c.status == status]
        if severity is not None:
            items = [c for c in items if c.severity == severity]
        return items

    def update_check(self, check_id: str, updates: dict[str, Any]) -> DataHealthCheck:
        check = self.get_check(check_id)
        if "check_type" in updates and updates["check_type"] not in _VALID_CHECK_TYPES:
            raise DataHealthCheckError("INVALID_CHECK_TYPE", f"check_type must be one of {_VALID_CHECK_TYPES}")
        if "status" in updates and updates["status"] not in _VALID_STATUSES:
            raise DataHealthCheckError("INVALID_STATUS", f"status must be one of {_VALID_STATUSES}")
        if "severity" in updates and updates["severity"] not in _VALID_SEVERITIES:
            raise DataHealthCheckError("INVALID_SEVERITY", f"severity must be one of {_VALID_SEVERITIES}")
        for k, v in updates.items():
            if hasattr(check, k) and k != "check_id":
                setattr(check, k, v)
        check.updated_at = time.time()
        return check

    def delete_check(self, check_id: str) -> bool:
        for i, c in enumerate(self._checks):
            if c.check_id == check_id:
                with self._lock:
                    if i < len(self._checks) and self._checks[i].check_id == check_id:
                        self._checks.pop(i)
                        return True
                return True
        return False

    def run_check(self, check_id: str) -> DataHealthCheck:
        check = self.get_check(check_id)
        now = time.time()
        check.last_run_at = now
        check.status = "passed"
        check.last_result = {"status": "passed", "executed_at": now}
        check.updated_at = now
        return check
