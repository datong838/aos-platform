"""W2-BI · CSV / Ontology 导出 / 用量 / Action 指标路由（W2+ 低优先级 #1 #2 #3 #4）."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.csv_ontology_export_action_metrics import (
    ActionMetric,
    ActionMetricSummary,
    CsvParseConfig,
    CsvParseResult,
    ExchangeMetricsError,
    OntologyExportPackage,
    OntologyImportResult,
    UsageRecord,
    UsageSummary,
    get_action_metrics_engine,
    get_csv_parsing_engine,
    get_ontology_exchange_engine,
    get_ontology_usage_engine,
)
from aos_api.errors import error_payload

router = APIRouter(
    prefix="/csv-ontology-export-action-metrics",
    tags=["csv-ontology-export-action-metrics"],
)


def _map_err(e: ExchangeMetricsError) -> HTTPException:
    if e.code == "NOT_FOUND":
        status = 404
    elif e.code.startswith("INVALID_"):
        status = 400
    else:
        status = 500
    return HTTPException(
        status_code=status,
        detail=error_payload(code=e.code, message=e.message),
    )


# ════════════════════ 请求体模型 ════════════════════

class CsvParseRequest(BaseModel):
    content: str
    config: CsvParseConfig | None = None
    parser_type: str = "dict_reader"


class OntologyExportRequest(BaseModel):
    source_ontology_id: str
    object_types: list[dict[str, Any]] | None = None
    link_types: list[dict[str, Any]] | None = None
    properties: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None


class OntologyImportRequest(BaseModel):
    export_id: str
    target_ontology_id: str
    overwrite: bool = False


class UsageRecordRequest(BaseModel):
    ontology_id: str
    resource_type: str
    amount: float
    description: str = ""


class ActionMetricRequest(BaseModel):
    action_id: str
    status: str
    duration_ms: float = 0
    error_code: str = ""
    metadata: dict[str, Any] | None = None


# ════════════════════ #1 CSV 解析 ════════════════════

@router.post("/csv/parse", response_model=CsvParseResult)
def parse_csv(req: CsvParseRequest, _=require_principal):
    try:
        return get_csv_parsing_engine().parse(req.content, req.config, req.parser_type)
    except ExchangeMetricsError as e:
        raise _map_err(e) from e


@router.get("/csv/results/{result_id}", response_model=CsvParseResult)
def get_csv_result(result_id: str, _=require_principal):
    try:
        return get_csv_parsing_engine().get_result(result_id)
    except ExchangeMetricsError as e:
        raise _map_err(e) from e


@router.get("/csv/results", response_model=list[CsvParseResult])
def list_csv_results(parser_type: str | None = None, _=require_principal):
    return get_csv_parsing_engine().list_results(parser_type=parser_type)


@router.delete("/csv/results/{result_id}")
def delete_csv_result(result_id: str, _=require_principal):
    return {"deleted": get_csv_parsing_engine().delete_result(result_id)}


# ════════════════════ #2 Ontology 导出/导入 ════════════════════

@router.post("/ontology-exchange/export", response_model=OntologyExportPackage)
def export_ontology(req: OntologyExportRequest, _=require_principal):
    try:
        return get_ontology_exchange_engine().export_ontology(
            source_ontology_id=req.source_ontology_id,
            object_types=req.object_types,
            link_types=req.link_types,
            properties=req.properties,
            metadata=req.metadata,
        )
    except ExchangeMetricsError as e:
        raise _map_err(e) from e


@router.get("/ontology-exchange/exports/{export_id}", response_model=OntologyExportPackage)
def get_ontology_export(export_id: str, _=require_principal):
    try:
        return get_ontology_exchange_engine().get_export(export_id)
    except ExchangeMetricsError as e:
        raise _map_err(e) from e


@router.get("/ontology-exchange/exports", response_model=list[OntologyExportPackage])
def list_ontology_exports(source_ontology_id: str | None = None, _=require_principal):
    return get_ontology_exchange_engine().list_exports(source_ontology_id=source_ontology_id)


@router.delete("/ontology-exchange/exports/{export_id}")
def delete_ontology_export(export_id: str, _=require_principal):
    return {"deleted": get_ontology_exchange_engine().delete_export(export_id)}


@router.post("/ontology-exchange/import", response_model=OntologyImportResult)
def import_ontology(req: OntologyImportRequest, _=require_principal):
    try:
        engine = get_ontology_exchange_engine()
        export_package = engine.get_export(req.export_id)
        return engine.import_ontology(export_package, req.target_ontology_id, req.overwrite)
    except ExchangeMetricsError as e:
        raise _map_err(e) from e


@router.get("/ontology-exchange/imports/{import_id}", response_model=OntologyImportResult)
def get_ontology_import(import_id: str, _=require_principal):
    try:
        return get_ontology_exchange_engine().get_import(import_id)
    except ExchangeMetricsError as e:
        raise _map_err(e) from e


@router.get("/ontology-exchange/imports", response_model=list[OntologyImportResult])
def list_ontology_imports(target_ontology_id: str | None = None, _=require_principal):
    return get_ontology_exchange_engine().list_imports(target_ontology_id=target_ontology_id)


@router.delete("/ontology-exchange/imports/{import_id}")
def delete_ontology_import(import_id: str, _=require_principal):
    return {"deleted": get_ontology_exchange_engine().delete_import(import_id)}


# ════════════════════ #3 Ontology 用量 ════════════════════

@router.post("/ontology-usage/record", response_model=UsageRecord)
def record_usage(req: UsageRecordRequest, _=require_principal):
    try:
        return get_ontology_usage_engine().record_usage(
            req.ontology_id, req.resource_type, req.amount, req.description
        )
    except ExchangeMetricsError as e:
        raise _map_err(e) from e


@router.get("/ontology-usage/summary/{ontology_id}", response_model=UsageSummary)
def get_usage_summary(ontology_id: str, _=require_principal):
    return get_ontology_usage_engine().get_summary(ontology_id)


@router.get("/ontology-usage/{usage_id}", response_model=UsageRecord)
def get_usage(usage_id: str, _=require_principal):
    try:
        return get_ontology_usage_engine().get_usage(usage_id)
    except ExchangeMetricsError as e:
        raise _map_err(e) from e


@router.get("/ontology-usage", response_model=list[UsageRecord])
def list_usage(
    ontology_id: str | None = None,
    resource_type: str | None = None,
    _=require_principal,
):
    return get_ontology_usage_engine().list_usage(
        ontology_id=ontology_id, resource_type=resource_type
    )


@router.delete("/ontology-usage/{usage_id}")
def delete_usage(usage_id: str, _=require_principal):
    return {"deleted": get_ontology_usage_engine().delete_usage(usage_id)}


# ════════════════════ #4 Action 指标 ════════════════════

@router.post("/action-metrics/record", response_model=ActionMetric)
def record_metric(req: ActionMetricRequest, _=require_principal):
    try:
        return get_action_metrics_engine().record_metric(
            req.action_id,
            req.status,
            req.duration_ms,
            req.error_code,
            req.metadata,
        )
    except ExchangeMetricsError as e:
        raise _map_err(e) from e


@router.get("/action-metrics/summary/{action_id}", response_model=ActionMetricSummary)
def get_metric_summary(action_id: str, days: int = Query(30, ge=1), _=require_principal):
    return get_action_metrics_engine().get_summary(action_id, days=days)


@router.get("/action-metrics/dashboard", response_model=list[ActionMetricSummary])
def get_metrics_dashboard(days: int = Query(30, ge=1), _=require_principal):
    return get_action_metrics_engine().get_dashboard(days=days)


@router.get("/action-metrics/{metric_id}", response_model=ActionMetric)
def get_metric(metric_id: str, _=require_principal):
    try:
        return get_action_metrics_engine().get_metric(metric_id)
    except ExchangeMetricsError as e:
        raise _map_err(e) from e


@router.get("/action-metrics", response_model=list[ActionMetric])
def list_metrics(
    action_id: str | None = None,
    status: str | None = None,
    days: int = Query(30, ge=1),
    _=require_principal,
):
    return get_action_metrics_engine().list_metrics(
        action_id=action_id, status=status, days=days
    )


@router.delete("/action-metrics/{metric_id}")
def delete_metric(metric_id: str, _=require_principal):
    return {"deleted": get_action_metrics_engine().delete_metric(metric_id)}
