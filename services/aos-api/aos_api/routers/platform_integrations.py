"""W2-AV · Platform Integrations 路由（#142 / #159 / #160）."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.platform_integrations import (
    FerryPackage,
    FerryPackageError,
    FunctionIntegration,
    FunctionIntegrationError,
    HealthAppEntry,
    HealthAppError,
    get_ferry_package_engine,
    get_function_integration_engine,
    get_health_app_engine,
)

router = APIRouter(
    prefix="/platform-integrations", tags=["Platform Integrations"]
)


def _map_health_err(e: HealthAppError) -> HTTPException:
    mapping = {
        "MISSING_APP_NAME": (400, "缺少 app_name"),
        "MISSING_PATH": (400, "缺少 path"),
        "INVALID_CATEGORY": (400, "category 无效"),
        "INVALID_STATUS": (400, "status 无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_func_int_err(e: FunctionIntegrationError) -> HTTPException:
    mapping = {
        "MISSING_MODULE": (400, "缺少 module_id"),
        "MISSING_FUNCTION": (400, "缺少 function_id"),
        "MISSING_BACKEND_TYPE": (400, "缺少 backend_type"),
        "INVALID_BACKEND_TYPE": (400, "backend_type 无效"),
        "INVALID_TRIGGER_TYPE": (400, "trigger_type 无效"),
        "INVALID_STATUS": (400, "status 无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_ferry_err(e: FerryPackageError) -> HTTPException:
    mapping = {
        "MISSING_SOURCE": (400, "缺少 source_dataset_rid"),
        "MISSING_TARGET": (400, "缺少 target_dataset_rid"),
        "INVALID_PACKAGE_TYPE": (400, "package_type 无效"),
        "INVALID_STATUS": (400, "status 无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


# ════════════════════ #142 Health App Entries ════════════════════

@router.post("/health-app-entries", response_model=HealthAppEntry)
def register_health_app_entry(
    body: HealthAppEntry,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_health_app_engine().register_entry(body)
    except HealthAppError as e:
        raise _map_health_err(e) from e


@router.get("/health-app-entries", response_model=list[HealthAppEntry])
def list_health_app_entries(
    category: str | None = None,
    status: str | None = None,
    principal: Principal = Depends(require_principal),
):
    return get_health_app_engine().list_entries(
        category=category, status=status
    )


# 静态路径须注册在参数路由 /health-app-entries/{entry_id} 之前
@router.post("/health-app-entries/reorder", response_model=list[HealthAppEntry])
def reorder_health_app_entries(
    body: dict[str, int],
    principal: Principal = Depends(require_principal),
):
    return get_health_app_engine().reorder_entries(body)


@router.get("/health-app-entries/{entry_id}", response_model=HealthAppEntry)
def get_health_app_entry(
    entry_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_health_app_engine().get_entry(entry_id)
    except HealthAppError as e:
        raise _map_health_err(e) from e


@router.put("/health-app-entries/{entry_id}", response_model=HealthAppEntry)
def update_health_app_entry(
    entry_id: str,
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    try:
        return get_health_app_engine().update_entry(entry_id, body)
    except HealthAppError as e:
        raise _map_health_err(e) from e


@router.delete("/health-app-entries/{entry_id}")
def delete_health_app_entry(
    entry_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_health_app_engine().delete_entry(entry_id)
        return {"deleted": True}
    except HealthAppError as e:
        raise _map_health_err(e) from e


@router.get("/sidebar-items", response_model=list[HealthAppEntry])
def get_sidebar_items(
    principal: Principal = Depends(require_principal),
):
    return get_health_app_engine().get_sidebar_items()


# ════════════════════ #159 Function Integrations ════════════════════

@router.post("/function-integrations", response_model=FunctionIntegration)
def register_function_integration(
    body: FunctionIntegration,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_function_integration_engine().register_integration(body)
    except FunctionIntegrationError as e:
        raise _map_func_int_err(e) from e


@router.get("/function-integrations", response_model=list[FunctionIntegration])
def list_function_integrations(
    module_id: str | None = None,
    backend_type: str | None = None,
    trigger_type: str | None = None,
    status: str | None = None,
    principal: Principal = Depends(require_principal),
):
    return get_function_integration_engine().list_integrations(
        module_id=module_id,
        backend_type=backend_type,
        trigger_type=trigger_type,
        status=status,
    )


# 静态路径须注册在参数路由 /function-integrations/{integration_id} 之前
@router.get("/function-integrations/by-function", response_model=list[FunctionIntegration])
def list_function_integrations_by_function(
    function_id: str,
    principal: Principal = Depends(require_principal),
):
    return get_function_integration_engine().list_by_function(function_id)


@router.get("/function-integrations/{integration_id}", response_model=FunctionIntegration)
def get_function_integration(
    integration_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_function_integration_engine().get_integration(integration_id)
    except FunctionIntegrationError as e:
        raise _map_func_int_err(e) from e


@router.put("/function-integrations/{integration_id}", response_model=FunctionIntegration)
def update_function_integration(
    integration_id: str,
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    try:
        return get_function_integration_engine().update_integration(
            integration_id, body
        )
    except FunctionIntegrationError as e:
        raise _map_func_int_err(e) from e


@router.delete("/function-integrations/{integration_id}")
def delete_function_integration(
    integration_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_function_integration_engine().delete_integration(integration_id)
        return {"deleted": True}
    except FunctionIntegrationError as e:
        raise _map_func_int_err(e) from e


@router.post("/function-integrations/{integration_id}/invoke")
def invoke_function_integration(
    integration_id: str,
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_function_integration_engine().invoke(
            integration_id, body
        )
    except FunctionIntegrationError as e:
        raise _map_func_int_err(e) from e


# ════════════════════ #160 Ferry Packages ════════════════════

@router.post("/ferry-packages", response_model=FerryPackage)
def create_ferry_package(
    body: FerryPackage,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ferry_package_engine().create_package(body)
    except FerryPackageError as e:
        raise _map_ferry_err(e) from e


@router.get("/ferry-packages", response_model=list[FerryPackage])
def list_ferry_packages(
    source_dataset_rid: str | None = None,
    target_dataset_rid: str | None = None,
    package_type: str | None = None,
    status: str | None = None,
    principal: Principal = Depends(require_principal),
):
    return get_ferry_package_engine().list_packages(
        source_dataset_rid=source_dataset_rid,
        target_dataset_rid=target_dataset_rid,
        package_type=package_type,
        status=status,
    )


@router.get("/ferry-packages/{package_id}", response_model=FerryPackage)
def get_ferry_package(
    package_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ferry_package_engine().get_package(package_id)
    except FerryPackageError as e:
        raise _map_ferry_err(e) from e


@router.put("/ferry-packages/{package_id}", response_model=FerryPackage)
def update_ferry_package(
    package_id: str,
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ferry_package_engine().update_package(package_id, body)
    except FerryPackageError as e:
        raise _map_ferry_err(e) from e


@router.delete("/ferry-packages/{package_id}")
def delete_ferry_package(
    package_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_ferry_package_engine().delete_package(package_id)
        return {"deleted": True}
    except FerryPackageError as e:
        raise _map_ferry_err(e) from e


@router.post("/ferry-packages/{package_id}/build", response_model=FerryPackage)
def build_ferry_package(
    package_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ferry_package_engine().build_package(package_id)
    except FerryPackageError as e:
        raise _map_ferry_err(e) from e


@router.post("/ferry-packages/{package_id}/fail", response_model=FerryPackage)
def fail_ferry_package(
    package_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ferry_package_engine().fail_package(package_id)
    except FerryPackageError as e:
        raise _map_ferry_err(e) from e


@router.post("/ferry-packages/{package_id}/apply")
def apply_ferry_package(
    package_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ferry_package_engine().apply_package(package_id)
    except FerryPackageError as e:
        raise _map_ferry_err(e) from e
