"""AIP-6 canonical tenant AgentInstance control plane."""
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, status

from aos_api.aip_agent_control_contracts import (
    ActivateAgentInstanceRequest,
    AipOperationalProjectionResponse,
    AgentInstallResponse,
    AgentInstanceActivationResponse,
    SuspendAgentInstanceRequest,
    AgentInstanceListResponse,
    AgentRuntimeReadinessResponse,
    OperationalProjectionSources,
    OperationalStageCounts,
)
from aos_api.aip_agent_instance_activation_service import (
    AipAgentInstanceActivationService,
)
from aos_api.aip_agent_overlay_store import AipAgentOverlayStore
from aos_api.aip_agent_registry_contracts import AgentInstance
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryError,
    AipAgentRegistryNotFound,
    AipAgentRegistryPersistenceError,
    AipAgentRegistryStore,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_contracts import TenantContext
from aos_api.aip_ecommerce_agent_installer import AipEcommerceAgentInstaller
from aos_api.aip_import_preview import preview_import
from aos_api.aip_import_job_service import (
    AipImportJobBlocked,
    AipImportJobConflict,
    AipImportJobError,
    AipImportJobNotFound,
    AipImportJobPersistenceError,
    AipImportJobService,
)
from aos_api.aip_marketplace_catalog import AipMarketplaceCatalog
from aos_api.aip_marketplace_import_contracts import (
    ApplyImportJobRequest,
    ApproveImportJobRequest,
    CreateImportJobRequest,
    ImportJob,
    ImportJobListResponse,
    ImportJobMutationResponse,
    ImportPreviewRequest,
    ImportPreviewResponse,
    MarketplaceCatalogResponse,
    RollbackImportJobRequest,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/aip", tags=["aip-agents"])
_STORE = AipAgentRegistryStore()
_INSTALLER = AipEcommerceAgentInstaller(agents=_STORE)
_ACTIVATION = AipAgentInstanceActivationService(store=_STORE)
_OVERLAY = AipAgentOverlayStore(agents=_STORE)
_MARKETPLACE = AipMarketplaceCatalog(installer=_INSTALLER)
_IMPORT_JOBS = AipImportJobService()


class PromptBody(BaseModel):
    prompt: str = Field(default="", max_length=8000)
    expected_revision: int | None = Field(default=None, ge=0, alias="expectedRevision")


class ToolsBody(BaseModel):
    items: list[dict] = Field(default_factory=list)
    expected_revision: int | None = Field(default=None, ge=0, alias="expectedRevision")


class GuardrailsBody(BaseModel):
    items: list[dict] = Field(default_factory=list)
    expected_revision: int | None = Field(default=None, ge=0, alias="expectedRevision")


def get_agent_store() -> AipAgentRegistryStore:
    return _STORE


def get_ecommerce_agent_installer() -> AipEcommerceAgentInstaller:
    return _INSTALLER


def get_agent_activation_service() -> AipAgentInstanceActivationService:
    return _ACTIVATION


def get_agent_overlay_store() -> AipAgentOverlayStore:
    return _OVERLAY


def get_marketplace_catalog() -> AipMarketplaceCatalog:
    return _MARKETPLACE


def get_import_job_service() -> AipImportJobService:
    return _IMPORT_JOBS


@router.get("/marketplace/catalog", response_model=MarketplaceCatalogResponse)
def list_marketplace_catalog(
    principal: Principal = Depends(require_principal),
    catalog: AipMarketplaceCatalog = Depends(get_marketplace_catalog),
) -> MarketplaceCatalogResponse:
    try:
        return catalog.list(principal)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.post("/import-previews", response_model=ImportPreviewResponse)
def create_import_preview(
    body: ImportPreviewRequest,
    principal: Principal = Depends(require_principal),
) -> ImportPreviewResponse:
    return preview_import(principal, body)


def _require_import_role(principal: Principal, *, approval: bool = False) -> None:
    roles = {role.lower() for role in principal.roles}
    allowed = {"admin", "aip_executor", "executor", "developer"}
    if approval:
        allowed = {"admin", "reviewer", "approver"}
    if not roles.intersection(allowed):
        raise ApiError(code="AIP_SCOPE_FORBIDDEN", message="trusted import control role required", status_code=403)


def _map_import_error(exc: AipImportJobError) -> ApiError:
    if isinstance(exc, AipImportJobNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, AipImportJobConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, AipImportJobBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    if isinstance(exc, AipImportJobPersistenceError):
        return ApiError(code=exc.code, message="import job persistence failed", status_code=503)
    return ApiError(code=exc.code, message="import job failed", status_code=500)


@router.get("/import-jobs", response_model=ImportJobListResponse)
def list_import_jobs(
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    service: AipImportJobService = Depends(get_import_job_service),
) -> ImportJobListResponse:
    try:
        return service.list(_scope(principal), limit=limit)
    except AipImportJobError as exc:
        raise _map_import_error(exc) from exc


@router.get("/import-jobs/{job_id}", response_model=ImportJob)
def get_import_job(
    job_id: str,
    principal: Principal = Depends(require_principal),
    service: AipImportJobService = Depends(get_import_job_service),
) -> ImportJob:
    try:
        return service.get(_scope(principal), job_id)
    except AipImportJobError as exc:
        raise _map_import_error(exc) from exc


@router.post("/import-jobs", response_model=ImportJobMutationResponse, status_code=status.HTTP_201_CREATED)
def create_import_job(
    body: CreateImportJobRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
    principal: Principal = Depends(require_principal),
    service: AipImportJobService = Depends(get_import_job_service),
) -> ImportJobMutationResponse:
    _require_import_role(principal)
    try:
        return service.create(principal, body, idempotency_key=idempotency_key)
    except AipImportJobError as exc:
        raise _map_import_error(exc) from exc


@router.post("/import-jobs/{job_id}/approval", response_model=ImportJobMutationResponse)
def approve_import_job(
    job_id: str,
    body: ApproveImportJobRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
    principal: Principal = Depends(require_principal),
    service: AipImportJobService = Depends(get_import_job_service),
) -> ImportJobMutationResponse:
    _require_import_role(principal, approval=True)
    try:
        return service.approve(_scope(principal), job_id, body, actor=principal.subject, idempotency_key=idempotency_key)
    except AipImportJobError as exc:
        raise _map_import_error(exc) from exc


@router.post("/import-jobs/{job_id}/apply", response_model=ImportJobMutationResponse)
def apply_import_job(
    job_id: str,
    body: ApplyImportJobRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
    principal: Principal = Depends(require_principal),
    service: AipImportJobService = Depends(get_import_job_service),
) -> ImportJobMutationResponse:
    _require_import_role(principal)
    try:
        return service.apply(_scope(principal), job_id, body, actor=principal.subject, idempotency_key=idempotency_key)
    except AipImportJobError as exc:
        raise _map_import_error(exc) from exc


@router.post("/import-jobs/{job_id}/rollback", response_model=ImportJobMutationResponse)
def rollback_import_job(
    job_id: str,
    body: RollbackImportJobRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
    principal: Principal = Depends(require_principal),
    service: AipImportJobService = Depends(get_import_job_service),
) -> ImportJobMutationResponse:
    _require_import_role(principal)
    try:
        return service.rollback(_scope(principal), job_id, body, actor=principal.subject, idempotency_key=idempotency_key)
    except AipImportJobError as exc:
        raise _map_import_error(exc) from exc


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _idem(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 120:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="Idempotency-Key must be 1..120 characters", status_code=400)
    return cleaned


def _map_error(exc: AipAgentRegistryError) -> ApiError:
    if isinstance(exc, AipAgentRegistryNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, AipAgentRegistryConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, AipAgentRegistryTransitionBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    if isinstance(exc, AipAgentRegistryPersistenceError):
        return ApiError(code=exc.code, message="agent registry persistence failed", status_code=503)
    return ApiError(code=exc.code, message="agent registry failed", status_code=503)


@router.get("/agents", response_model=AgentInstanceListResponse)
def list_agents(
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    store: AipAgentRegistryStore = Depends(get_agent_store),
) -> AgentInstanceListResponse:
    try:
        items = store.list_instances(_scope(principal), limit=limit)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return AgentInstanceListResponse(
        tenant=TenantContext(org_id=principal.org_id, project_id=principal.project_id),
        items=items,
        count=len(items),
    )


@router.get(
    "/agent-registry/runtime-readiness",
    response_model=AgentRuntimeReadinessResponse,
)
def get_agent_runtime_readiness(
    principal: Principal = Depends(require_principal),
    installer: AipEcommerceAgentInstaller = Depends(get_ecommerce_agent_installer),
) -> AgentRuntimeReadinessResponse:
    try:
        return installer.runtime_readiness(principal)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


def _ref_key(value: Any) -> tuple[str, int, str]:
    return (str(value.asset_id), int(value.revision), str(value.content_hash))


def _fresh(value: datetime | None, now: datetime) -> bool:
    if value is None:
        return False
    checked = value if value.tzinfo else value.replace(tzinfo=UTC)
    return checked > now


def _build_operational_projection(
    *,
    principal: Principal,
    runtime: AgentRuntimeReadinessResponse,
    model_runtime: Any,
    tool_items: list[dict[str, Any]],
    overlay_tools: dict[str, list[dict[str, Any]]],
    generated_at: datetime,
) -> AipOperationalProjectionResponse:
    """Build a deterministic, secret-free projection from canonical read models."""

    catalog_items = runtime.catalog.items
    instance_ids = {
        item.instance.instance_id
        for item in catalog_items
        if item.instance is not None
    }
    active_instance_ids = {
        item.instance.instance_id
        for item in catalog_items
        if item.instance is not None and item.instance.status == "active"
    }
    runnable_instance_ids = {
        item.instance.instance_id
        for item in catalog_items
        if item.instance is not None and item.runtime_readiness == "runnable"
    }
    bound_instance_ids = {
        item.instance_id
        for item in runtime.skill_bindings
        if item.instance_id in instance_ids
    }
    role_counts = OperationalStageCounts(
        definition=runtime.catalog.stats.definition_count,
        bound=len(bound_instance_ids),
        enabled=len(active_instance_ids & bound_instance_ids),
        runnable=len(runnable_instance_ids & active_instance_ids & bound_instance_ids),
    )

    catalog_capability_ids = {
        capability_id
        for item in catalog_items
        for capability_id in item.required_capability_ids
    }
    capability_bindings = [
        item for item in runtime.capability_bindings
        if item.capability.asset_id in catalog_capability_ids
    ]
    bound_capability_ids = {item.capability.asset_id for item in capability_bindings}
    enabled_capability_ids = {
        item.capability.asset_id for item in capability_bindings
        if item.status == "active"
    }
    runnable_capability_ids = {
        item.capability.asset_id for item in capability_bindings
        if item.status == "active"
        and item.operational_readiness == "available"
        and _fresh(item.readiness_expires_at, generated_at)
    }
    capability_counts = OperationalStageCounts(
        definition=len(catalog_capability_ids),
        bound=len(bound_capability_ids),
        enabled=len(enabled_capability_ids),
        runnable=len(runnable_capability_ids),
    )

    tool_definition_ids = {
        str(item.get("id") or "").strip() for item in tool_items
        if str(item.get("id") or "").strip()
    }
    dependency_tool_ids = {
        ref.asset_id
        for binding in [*runtime.capability_bindings, *runtime.skill_bindings]
        for ref in binding.dependencies.tool_dependency_refs
        if ref.asset_id in tool_definition_ids
    }
    overlay_bound_ids: set[str] = set()
    overlay_enabled_ids: set[str] = set()
    overlay_runnable_ids: set[str] = set()
    for instance_id, items in overlay_tools.items():
        for item in items:
            tool_id = str(item.get("id") or "").strip()
            if tool_id not in tool_definition_ids:
                continue
            overlay_bound_ids.add(tool_id)
            if item.get("enabled") is not False and instance_id in active_instance_ids:
                overlay_enabled_ids.add(tool_id)
                if instance_id in runnable_instance_ids:
                    overlay_runnable_ids.add(tool_id)
    dependency_enabled_ids = {
        ref.asset_id
        for binding in runtime.capability_bindings
        if binding.status == "active"
        for ref in binding.dependencies.tool_dependency_refs
        if ref.asset_id in tool_definition_ids
    }
    dependency_runnable_ids = {
        ref.asset_id
        for binding in runtime.capability_bindings
        if binding.status == "active"
        and binding.operational_readiness == "available"
        and _fresh(binding.readiness_expires_at, generated_at)
        for ref in binding.dependencies.tool_dependency_refs
        if ref.asset_id in tool_definition_ids
    }
    bound_tool_ids = dependency_tool_ids | overlay_bound_ids
    enabled_tool_ids = (dependency_enabled_ids | overlay_enabled_ids) & bound_tool_ids
    runnable_tool_ids = (dependency_runnable_ids | overlay_runnable_ids) & enabled_tool_ids
    tool_counts = OperationalStageCounts(
        definition=len(bound_tool_ids),
        bound=len(bound_tool_ids),
        enabled=len(enabled_tool_ids),
        runnable=len(runnable_tool_ids),
    )

    eval_definition = len(model_runtime.eval_gates)
    eval_evaluated = sum(item.status != "unknown" for item in model_runtime.eval_gates)
    eval_passed = sum(item.status == "passed" for item in model_runtime.eval_gates)
    eval_counts = OperationalStageCounts(
        definition=eval_definition,
        bound=eval_definition,
        enabled=eval_evaluated,
        runnable=eval_passed,
    )

    bound_route_keys = {
        _ref_key(binding.dependencies.model_route_ref)
        for binding in [*runtime.capability_bindings, *runtime.skill_bindings]
        if binding.dependencies.model_route_ref is not None
    }
    route_keys = {_ref_key(item.ref) for item in model_runtime.routes}
    active_route_keys = {
        _ref_key(item.ref) for item in model_runtime.routes if item.lifecycle == "active"
    }
    ready_route_keys = {
        _ref_key(item.route) for item in model_runtime.resolutions
        if item.readiness == "ready"
    }
    bound_routes = route_keys & bound_route_keys
    enabled_routes = bound_routes & active_route_keys
    runnable_routes = enabled_routes & ready_route_keys
    route_counts = OperationalStageCounts(
        definition=len(route_keys),
        bound=len(bound_routes),
        enabled=len(enabled_routes),
        runnable=len(runnable_routes),
    )

    blockers: list[str] = []
    if role_counts.definition == 0 or role_counts.runnable != role_counts.definition:
        blockers.append("roles_not_fully_runnable")
    if capability_counts.definition == 0 or capability_counts.runnable != capability_counts.definition:
        blockers.append("capabilities_not_fully_runnable")
    if tool_counts.definition == 0 or tool_counts.runnable != tool_counts.definition:
        blockers.append("tools_not_fully_runnable")
    if route_counts.definition == 0 or route_counts.runnable != route_counts.definition:
        blockers.append("routes_not_fully_runnable")
    if eval_counts.definition == 0 or eval_counts.runnable != eval_counts.definition:
        blockers.append("eval_gates_not_fully_passed")

    basis = {
        "tenant": [principal.org_id, principal.project_id],
        "catalog": [
            {
                "template": [item.template.template_id, item.template.revision, item.template.content_hash],
                "instance": None if item.instance is None else [
                    item.instance.instance_id,
                    item.instance.instance_ref.revision,
                    item.instance.instance_ref.content_hash,
                    item.instance.status,
                ],
                "readiness": item.runtime_readiness,
                "blockers": sorted(item.blockers),
            }
            for item in catalog_items
        ],
        "capabilityBindings": sorted([
            [item.binding_id, item.version, item.status, item.operational_readiness, item.dependency_snapshot_hash]
            for item in runtime.capability_bindings
        ]),
        "skillBindings": sorted([
            [item.binding_id, item.version, item.instance_id, item.status, item.readiness, item.dependency_snapshot_hash]
            for item in runtime.skill_bindings
        ]),
        "tools": sorted([
            [str(item.get("id") or ""), str(item.get("kind") or ""), bool(item.get("blocked", False))]
            for item in tool_items
        ]),
        "overlayTools": {
            key: sorted([[str(item.get("id") or ""), item.get("enabled") is not False] for item in value])
            for key, value in sorted(overlay_tools.items())
        },
        "modelAssets": sorted([
            [item.ref.asset_type, item.ref.asset_id, item.ref.revision, item.ref.content_hash, item.lifecycle]
            for item in [
                *model_runtime.providers,
                *model_runtime.models,
                *model_runtime.routes,
                *model_runtime.policies,
                *model_runtime.price_snapshots,
            ]
        ]),
        "evalGates": sorted([
            [item.ref.asset_id, item.ref.revision, item.ref.content_hash, item.status]
            for item in model_runtime.eval_gates
        ]),
        "resolutions": sorted([
            [item.route.asset_id, item.route.revision, item.route.content_hash, item.readiness, sorted(item.blocker_codes)]
            for item in model_runtime.resolutions
        ]),
    }
    snapshot_hash = hashlib.sha256(
        json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return AipOperationalProjectionResponse(
        tenant={"orgId": principal.org_id, "projectId": principal.project_id},
        roles=role_counts,
        capabilities=capability_counts,
        tools=tool_counts,
        evalGates=eval_counts,
        routes=route_counts,
        overallReadiness="ready" if not blockers else "blocked",
        blockerCodes=blockers,
        sources=OperationalProjectionSources(
            agentReadinessAt=runtime.evaluated_at,
            modelRuntimeAt=model_runtime.generated_at,
        ),
        snapshotHash=snapshot_hash,
        generatedAt=generated_at,
    )


@router.get(
    "/operational-projection",
    response_model=AipOperationalProjectionResponse,
)
def get_operational_projection(
    principal: Principal = Depends(require_principal),
    installer: AipEcommerceAgentInstaller = Depends(get_ecommerce_agent_installer),
    overlay: AipAgentOverlayStore = Depends(get_agent_overlay_store),
) -> AipOperationalProjectionResponse:
    """Cross-page read projection. It never writes, refreshes, evaluates or calls a provider."""

    from aos_api.routers.aip_model_runtime import get_overview as model_overview
    from aos_api.routers.aip_model_runtime import get_store as get_model_runtime_store
    from aos_api.routers.wave_ext import list_tools

    try:
        runtime = installer.runtime_readiness(principal)
        model_runtime = model_overview(principal, get_model_runtime_store())
        tool_items = list_tools(principal).get("items") or []
        scope = _scope(principal)
        overlay_tools = {
            item.instance.instance_id: overlay.get_tools(
                scope, item.instance.instance_id
            ).get("items", [])
            for item in runtime.catalog.items
            if item.instance is not None
        }
        return _build_operational_projection(
            principal=principal,
            runtime=runtime,
            model_runtime=model_runtime,
            tool_items=tool_items,
            overlay_tools=overlay_tools,
            generated_at=datetime.now(UTC),
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/agent-registry/refresh-readiness",
    response_model=AgentRuntimeReadinessResponse,
)
def refresh_agent_runtime_readiness(
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    installer: AipEcommerceAgentInstaller = Depends(get_ecommerce_agent_installer),
) -> AgentRuntimeReadinessResponse:
    try:
        return installer.refresh_binding_readiness(
            principal, idempotency_key=_idem(idempotency_key)
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/agents/install-ecommerce",
    response_model=AgentInstallResponse,
    status_code=status.HTTP_201_CREATED,
)
def install_ecommerce_agents(
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    installer: AipEcommerceAgentInstaller = Depends(get_ecommerce_agent_installer),
) -> AgentInstallResponse:
    try:
        return installer.install(principal, idempotency_key=_idem(idempotency_key))
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.post("/agents")
def retired_create_agent(principal: Principal = Depends(require_principal)) -> None:
    _ = principal
    raise ApiError(
        code="AIP_LEGACY_AGENT_WRITE_RETIRED",
        message="legacy in-memory agent creation is retired; install a published SolutionPack",
        status_code=409,
    )


@router.get("/agents/{instance_id}", response_model=AgentInstance)
def get_agent(
    instance_id: str,
    principal: Principal = Depends(require_principal),
    store: AipAgentRegistryStore = Depends(get_agent_store),
) -> AgentInstance:
    try:
        return store.get_instance(_scope(principal), instance_id)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/agents/{instance_id}/activate",
    response_model=AgentInstanceActivationResponse,
)
def activate_agent(
    instance_id: str,
    body: ActivateAgentInstanceRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipAgentInstanceActivationService = Depends(
        get_agent_activation_service
    ),
) -> AgentInstanceActivationResponse:
    try:
        instance, receipt = service.activate(
            _scope(principal),
            instance_id,
            body,
            idempotency_key=_idem(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return AgentInstanceActivationResponse(
        tenant=TenantContext(
            org_id=principal.org_id,
            project_id=principal.project_id,
        ),
        instance=instance,
        capability_binding_ids=body.capability_binding_ids,
        receipt=receipt,
    )


@router.post(
    "/agents/{instance_id}/suspend",
    response_model=AgentInstanceActivationResponse,
)
def suspend_agent(
    instance_id: str,
    body: SuspendAgentInstanceRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipAgentInstanceActivationService = Depends(
        get_agent_activation_service
    ),
) -> AgentInstanceActivationResponse:
    try:
        instance, receipt = service.suspend(
            _scope(principal),
            instance_id,
            body,
            idempotency_key=_idem(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return AgentInstanceActivationResponse(
        tenant=TenantContext(
            org_id=principal.org_id,
            project_id=principal.project_id,
        ),
        instance=instance,
        capability_binding_ids=[],
        receipt=receipt,
    )


@router.get("/agents/{instance_id}/prompt")
def get_prompt(
    instance_id: str,
    principal: Principal = Depends(require_principal),
    overlay: AipAgentOverlayStore = Depends(get_agent_overlay_store),
) -> dict:
    try:
        return overlay.get_prompt(_scope(principal), instance_id)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    except ValueError as exc:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message=str(exc), status_code=400) from exc


@router.put("/agents/{instance_id}/prompt")
def update_prompt(
    instance_id: str,
    body: PromptBody,
    principal: Principal = Depends(require_principal),
    overlay: AipAgentOverlayStore = Depends(get_agent_overlay_store),
) -> dict:
    try:
        return overlay.put_prompt(
            _scope(principal),
            instance_id,
            prompt=body.prompt,
            actor=principal.subject,
            expected_revision=body.expected_revision,
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    except ValueError as exc:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message=str(exc), status_code=400) from exc


@router.get("/agents/{instance_id}/tools")
def get_tools(
    instance_id: str,
    principal: Principal = Depends(require_principal),
    overlay: AipAgentOverlayStore = Depends(get_agent_overlay_store),
) -> dict:
    try:
        return overlay.get_tools(_scope(principal), instance_id)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    except ValueError as exc:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message=str(exc), status_code=400) from exc


@router.put("/agents/{instance_id}/tools")
def update_tools(
    instance_id: str,
    body: ToolsBody,
    principal: Principal = Depends(require_principal),
    overlay: AipAgentOverlayStore = Depends(get_agent_overlay_store),
) -> dict:
    try:
        return overlay.put_tools(
            _scope(principal),
            instance_id,
            items=list(body.items or []),
            actor=principal.subject,
            expected_revision=body.expected_revision,
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    except ValueError as exc:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message=str(exc), status_code=400) from exc


@router.get("/agents/{instance_id}/guardrails")
def get_guardrails(
    instance_id: str,
    principal: Principal = Depends(require_principal),
    overlay: AipAgentOverlayStore = Depends(get_agent_overlay_store),
) -> dict:
    try:
        return overlay.get_guardrails(_scope(principal), instance_id)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    except ValueError as exc:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message=str(exc), status_code=400) from exc


@router.put("/agents/{instance_id}/guardrails")
def update_guardrails(
    instance_id: str,
    body: GuardrailsBody,
    principal: Principal = Depends(require_principal),
    overlay: AipAgentOverlayStore = Depends(get_agent_overlay_store),
) -> dict:
    try:
        return overlay.put_guardrails(
            _scope(principal),
            instance_id,
            items=list(body.items or []),
            actor=principal.subject,
            expected_revision=body.expected_revision,
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    except ValueError as exc:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message=str(exc), status_code=400) from exc
