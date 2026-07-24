"""W2-AX · Dataset Preview Health 路由（ColumnStats / PreviewViews / DataHealthCheck）."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from aos_api.auth import require_principal
from aos_api.dataset_preview_health import (
    ColumnStats,
    ColumnStatsEngine,
    ColumnStatsError,
    DataHealthCheck,
    DataHealthCheckEngine,
    DataHealthCheckError,
    PreviewView,
    DatasetPreviewViewsEngine,
    PreviewViewError,
)

router = APIRouter(prefix="/dataset-preview-health", tags=["dataset-preview-health"])


def _map_column_stats_err(err: ColumnStatsError) -> HTTPException:
    status = 404 if err.code == "NOT_FOUND" else 400
    return HTTPException(status_code=status, detail={"code": err.code, "message": err.message})


def _map_preview_view_err(err: PreviewViewError) -> HTTPException:
    status = 404 if err.code == "NOT_FOUND" else 400
    return HTTPException(status_code=status, detail={"code": err.code, "message": err.message})


def _map_health_check_err(err: DataHealthCheckError) -> HTTPException:
    status = 404 if err.code == "NOT_FOUND" else 400
    return HTTPException(status_code=status, detail={"code": err.code, "message": err.message})


# ════════════════════ ColumnStats ════════════════════

class ColumnStatsIn(BaseModel):
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


@router.post("/column-stats", response_model=ColumnStats)
def compute_column_stats(body: ColumnStatsIn, _=require_principal):
    try:
        stats = ColumnStats(**body.model_dump())
        return ColumnStatsEngine.get_instance().compute_stats(stats)
    except ColumnStatsError as e:
        raise _map_column_stats_err(e) from e


@router.get("/column-stats/{stats_id}", response_model=ColumnStats)
def get_column_stats(stats_id: str, _=require_principal):
    try:
        return ColumnStatsEngine.get_instance().get_stats(stats_id)
    except ColumnStatsError as e:
        raise _map_column_stats_err(e) from e


@router.get("/column-stats", response_model=list[ColumnStats])
def list_column_stats(
    dataset_rid: Optional[str] = Query(None),
    column_name: Optional[str] = Query(None),
    data_type: Optional[str] = Query(None),
    _=require_principal,
):
    return ColumnStatsEngine.get_instance().list_stats(
        dataset_rid=dataset_rid,
        column_name=column_name,
        data_type=data_type,
    )


@router.delete("/column-stats/{stats_id}")
def delete_column_stats(stats_id: str, _=require_principal):
    ok = ColumnStatsEngine.get_instance().delete_stats(stats_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"stats {stats_id} not found"})
    return {"deleted": True}


# ════════════════════ PreviewViews ════════════════════

class PreviewViewIn(BaseModel):
    dataset_rid: str
    view_type: str
    config_data: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class PreviewViewUpdateIn(BaseModel):
    view_type: Optional[str] = None
    config_data: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None


@router.post("/preview-views", response_model=PreviewView)
def register_preview_view(body: PreviewViewIn, _=require_principal):
    try:
        view = PreviewView(**body.model_dump())
        return DatasetPreviewViewsEngine.get_instance().register_view(view)
    except PreviewViewError as e:
        raise _map_preview_view_err(e) from e


@router.get("/preview-views/{view_id}", response_model=PreviewView)
def get_preview_view(view_id: str, _=require_principal):
    try:
        return DatasetPreviewViewsEngine.get_instance().get_view(view_id)
    except PreviewViewError as e:
        raise _map_preview_view_err(e) from e


@router.get("/preview-views", response_model=list[PreviewView])
def list_preview_views(
    dataset_rid: Optional[str] = Query(None),
    view_type: Optional[str] = Query(None),
    enabled: Optional[bool] = None,
    _=require_principal,
):
    return DatasetPreviewViewsEngine.get_instance().list_views(
        dataset_rid=dataset_rid,
        view_type=view_type,
        enabled=enabled,
    )


@router.put("/preview-views/{view_id}", response_model=PreviewView)
def update_preview_view(view_id: str, body: PreviewViewUpdateIn, _=require_principal):
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        return DatasetPreviewViewsEngine.get_instance().update_view(view_id, updates)
    except PreviewViewError as e:
        raise _map_preview_view_err(e) from e


@router.delete("/preview-views/{view_id}")
def delete_preview_view(view_id: str, _=require_principal):
    ok = DatasetPreviewViewsEngine.get_instance().delete_view(view_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"view {view_id} not found"})
    return {"deleted": True}


# ════════════════════ DataHealthCheck ════════════════════

class DataHealthCheckIn(BaseModel):
    dataset_rid: str
    check_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    severity: str = "warning"


class DataHealthCheckUpdateIn(BaseModel):
    check_type: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    severity: Optional[str] = None


@router.post("/health-checks", response_model=DataHealthCheck)
def register_health_check(body: DataHealthCheckIn, _=require_principal):
    try:
        check = DataHealthCheck(**body.model_dump())
        return DataHealthCheckEngine.get_instance().register_check(check)
    except DataHealthCheckError as e:
        raise _map_health_check_err(e) from e


@router.get("/health-checks/{check_id}", response_model=DataHealthCheck)
def get_health_check(check_id: str, _=require_principal):
    try:
        return DataHealthCheckEngine.get_instance().get_check(check_id)
    except DataHealthCheckError as e:
        raise _map_health_check_err(e) from e


@router.get("/health-checks", response_model=list[DataHealthCheck])
def list_health_checks(
    dataset_rid: Optional[str] = Query(None),
    check_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    _=require_principal,
):
    return DataHealthCheckEngine.get_instance().list_checks(
        dataset_rid=dataset_rid,
        check_type=check_type,
        status=status,
        severity=severity,
    )


@router.put("/health-checks/{check_id}", response_model=DataHealthCheck)
def update_health_check(check_id: str, body: DataHealthCheckUpdateIn, _=require_principal):
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        return DataHealthCheckEngine.get_instance().update_check(check_id, updates)
    except DataHealthCheckError as e:
        raise _map_health_check_err(e) from e


@router.delete("/health-checks/{check_id}")
def delete_health_check(check_id: str, _=require_principal):
    ok = DataHealthCheckEngine.get_instance().delete_check(check_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"check {check_id} not found"})
    return {"deleted": True}


@router.post("/health-checks/{check_id}/run", response_model=DataHealthCheck)
def run_health_check(check_id: str, _=require_principal):
    try:
        return DataHealthCheckEngine.get_instance().run_check(check_id)
    except DataHealthCheckError as e:
        raise _map_health_check_err(e) from e
