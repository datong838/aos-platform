"""W2-BL · Linter Foundry Rules 路由（#14 #15 #16/#28 #17）."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.linter_foundry_rules import (
    FoundryRule,
    FoundryRuleExecution,
    LintFinding,
    LintFixProposal,
    LinterFoundryError,
    LinterRule,
    ScanRun,
    ScanSchedule,
    TimeSeriesDataPoint,
    TimeSeriesSync,
    get_foundry_rules_engine,
    get_foundry_time_series_engine,
    get_linter_rule_engine,
    get_linter_scan_schedule_engine,
)

router = APIRouter(
    prefix="/linter-foundry-rules",
    tags=["linter-foundry-rules"],
)


def _map_err(err: LinterFoundryError) -> HTTPException:
    code = getattr(err, "code", "") or ""
    if code == "NOT_FOUND":
        status = 404
    elif code.startswith("INVALID_"):
        status = 400
    else:
        status = 500
    payload = (
        err.error_payload()
        if hasattr(err, "error_payload")
        else {"code": code, "message": str(err)}
    )
    return HTTPException(status_code=status, detail=payload)


# ════════════════════ 请求体模型 ════════════════════

class CreateLinterRuleBody(BaseModel):
    code: str
    title: str
    description: str
    severity: str
    category: str
    pattern: str = ""
    suggestion: str = ""
    auto_fix: bool = False


class DetectBody(BaseModel):
    resource_type: str
    resource_id: str
    resource_data: dict[str, Any] = {}


class FixFindingBody(BaseModel):
    proposed_value: str
    description: str = ""


class CreateScanScheduleBody(BaseModel):
    name: str
    cron_expression: str
    resource_scope: str = "all"
    resource_filter: dict[str, Any] = {}
    rule_scope: str = "all"
    rule_filter: dict[str, Any] = {}


class CreateFoundryRuleBody(BaseModel):
    name: str
    description: str
    trigger_type: str
    conditions: list[dict[str, Any]] = []
    actions: list[str] = []
    workflow_id: str = ""


class ExecuteFoundryRuleBody(BaseModel):
    input_data: dict[str, Any] = {}


class CreateSyncBody(BaseModel):
    rule_id: str
    dataset_id: str
    sync_interval_seconds: int = 300


class RecordDatapointBody(BaseModel):
    value: float
    metadata: dict[str, Any] = {}


# ════════════════════ #14 Linter Rules ════════════════════

@router.post("/linter/rules", response_model=LinterRule)
def create_linter_rule(body: CreateLinterRuleBody, _=require_principal):
    try:
        return get_linter_rule_engine().register_rule(
            code=body.code,
            title=body.title,
            description=body.description,
            severity=body.severity,
            category=body.category,
            pattern=body.pattern,
            suggestion=body.suggestion,
            auto_fix=body.auto_fix,
        )
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get("/linter/rules/{rule_id}", response_model=LinterRule)
def get_linter_rule(rule_id: str, _=require_principal):
    try:
        return get_linter_rule_engine().get_rule(rule_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get("/linter/rules", response_model=list[LinterRule])
def list_linter_rules(
    category: str | None = Query(None),
    severity: str | None = Query(None),
    enabled_only: bool = False,
    _=require_principal,
):
    return get_linter_rule_engine().list_rules(
        category=category, severity=severity, enabled_only=enabled_only
    )


@router.put("/linter/rules/{rule_id}", response_model=LinterRule)
def update_linter_rule(
    rule_id: str, updates: dict[str, Any], _=require_principal
):
    try:
        return get_linter_rule_engine().update_rule(rule_id, updates)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.delete("/linter/rules/{rule_id}")
def delete_linter_rule(rule_id: str, _=require_principal):
    deleted = get_linter_rule_engine().delete_rule(rule_id)
    return {"deleted": deleted, "id": rule_id}


@router.post("/linter/detect", response_model=list[LintFinding])
def detect_lint(body: DetectBody, _=require_principal):
    return get_linter_rule_engine().detect(
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        resource_data=body.resource_data,
    )


@router.get("/linter/findings/{finding_id}", response_model=LintFinding)
def get_lint_finding(finding_id: str, _=require_principal):
    try:
        return get_linter_rule_engine().get_finding(finding_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get("/linter/findings", response_model=list[LintFinding])
def list_lint_findings(
    resource_type: str | None = Query(None),
    severity: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_linter_rule_engine().list_findings(
        resource_type=resource_type, severity=severity, status=status
    )


@router.post(
    "/linter/findings/{finding_id}/fix", response_model=LintFixProposal
)
def fix_lint_finding(
    finding_id: str, body: FixFindingBody, _=require_principal
):
    try:
        return get_linter_rule_engine().fix_finding(
            finding_id=finding_id,
            proposed_value=body.proposed_value,
            description=body.description,
        )
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.post(
    "/linter/findings/{finding_id}/ignore", response_model=LintFinding
)
def ignore_lint_finding(finding_id: str, _=require_principal):
    try:
        return get_linter_rule_engine().ignore_finding(finding_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get("/linter/fixes/{fix_id}", response_model=LintFixProposal)
def get_lint_fix(fix_id: str, _=require_principal):
    try:
        return get_linter_rule_engine().get_fix_proposal(fix_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.post("/linter/fixes/{fix_id}/apply", response_model=LintFixProposal)
def apply_lint_fix(fix_id: str, _=require_principal):
    try:
        return get_linter_rule_engine().apply_fix(fix_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.delete("/linter/findings/{finding_id}")
def delete_lint_finding(finding_id: str, _=require_principal):
    deleted = get_linter_rule_engine().delete_finding(finding_id)
    return {"deleted": deleted, "id": finding_id}


# ════════════════════ #15 Scan Schedule ════════════════════

@router.post("/scan/schedules", response_model=ScanSchedule)
def create_scan_schedule(body: CreateScanScheduleBody, _=require_principal):
    try:
        return get_linter_scan_schedule_engine().create_schedule(
            name=body.name,
            cron_expression=body.cron_expression,
            resource_scope=body.resource_scope,
            resource_filter=body.resource_filter,
            rule_scope=body.rule_scope,
            rule_filter=body.rule_filter,
        )
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get("/scan/schedules/{schedule_id}", response_model=ScanSchedule)
def get_scan_schedule(schedule_id: str, _=require_principal):
    try:
        return get_linter_scan_schedule_engine().get_schedule(schedule_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get("/scan/schedules", response_model=list[ScanSchedule])
def list_scan_schedules(
    enabled_only: bool = False, _=require_principal
):
    return get_linter_scan_schedule_engine().list_schedules(
        enabled_only=enabled_only
    )


@router.put("/scan/schedules/{schedule_id}", response_model=ScanSchedule)
def update_scan_schedule(
    schedule_id: str, updates: dict[str, Any], _=require_principal
):
    try:
        return get_linter_scan_schedule_engine().update_schedule(
            schedule_id, updates
        )
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.delete("/scan/schedules/{schedule_id}")
def delete_scan_schedule(schedule_id: str, _=require_principal):
    deleted = get_linter_scan_schedule_engine().delete_schedule(schedule_id)
    return {"deleted": deleted, "id": schedule_id}


@router.post("/scan/schedules/{schedule_id}/run", response_model=ScanRun)
def run_scan(schedule_id: str, _=require_principal):
    try:
        return get_linter_scan_schedule_engine().run_scan(schedule_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get("/scan/runs/{run_id}", response_model=ScanRun)
def get_scan_run(run_id: str, _=require_principal):
    try:
        return get_linter_scan_schedule_engine().get_run(run_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get("/scan/runs", response_model=list[ScanRun])
def list_scan_runs(
    schedule_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_linter_scan_schedule_engine().list_runs(
        schedule_id=schedule_id, status=status
    )


@router.delete("/scan/runs/{run_id}")
def delete_scan_run(run_id: str, _=require_principal):
    deleted = get_linter_scan_schedule_engine().delete_run(run_id)
    return {"deleted": deleted, "id": run_id}


# ════════════════════ #16/#28 Foundry Rules ════════════════════

@router.post("/foundry/rules", response_model=FoundryRule)
def create_foundry_rule(body: CreateFoundryRuleBody, _=require_principal):
    try:
        return get_foundry_rules_engine().create_rule(
            name=body.name,
            description=body.description,
            trigger_type=body.trigger_type,
            conditions=body.conditions,
            actions=body.actions,
            workflow_id=body.workflow_id,
        )
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get("/foundry/rules/{rule_id}", response_model=FoundryRule)
def get_foundry_rule(rule_id: str, _=require_principal):
    try:
        return get_foundry_rules_engine().get_rule(rule_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get("/foundry/rules", response_model=list[FoundryRule])
def list_foundry_rules(
    trigger_type: str | None = Query(None),
    enabled_only: bool = False,
    _=require_principal,
):
    return get_foundry_rules_engine().list_rules(
        trigger_type=trigger_type, enabled_only=enabled_only
    )


@router.put("/foundry/rules/{rule_id}", response_model=FoundryRule)
def update_foundry_rule(
    rule_id: str, updates: dict[str, Any], _=require_principal
):
    try:
        return get_foundry_rules_engine().update_rule(rule_id, updates)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.delete("/foundry/rules/{rule_id}")
def delete_foundry_rule(rule_id: str, _=require_principal):
    deleted = get_foundry_rules_engine().delete_rule(rule_id)
    return {"deleted": deleted, "id": rule_id}


@router.post(
    "/foundry/rules/{rule_id}/execute", response_model=FoundryRuleExecution
)
def execute_foundry_rule(
    rule_id: str,
    body: ExecuteFoundryRuleBody | None = None,
    _=require_principal,
):
    try:
        input_data = body.input_data if body is not None else None
        return get_foundry_rules_engine().execute_rule(rule_id, input_data)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get(
    "/foundry/executions/{execution_id}", response_model=FoundryRuleExecution
)
def get_foundry_execution(execution_id: str, _=require_principal):
    try:
        return get_foundry_rules_engine().get_execution(execution_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get(
    "/foundry/executions", response_model=list[FoundryRuleExecution]
)
def list_foundry_executions(
    rule_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_foundry_rules_engine().list_executions(
        rule_id=rule_id, status=status
    )


@router.delete("/foundry/executions/{execution_id}")
def delete_foundry_execution(execution_id: str, _=require_principal):
    deleted = get_foundry_rules_engine().delete_execution(execution_id)
    return {"deleted": deleted, "id": execution_id}


# ════════════════════ #17 Foundry Time Series ════════════════════

@router.post("/timeseries/syncs", response_model=TimeSeriesSync)
def create_ts_sync(body: CreateSyncBody, _=require_principal):
    return get_foundry_time_series_engine().register_sync(
        rule_id=body.rule_id,
        dataset_id=body.dataset_id,
        sync_interval_seconds=body.sync_interval_seconds,
    )


@router.get("/timeseries/syncs/{sync_id}", response_model=TimeSeriesSync)
def get_ts_sync(sync_id: str, _=require_principal):
    try:
        return get_foundry_time_series_engine().get_sync(sync_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get("/timeseries/syncs", response_model=list[TimeSeriesSync])
def list_ts_syncs(
    rule_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_foundry_time_series_engine().list_syncs(
        rule_id=rule_id, status=status
    )


@router.put("/timeseries/syncs/{sync_id}", response_model=TimeSeriesSync)
def update_ts_sync(
    sync_id: str, updates: dict[str, Any], _=require_principal
):
    try:
        return get_foundry_time_series_engine().update_sync(sync_id, updates)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.post(
    "/timeseries/syncs/{sync_id}/pause", response_model=TimeSeriesSync
)
def pause_ts_sync(sync_id: str, _=require_principal):
    try:
        return get_foundry_time_series_engine().pause_sync(sync_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.post(
    "/timeseries/syncs/{sync_id}/resume", response_model=TimeSeriesSync
)
def resume_ts_sync(sync_id: str, _=require_principal):
    try:
        return get_foundry_time_series_engine().resume_sync(sync_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.post(
    "/timeseries/syncs/{sync_id}/datapoints",
    response_model=TimeSeriesDataPoint,
)
def record_ts_datapoint(
    sync_id: str, body: RecordDatapointBody, _=require_principal
):
    try:
        return get_foundry_time_series_engine().record_datapoint(
            sync_id=sync_id,
            value=body.value,
            metadata=body.metadata,
        )
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get(
    "/timeseries/datapoints/{datapoint_id}",
    response_model=TimeSeriesDataPoint,
)
def get_ts_datapoint(datapoint_id: str, _=require_principal):
    try:
        return get_foundry_time_series_engine().get_datapoint(datapoint_id)
    except LinterFoundryError as e:
        raise _map_err(e) from e


@router.get(
    "/timeseries/datapoints", response_model=list[TimeSeriesDataPoint]
)
def list_ts_datapoints(
    sync_id: str | None = Query(None),
    limit: int = 100,
    _=require_principal,
):
    return get_foundry_time_series_engine().list_datapoints(
        sync_id=sync_id, limit=limit
    )


@router.delete("/timeseries/syncs/{sync_id}")
def delete_ts_sync(sync_id: str, _=require_principal):
    deleted = get_foundry_time_series_engine().delete_sync(sync_id)
    return {"deleted": deleted, "id": sync_id}


@router.delete("/timeseries/datapoints/{datapoint_id}")
def delete_ts_datapoint(datapoint_id: str, _=require_principal):
    deleted = get_foundry_time_series_engine().delete_datapoint(datapoint_id)
    return {"deleted": deleted, "id": datapoint_id}
