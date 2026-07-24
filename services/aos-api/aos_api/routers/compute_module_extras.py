"""W2-AT · Compute Module Extras 路由（#155 #156 #157）."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.compute_module_extras import (
    ColdStartAlert,
    ContainerConfigError,
    ContainerTabConfig,
    DevScaffoldError,
    GeneratedScaffold,
    ScaleToZeroError,
    ScaleToZeroPolicy,
    ScaffoldFile,
    ScaffoldTemplate,
    get_container_config_engine,
    get_dev_scaffold_engine,
    get_scale_to_zero_engine,
)
from aos_api.errors import ApiError

router = APIRouter(
    prefix="/compute-module-extras", tags=["Compute Module Extras"])


def _map_config_err(e: ContainerConfigError) -> HTTPException:
    mapping = {
        "MISSING_MODULE": (400, "缺少 module_id"),
        "MISSING_TAB_NAME": (400, "缺少 tab_name"),
        "INVALID_TAB_NAME": (400, "tab_name 无效"),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_scale_err(e: ScaleToZeroError) -> HTTPException:
    mapping = {
        "MISSING_MODULE": (400, "缺少 module_id"),
        "INVALID_IDLE_TIMEOUT": (400, "idle_timeout_seconds 无效"),
        "INVALID_MIN_REPLICAS": (400, "min_replicas 无效"),
        "INVALID_SCALE_UP_DELAY": (400, "scale_up_delay_seconds 无效"),
        "INVALID_STATUS": (400, "状态无效"),
        "INVALID_ALERT_TYPE": (400, "alert_type 无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_scaffold_err(e: DevScaffoldError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少 name"),
        "MISSING_MODULE": (400, "缺少 module_id"),
        "INVALID_LANGUAGE": (400, "language 无效"),
        "TEMPLATE_NOT_FOUND": (404, "模板不存在"),
        "SCAFFOLD_NOT_FOUND": (404, "脚手架不存在"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


# ════════════════════ #155 Container Config ════════════════════

@router.post("/tab-configs", response_model=ContainerTabConfig)
def register_tab_config(body: ContainerTabConfig, _=require_principal):
    try:
        return get_container_config_engine().register_config(body)
    except ContainerConfigError as e:
        raise _map_config_err(e) from e


@router.get("/tab-configs/module/{module_id}/overview")
def get_module_overview(module_id: str, _=require_principal):
    try:
        return get_container_config_engine().get_module_overview(module_id)
    except ContainerConfigError as e:
        raise _map_config_err(e) from e


@router.get("/tab-configs/{tab_config_id}", response_model=ContainerTabConfig)
def get_tab_config(tab_config_id: str, _=require_principal):
    try:
        return get_container_config_engine().get_config(tab_config_id)
    except ContainerConfigError as e:
        raise _map_config_err(e) from e


@router.get("/tab-configs", response_model=list[ContainerTabConfig])
def list_tab_configs(
    module_id: str | None = Query(None),
    tab: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_container_config_engine().list_configs(
        module_id=module_id, tab=tab, status=status)


@router.put("/tab-configs/{tab_config_id}", response_model=ContainerTabConfig)
def update_tab_config(tab_config_id: str, updates: dict, _=require_principal):
    try:
        return get_container_config_engine().update_config(
            tab_config_id, updates)
    except ContainerConfigError as e:
        raise _map_config_err(e) from e


@router.delete("/tab-configs/{tab_config_id}")
def delete_tab_config(tab_config_id: str, _=require_principal):
    try:
        get_container_config_engine().delete_config(tab_config_id)
        return {"deleted": True}
    except ContainerConfigError as e:
        raise _map_config_err(e) from e


# ════════════════════ #156 Scale To Zero ════════════════════

@router.post("/scale-to-zero-policies", response_model=ScaleToZeroPolicy)
def register_scale_to_zero_policy(body: ScaleToZeroPolicy, _=require_principal):
    try:
        return get_scale_to_zero_engine().register_policy(body)
    except ScaleToZeroError as e:
        raise _map_scale_err(e) from e


@router.get("/scale-to-zero-policies/{policy_id}",
            response_model=ScaleToZeroPolicy)
def get_scale_to_zero_policy(policy_id: str, _=require_principal):
    try:
        return get_scale_to_zero_engine().get_policy(policy_id)
    except ScaleToZeroError as e:
        raise _map_scale_err(e) from e


@router.get("/scale-to-zero-policies", response_model=list[ScaleToZeroPolicy])
def list_scale_to_zero_policies(
    module_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_scale_to_zero_engine().list_policies(
        module_id=module_id, status=status)


@router.put("/scale-to-zero-policies/{policy_id}",
            response_model=ScaleToZeroPolicy)
def update_scale_to_zero_policy(
    policy_id: str, updates: dict, _=require_principal
):
    try:
        return get_scale_to_zero_engine().update_policy(policy_id, updates)
    except ScaleToZeroError as e:
        raise _map_scale_err(e) from e


@router.delete("/scale-to-zero-policies/{policy_id}")
def delete_scale_to_zero_policy(policy_id: str, _=require_principal):
    try:
        get_scale_to_zero_engine().delete_policy(policy_id)
        return {"deleted": True}
    except ScaleToZeroError as e:
        raise _map_scale_err(e) from e


class TriggerAlertBody(BaseModel):
    alert_type: str
    wait_duration_ms: int
    severity: str


@router.post("/scale-to-zero-policies/{policy_id}/trigger-alert",
             response_model=ColdStartAlert)
def trigger_alert_for_policy(
    policy_id: str, body: TriggerAlertBody, _=require_principal
):
    try:
        policy = get_scale_to_zero_engine().get_policy(policy_id)
        return get_scale_to_zero_engine().trigger_alert(
            module_id=policy.module_id,
            alert_type=body.alert_type,
            wait_duration_ms=body.wait_duration_ms,
            severity=body.severity,
        )
    except ScaleToZeroError as e:
        raise _map_scale_err(e) from e


@router.get("/cold-start-alerts", response_model=list[ColdStartAlert])
def list_cold_start_alerts(
    module_id: str | None = Query(None),
    alert_type: str | None = Query(None),
    cleared: bool | None = Query(None),
    _=require_principal,
):
    return get_scale_to_zero_engine().list_alerts(
        module_id=module_id, alert_type=alert_type, cleared=cleared)


@router.post("/cold-start-alerts/{alert_id}/clear",
             response_model=ColdStartAlert)
def clear_cold_start_alert(alert_id: str, _=require_principal):
    try:
        return get_scale_to_zero_engine().clear_alert(alert_id)
    except ScaleToZeroError as e:
        raise _map_scale_err(e) from e


class SimulateColdStartBody(BaseModel):
    module_id: str


@router.post("/simulate-cold-start")
def simulate_cold_start(body: SimulateColdStartBody, _=require_principal):
    try:
        return get_scale_to_zero_engine().simulate_cold_start(body.module_id)
    except ScaleToZeroError as e:
        raise _map_scale_err(e) from e


# ════════════════════ #157 Dev Scaffold ════════════════════

@router.post("/scaffold-templates", response_model=ScaffoldTemplate)
def register_scaffold_template(body: ScaffoldTemplate, _=require_principal):
    try:
        return get_dev_scaffold_engine().register_template(body)
    except DevScaffoldError as e:
        raise _map_scaffold_err(e) from e


@router.get("/scaffold-templates/{template_id}", response_model=ScaffoldTemplate)
def get_scaffold_template(template_id: str, _=require_principal):
    try:
        return get_dev_scaffold_engine().get_template(template_id)
    except DevScaffoldError as e:
        raise _map_scaffold_err(e) from e


@router.get("/scaffold-templates", response_model=list[ScaffoldTemplate])
def list_scaffold_templates(
    language: str | None = Query(None),
    _=require_principal,
):
    return get_dev_scaffold_engine().list_templates(language=language)


@router.put("/scaffold-templates/{template_id}", response_model=ScaffoldTemplate)
def update_scaffold_template(
    template_id: str, updates: dict, _=require_principal
):
    try:
        return get_dev_scaffold_engine().update_template(template_id, updates)
    except DevScaffoldError as e:
        raise _map_scaffold_err(e) from e


@router.delete("/scaffold-templates/{template_id}")
def delete_scaffold_template(template_id: str, _=require_principal):
    try:
        get_dev_scaffold_engine().delete_template(template_id)
        return {"deleted": True}
    except DevScaffoldError as e:
        raise _map_scaffold_err(e) from e


class GenerateScaffoldBody(BaseModel):
    module_id: str
    variables: dict = {}


@router.post("/scaffold-templates/{template_id}/generate",
             response_model=GeneratedScaffold)
def generate_scaffold(template_id: str, body: GenerateScaffoldBody,
                      _=require_principal):
    try:
        return get_dev_scaffold_engine().generate_scaffold(
            module_id=body.module_id,
            template_id=template_id,
            variables=body.variables,
        )
    except DevScaffoldError as e:
        raise _map_scaffold_err(e) from e


@router.get("/generated-scaffolds/{scaffold_id}",
            response_model=GeneratedScaffold)
def get_generated_scaffold(scaffold_id: str, _=require_principal):
    try:
        return get_dev_scaffold_engine().get_scaffold(scaffold_id)
    except DevScaffoldError as e:
        raise _map_scaffold_err(e) from e


@router.get("/generated-scaffolds", response_model=list[GeneratedScaffold])
def list_generated_scaffolds(
    module_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_dev_scaffold_engine().list_scaffolds(
        module_id=module_id, status=status)


@router.post("/generated-scaffolds/{scaffold_id}/apply",
             response_model=GeneratedScaffold)
def apply_generated_scaffold(scaffold_id: str, _=require_principal):
    try:
        return get_dev_scaffold_engine().apply_scaffold(scaffold_id)
    except DevScaffoldError as e:
        raise _map_scaffold_err(e) from e
