"""AIP-6 canonical agent and capability catalogs."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from aos_api.aip_agent_control_contracts import (
    AgentCatalogResponse,
    CapabilityCatalogResponse,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryError
from aos_api.aip_ecommerce_agent_installer import AipEcommerceAgentInstaller
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError

router = APIRouter(prefix="/v1/aip", tags=["aip-capabilities"])
_CONTROL = AipEcommerceAgentInstaller()


def get_agent_catalog_service() -> AipEcommerceAgentInstaller:
    return _CONTROL


def _map_error(exc: AipAgentRegistryError) -> ApiError:
    return ApiError(code=exc.code, message=str(exc), status_code=409 if "INVALID" in exc.code or "CONFLICT" in exc.code else 503)


@router.get("/agent-registry", response_model=AgentCatalogResponse)
def list_registry(
    principal: Principal = Depends(require_principal),
    service: AipEcommerceAgentInstaller = Depends(get_agent_catalog_service),
) -> AgentCatalogResponse:
    try:
        return service.catalog(principal)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.get("/capability-catalog", response_model=CapabilityCatalogResponse)
def list_capability_catalog(
    principal: Principal = Depends(require_principal),
    service: AipEcommerceAgentInstaller = Depends(get_agent_catalog_service),
) -> CapabilityCatalogResponse:
    try:
        return service.capability_catalog(principal)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


def _binding_required(principal: Principal) -> None:
    _ = principal
    raise ApiError(
        code="AIP_CAPABILITY_BINDING_REQUIRED",
        message="capability configuration and connectivity require a versioned tenant CapabilityBinding",
        status_code=409,
    )


@router.put("/capabilities/{capability_id}")
def retired_update_capability(
    capability_id: str,
    principal: Principal = Depends(require_principal),
) -> None:
    _ = capability_id
    _binding_required(principal)


@router.post("/capabilities/test")
def retired_test_capability(principal: Principal = Depends(require_principal)) -> None:
    _binding_required(principal)
