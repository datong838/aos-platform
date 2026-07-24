"""W2-AM · Data Health Integration 路由（#139 #140 #141）."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.data_health_integration import (
    DatasetHealthTab,
    DatasetHealthTabError,
    HealthIssue,
    HealthIssuesIntegrationError,
    LineageColoringConfig,
    LineageHealthColor,
    LineageHealthColoringError,
    get_dataset_health_tab_engine,
    get_health_issues_integration_engine,
    get_lineage_health_coloring_engine,
)
from aos_api.errors import ApiError

router = APIRouter(prefix="/health-integration", tags=["Data Health Integration"])


def _map_issues_err(e: HealthIssuesIntegrationError) -> HTTPException:
    mapping = {
        "MISSING_DATASET": (400, "缺少 dataset_rid"),
        "MISSING_CHECK": (400, "缺少 check_id"),
        "INVALID_SEVERITY": (400, "严重级无效"),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(status_code=status, detail=ApiError(code=e.code, message=msg).model_dump())


def _map_tab_err(e: DatasetHealthTabError) -> HTTPException:
    mapping = {
        "MISSING_DATASET": (400, "缺少 dataset_rid"),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(status_code=status, detail=ApiError(code=e.code, message=msg).model_dump())


def _map_coloring_err(e: LineageHealthColoringError) -> HTTPException:
    mapping = {
        "MISSING_DATASET": (400, "缺少 dataset_rid"),
        "MISSING_NAME": (400, "缺少配置名称"),
        "INVALID_HEALTH_STATUS": (400, "健康状态无效"),
        "INVALID_COLOR_CODE": (400, "颜色代码无效"),
        "INVALID_COLOR_SCHEME": (400, "颜色方案无效"),
        "NOT_FOUND": (404, "资源不存在"),
        "CONFIG_NOT_FOUND": (404, "配置不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(status_code=status, detail=ApiError(code=e.code, message=msg).model_dump())


# ════════════════════ #139 Health Issues Integration ════════════════════

class CreateIssueBody(BaseModel):
    dataset_rid: str
    check_id: str
    check_name: str
    severity: str
    title: str
    description: str


@router.post("/issues", response_model=HealthIssue)
def create_issue(body: CreateIssueBody, _=require_principal):
    try:
        return get_health_issues_integration_engine().create_issue(
            dataset_rid=body.dataset_rid,
            check_id=body.check_id,
            check_name=body.check_name,
            severity=body.severity,
            title=body.title,
            description=body.description,
        )
    except HealthIssuesIntegrationError as e:
        raise _map_issues_err(e) from e


@router.get("/issues/{issue_id}", response_model=HealthIssue)
def get_issue(issue_id: str, _=require_principal):
    try:
        return get_health_issues_integration_engine().get_issue(issue_id)
    except HealthIssuesIntegrationError as e:
        raise _map_issues_err(e) from e


@router.get("/issues", response_model=list[HealthIssue])
def list_issues(
    dataset_rid: str | None = Query(None),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _=require_principal,
):
    try:
        return get_health_issues_integration_engine().list_issues(
            dataset_rid=dataset_rid,
            status=status,
            severity=severity,
            limit=limit,
        )
    except HealthIssuesIntegrationError as e:
        raise _map_issues_err(e) from e


@router.put("/issues/{issue_id}", response_model=HealthIssue)
def update_issue(issue_id: str, updates: dict, _=require_principal):
    try:
        return get_health_issues_integration_engine().update_issue(issue_id, updates)
    except HealthIssuesIntegrationError as e:
        raise _map_issues_err(e) from e


@router.post("/issues/{issue_id}/resolve", response_model=HealthIssue)
def resolve_issue(issue_id: str, _=require_principal):
    try:
        return get_health_issues_integration_engine().resolve_issue(issue_id)
    except HealthIssuesIntegrationError as e:
        raise _map_issues_err(e) from e


@router.post("/issues/{issue_id}/close", response_model=HealthIssue)
def close_issue(issue_id: str, _=require_principal):
    try:
        return get_health_issues_integration_engine().close_issue(issue_id)
    except HealthIssuesIntegrationError as e:
        raise _map_issues_err(e) from e


class AutoCreateIssueBody(BaseModel):
    dataset_rid: str
    check_id: str
    check_name: str
    severity: str
    failure_message: str


@router.post("/issues/auto-create", response_model=HealthIssue)
def auto_create_issue(body: AutoCreateIssueBody, _=require_principal):
    try:
        return get_health_issues_integration_engine().auto_create_from_check(
            dataset_rid=body.dataset_rid,
            check_id=body.check_id,
            check_name=body.check_name,
            severity=body.severity,
            failure_message=body.failure_message,
        )
    except HealthIssuesIntegrationError as e:
        raise _map_issues_err(e) from e


class AutoResolveIssueBody(BaseModel):
    dataset_rid: str
    check_id: str


@router.post("/issues/auto-resolve")
def auto_resolve_issue(body: AutoResolveIssueBody, _=require_principal):
    try:
        result = get_health_issues_integration_engine().auto_resolve_from_check(
            dataset_rid=body.dataset_rid,
            check_id=body.check_id,
        )
        if result is None:
            return {"resolved": False, "issue": None}
        return {"resolved": True, "issue": result}
    except HealthIssuesIntegrationError as e:
        raise _map_issues_err(e) from e


# ════════════════════ #140 Dataset Health Tab ════════════════════

class RegisterTabBody(BaseModel):
    dataset_rid: str


@router.post("/tabs", response_model=DatasetHealthTab)
def register_tab(body: RegisterTabBody, _=require_principal):
    try:
        return get_dataset_health_tab_engine().register(body.dataset_rid)
    except DatasetHealthTabError as e:
        raise _map_tab_err(e) from e


@router.get("/tabs/{tab_id}", response_model=DatasetHealthTab)
def get_tab(tab_id: str, _=require_principal):
    try:
        return get_dataset_health_tab_engine().get(tab_id)
    except DatasetHealthTabError as e:
        raise _map_tab_err(e) from e


@router.get("/tabs/dataset/{dataset_rid}", response_model=DatasetHealthTab)
def get_tab_by_dataset(dataset_rid: str, _=require_principal):
    try:
        return get_dataset_health_tab_engine().get_by_dataset(dataset_rid)
    except DatasetHealthTabError as e:
        raise _map_tab_err(e) from e


@router.get("/tabs", response_model=list[DatasetHealthTab])
def list_tabs(
    dataset_rid: str | None = Query(None),
    _=require_principal,
):
    return get_dataset_health_tab_engine().list(dataset_rid=dataset_rid)


class UpdateTabStatusBody(BaseModel):
    overall_status: str
    checks_summary: dict


@router.post("/tabs/{tab_id}/status", response_model=DatasetHealthTab)
def update_tab_status(tab_id: str, body: UpdateTabStatusBody, _=require_principal):
    try:
        engine = get_dataset_health_tab_engine()
        tab = engine.get(tab_id)
        return engine.update_status(
            dataset_rid=tab.dataset_rid,
            overall_status=body.overall_status,
            checks_summary=body.checks_summary,
        )
    except DatasetHealthTabError as e:
        raise _map_tab_err(e) from e


class AddRecommendationBody(BaseModel):
    recommendation: str


@router.post("/tabs/{tab_id}/recommendations", response_model=DatasetHealthTab)
def add_tab_recommendation(tab_id: str, body: AddRecommendationBody, _=require_principal):
    try:
        engine = get_dataset_health_tab_engine()
        tab = engine.get(tab_id)
        return engine.add_recommendation(
            dataset_rid=tab.dataset_rid,
            recommendation=body.recommendation,
        )
    except DatasetHealthTabError as e:
        raise _map_tab_err(e) from e


class AddTrendBody(BaseModel):
    date: str
    status: str
    pass_rate: float


@router.post("/tabs/{tab_id}/trends", response_model=DatasetHealthTab)
def add_tab_trend(tab_id: str, body: AddTrendBody, _=require_principal):
    try:
        engine = get_dataset_health_tab_engine()
        tab = engine.get(tab_id)
        return engine.add_trend(
            dataset_rid=tab.dataset_rid,
            date_str=body.date,
            status=body.status,
            pass_rate=body.pass_rate,
        )
    except DatasetHealthTabError as e:
        raise _map_tab_err(e) from e


@router.delete("/tabs/{tab_id}")
def delete_tab(tab_id: str, _=require_principal):
    try:
        get_dataset_health_tab_engine().delete(tab_id)
        return {"deleted": True}
    except DatasetHealthTabError as e:
        raise _map_tab_err(e) from e


# ════════════════════ #141 Lineage Health Coloring ════════════════════
# 注意：字面量路由（configs/apply）须注册在参数路由 {dataset_rid} 之前，
# 否则 GET /lineage-colors/configs 会被 {dataset_rid} 误匹配。

class RegisterColorBody(BaseModel):
    dataset_rid: str
    health_status: str
    color_code: str
    display_name: str
    tooltip: str


@router.post("/lineage-colors", response_model=LineageHealthColor)
def register_color(body: RegisterColorBody, _=require_principal):
    try:
        return get_lineage_health_coloring_engine().register_color(
            dataset_rid=body.dataset_rid,
            health_status=body.health_status,
            color_code=body.color_code,
            display_name=body.display_name,
            tooltip=body.tooltip,
        )
    except LineageHealthColoringError as e:
        raise _map_coloring_err(e) from e


@router.get("/lineage-colors", response_model=list[LineageHealthColor])
def list_colors(
    status_filter: str | None = Query(None),
    _=require_principal,
):
    try:
        return get_lineage_health_coloring_engine().list_colors(status_filter=status_filter)
    except LineageHealthColoringError as e:
        raise _map_coloring_err(e) from e


@router.post("/lineage-colors/configs", response_model=LineageColoringConfig)
def register_config(config: LineageColoringConfig, _=require_principal):
    try:
        return get_lineage_health_coloring_engine().register_config(config)
    except LineageHealthColoringError as e:
        raise _map_coloring_err(e) from e


@router.get("/lineage-colors/configs", response_model=list[LineageColoringConfig])
def list_configs(_=require_principal):
    return get_lineage_health_coloring_engine().list_configs()


@router.get("/lineage-colors/configs/{config_id}", response_model=LineageColoringConfig)
def get_config(config_id: str, _=require_principal):
    try:
        return get_lineage_health_coloring_engine().get_config(config_id)
    except LineageHealthColoringError as e:
        raise _map_coloring_err(e) from e


class ApplyColoringBody(BaseModel):
    dataset_rids: list[str]
    config_id: str


@router.post("/lineage-colors/apply", response_model=list[LineageHealthColor])
def apply_coloring(body: ApplyColoringBody, _=require_principal):
    try:
        return get_lineage_health_coloring_engine().apply_coloring(
            dataset_rids=body.dataset_rids,
            config_id=body.config_id,
        )
    except LineageHealthColoringError as e:
        raise _map_coloring_err(e) from e


@router.get("/lineage-colors/{dataset_rid}", response_model=LineageHealthColor)
def get_color(dataset_rid: str, _=require_principal):
    try:
        return get_lineage_health_coloring_engine().get_color(dataset_rid)
    except LineageHealthColoringError as e:
        raise _map_coloring_err(e) from e


@router.put("/lineage-colors/{dataset_rid}", response_model=LineageHealthColor)
def update_color(dataset_rid: str, updates: dict, _=require_principal):
    try:
        return get_lineage_health_coloring_engine().update_color(dataset_rid, updates)
    except LineageHealthColoringError as e:
        raise _map_coloring_err(e) from e


@router.delete("/lineage-colors/{dataset_rid}")
def delete_color(dataset_rid: str, _=require_principal):
    try:
        get_lineage_health_coloring_engine().delete_color(dataset_rid)
        return {"deleted": True}
    except LineageHealthColoringError as e:
        raise _map_coloring_err(e) from e
