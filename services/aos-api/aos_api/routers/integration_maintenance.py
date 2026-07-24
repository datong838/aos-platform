"""W2-AR · Integration Maintenance 路由（#161 #162 #163）."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.integration_maintenance import (
    DataExpectation,
    DataIntegrationError,
    IntegrationFramework,
    InterfaceExtensionError,
    InterfaceLinkType,
    InterfaceMarketplaceListing,
    PipelineHealthCheck,
    PipelineMaintenanceError,
    StabilitySuggestion,
    get_data_integration_framework_engine,
    get_ontology_interface_extension_engine,
    get_pipeline_maintenance_engine,
)

router = APIRouter(prefix="/integration-maintenance", tags=["Integration Maintenance"])


def _map_integration_err(e: DataIntegrationError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少 name"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_maintenance_err(e: PipelineMaintenanceError) -> HTTPException:
    mapping = {
        "MISSING_PIPELINE": (400, "缺少 pipeline_id"),
        "MISSING_CHECK_TYPE": (400, "缺少 check_type"),
        "MISSING_SUGGESTION_TYPE": (400, "缺少 suggestion_type"),
        "INVALID_STATUS": (400, "status 无效"),
        "INVALID_SEVERITY": (400, "severity 无效"),
        "INVALID_PRIORITY": (400, "priority 无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_interface_ext_err(e: InterfaceExtensionError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少 name"),
        "MISSING_SOURCE_INTERFACE": (400, "缺少 source_interface_id"),
        "MISSING_TARGET_INTERFACE": (400, "缺少 target_interface_id"),
        "MISSING_INTERFACE": (400, "缺少 interface_id"),
        "MISSING_TITLE": (400, "缺少 title"),
        "INVALID_CARDINALITY": (400, "cardinality 无效"),
        "INVALID_STATUS": (400, "status 无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


# ════════════════════ #161 Data Integration Framework ════════════════════

@router.post("/frameworks", response_model=IntegrationFramework)
def register_framework(
    body: IntegrationFramework,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_data_integration_framework_engine().register(body)
    except DataIntegrationError as e:
        raise _map_integration_err(e) from e


@router.get("/frameworks", response_model=list[IntegrationFramework])
def list_frameworks(
    status: str | None = Query(None),
    principal: Principal = Depends(require_principal),
):
    return get_data_integration_framework_engine().list(status=status)


@router.get("/frameworks/{framework_id}", response_model=IntegrationFramework)
def get_framework(
    framework_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_data_integration_framework_engine().get(framework_id)
    except DataIntegrationError as e:
        raise _map_integration_err(e) from e


@router.put("/frameworks/{framework_id}", response_model=IntegrationFramework)
def update_framework(
    framework_id: str,
    fields: dict,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_data_integration_framework_engine().update(framework_id, fields)
    except DataIntegrationError as e:
        raise _map_integration_err(e) from e


@router.delete("/frameworks/{framework_id}")
def delete_framework(
    framework_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_data_integration_framework_engine().delete(framework_id)
        return {"deleted": True}
    except DataIntegrationError as e:
        raise _map_integration_err(e) from e


class ConnectionLinkBody(BaseModel):
    connection_id: str


@router.post("/frameworks/{framework_id}/link-connection", response_model=IntegrationFramework)
def link_connection(
    framework_id: str,
    body: ConnectionLinkBody,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_data_integration_framework_engine().link_connection(
            framework_id, body.connection_id)
    except DataIntegrationError as e:
        raise _map_integration_err(e) from e


class TransformLinkBody(BaseModel):
    transform_id: str


@router.post("/frameworks/{framework_id}/link-transform", response_model=IntegrationFramework)
def link_transform(
    framework_id: str,
    body: TransformLinkBody,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_data_integration_framework_engine().link_transform(
            framework_id, body.transform_id)
    except DataIntegrationError as e:
        raise _map_integration_err(e) from e


@router.get("/frameworks/{framework_id}/summary")
def get_framework_summary(
    framework_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_data_integration_framework_engine().get_summary(framework_id)
    except DataIntegrationError as e:
        raise _map_integration_err(e) from e


# ════════════════════ #162 Pipeline Maintenance ════════════════════
# 注意：字面量路由 /pipeline-checks/failing 须注册在参数路由
# /pipeline-checks/{check_id} 之前，避免被 {check_id} 误匹配。

# ── 健康检查 ──

@router.post("/pipeline-checks", response_model=PipelineHealthCheck)
def register_check(
    body: PipelineHealthCheck,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_pipeline_maintenance_engine().register_check(body)
    except PipelineMaintenanceError as e:
        raise _map_maintenance_err(e) from e


@router.get("/pipeline-checks", response_model=list[PipelineHealthCheck])
def list_checks(
    pipeline_id: str | None = Query(None),
    status: str | None = Query(None),
    principal: Principal = Depends(require_principal),
):
    return get_pipeline_maintenance_engine().list_checks(
        pipeline_id=pipeline_id, status=status)


@router.get("/pipeline-checks/failing", response_model=list[PipelineHealthCheck])
def list_failing_checks(
    pipeline_id: str | None = Query(None),
    principal: Principal = Depends(require_principal),
):
    return get_pipeline_maintenance_engine().list_failing_checks(pipeline_id=pipeline_id)


@router.put("/pipeline-checks/{check_id}", response_model=PipelineHealthCheck)
def update_check(
    check_id: str,
    fields: dict,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_pipeline_maintenance_engine().update_check(check_id, fields)
    except PipelineMaintenanceError as e:
        raise _map_maintenance_err(e) from e


@router.delete("/pipeline-checks/{check_id}")
def delete_check(
    check_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_pipeline_maintenance_engine().delete_check(check_id)
        return {"deleted": True}
    except PipelineMaintenanceError as e:
        raise _map_maintenance_err(e) from e


# ── 数据期望 ──

@router.post("/data-expectations", response_model=DataExpectation)
def register_expectation(
    body: DataExpectation,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_pipeline_maintenance_engine().register_expectation(body)
    except PipelineMaintenanceError as e:
        raise _map_maintenance_err(e) from e


@router.get("/data-expectations", response_model=list[DataExpectation])
def list_expectations(
    pipeline_id: str | None = Query(None),
    principal: Principal = Depends(require_principal),
):
    return get_pipeline_maintenance_engine().list_expectations(pipeline_id=pipeline_id)


@router.put("/data-expectations/{expectation_id}", response_model=DataExpectation)
def update_expectation(
    expectation_id: str,
    fields: dict,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_pipeline_maintenance_engine().update_expectation(expectation_id, fields)
    except PipelineMaintenanceError as e:
        raise _map_maintenance_err(e) from e


@router.delete("/data-expectations/{expectation_id}")
def delete_expectation(
    expectation_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_pipeline_maintenance_engine().delete_expectation(expectation_id)
        return {"deleted": True}
    except PipelineMaintenanceError as e:
        raise _map_maintenance_err(e) from e


# ── 稳定性建议 ──

@router.post("/stability-suggestions", response_model=StabilitySuggestion)
def register_suggestion(
    body: StabilitySuggestion,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_pipeline_maintenance_engine().register_suggestion(body)
    except PipelineMaintenanceError as e:
        raise _map_maintenance_err(e) from e


@router.get("/stability-suggestions", response_model=list[StabilitySuggestion])
def list_suggestions(
    pipeline_id: str | None = Query(None),
    priority: str | None = Query(None),
    principal: Principal = Depends(require_principal),
):
    return get_pipeline_maintenance_engine().list_suggestions(
        pipeline_id=pipeline_id, priority=priority)


@router.delete("/stability-suggestions/{suggestion_id}")
def delete_suggestion(
    suggestion_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_pipeline_maintenance_engine().delete_suggestion(suggestion_id)
        return {"deleted": True}
    except PipelineMaintenanceError as e:
        raise _map_maintenance_err(e) from e


# ── 综合 ──

@router.get("/pipeline-monitor/{pipeline_id}")
def monitor_pipeline(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
):
    return get_pipeline_maintenance_engine().monitor_pipeline(pipeline_id)


# ════════════════════ #163 Ontology Interface Extension ════════════════════
# 注意：字面量路由 /marketplace-listings/import 须注册在参数路由
# /marketplace-listings/{listing_id} 之前。

# ── 接口链接类型 ──

@router.post("/interface-link-types", response_model=InterfaceLinkType)
def register_link_type(
    body: InterfaceLinkType,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ontology_interface_extension_engine().register_link_type(body)
    except InterfaceExtensionError as e:
        raise _map_interface_ext_err(e) from e


@router.get("/interface-link-types", response_model=list[InterfaceLinkType])
def list_link_types(
    source_interface_id: str | None = Query(None),
    principal: Principal = Depends(require_principal),
):
    return get_ontology_interface_extension_engine().list_link_types(
        source_interface_id=source_interface_id)


@router.get("/interface-link-types/{link_type_id}", response_model=InterfaceLinkType)
def get_link_type(
    link_type_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ontology_interface_extension_engine().get_link_type(link_type_id)
    except InterfaceExtensionError as e:
        raise _map_interface_ext_err(e) from e


@router.put("/interface-link-types/{link_type_id}", response_model=InterfaceLinkType)
def update_link_type(
    link_type_id: str,
    fields: dict,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ontology_interface_extension_engine().update_link_type(link_type_id, fields)
    except InterfaceExtensionError as e:
        raise _map_interface_ext_err(e) from e


@router.delete("/interface-link-types/{link_type_id}")
def delete_link_type(
    link_type_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_ontology_interface_extension_engine().delete_link_type(link_type_id)
        return {"deleted": True}
    except InterfaceExtensionError as e:
        raise _map_interface_ext_err(e) from e


# ── Marketplace ──

@router.post("/marketplace-listings", response_model=InterfaceMarketplaceListing)
def register_listing(
    body: InterfaceMarketplaceListing,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ontology_interface_extension_engine().register_listing(body)
    except InterfaceExtensionError as e:
        raise _map_interface_ext_err(e) from e


@router.get("/marketplace-listings", response_model=list[InterfaceMarketplaceListing])
def list_listings(
    status: str | None = Query(None),
    principal: Principal = Depends(require_principal),
):
    return get_ontology_interface_extension_engine().list_listings(status=status)


class ImportListingBody(BaseModel):
    interface_id: str
    title: str
    description: str = ""
    version: str = "1.0.0"
    publisher: str = ""


@router.post("/marketplace-listings/import", response_model=InterfaceMarketplaceListing)
def import_listing(
    body: ImportListingBody,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ontology_interface_extension_engine().import_from_marketplace(
            interface_id=body.interface_id,
            title=body.title,
            description=body.description,
            version=body.version,
            publisher=body.publisher,
        )
    except InterfaceExtensionError as e:
        raise _map_interface_ext_err(e) from e


@router.get("/marketplace-listings/{listing_id}", response_model=InterfaceMarketplaceListing)
def get_listing(
    listing_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ontology_interface_extension_engine().get_listing(listing_id)
    except InterfaceExtensionError as e:
        raise _map_interface_ext_err(e) from e


@router.post("/marketplace-listings/{listing_id}/publish", response_model=InterfaceMarketplaceListing)
def publish_listing(
    listing_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ontology_interface_extension_engine().publish_to_marketplace(listing_id)
    except InterfaceExtensionError as e:
        raise _map_interface_ext_err(e) from e


@router.put("/marketplace-listings/{listing_id}", response_model=InterfaceMarketplaceListing)
def update_listing(
    listing_id: str,
    fields: dict,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_ontology_interface_extension_engine().update_listing(listing_id, fields)
    except InterfaceExtensionError as e:
        raise _map_interface_ext_err(e) from e


@router.delete("/marketplace-listings/{listing_id}")
def delete_listing(
    listing_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_ontology_interface_extension_engine().delete_listing(listing_id)
        return {"deleted": True}
    except InterfaceExtensionError as e:
        raise _map_interface_ext_err(e) from e
