"""AIP-6 canonical tenant AgentInstance control plane."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status

from aos_api.aip_agent_control_contracts import (
    AgentInstallResponse,
    AgentInstanceListResponse,
)
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
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip", tags=["aip-agents"])
_STORE = AipAgentRegistryStore()
_INSTALLER = AipEcommerceAgentInstaller(agents=_STORE)


def get_agent_store() -> AipAgentRegistryStore:
    return _STORE


def get_ecommerce_agent_installer() -> AipEcommerceAgentInstaller:
    return _INSTALLER


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


def _overlay_not_implemented(principal: Principal) -> None:
    _ = principal
    raise ApiError(
        code="AIP_CANONICAL_OVERLAY_NOT_IMPLEMENTED",
        message="prompt, tool and guardrail overlays require a versioned canonical overlay contract",
        status_code=409,
    )


@router.get("/agents/{instance_id}/prompt")
def get_prompt(instance_id: str, principal: Principal = Depends(require_principal)) -> None:
    _ = instance_id
    _overlay_not_implemented(principal)


@router.put("/agents/{instance_id}/prompt")
def update_prompt(instance_id: str, principal: Principal = Depends(require_principal)) -> None:
    _ = instance_id
    _overlay_not_implemented(principal)


@router.get("/agents/{instance_id}/tools")
def get_tools(instance_id: str, principal: Principal = Depends(require_principal)) -> None:
    _ = instance_id
    _overlay_not_implemented(principal)


@router.put("/agents/{instance_id}/tools")
def update_tools(instance_id: str, principal: Principal = Depends(require_principal)) -> None:
    _ = instance_id
    _overlay_not_implemented(principal)


@router.get("/agents/{instance_id}/guardrails")
def get_guardrails(instance_id: str, principal: Principal = Depends(require_principal)) -> None:
    _ = instance_id
    _overlay_not_implemented(principal)


@router.put("/agents/{instance_id}/guardrails")
def update_guardrails(instance_id: str, principal: Principal = Depends(require_principal)) -> None:
    _ = instance_id
    _overlay_not_implemented(principal)
