"""Canonical tenant API for governed CapabilityBinding and SkillBinding."""
from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from fastapi import APIRouter, Depends, Header, Query, status

from aos_api.aip_agent_registry_contracts import (
    CapabilityBinding,
    CreateCapabilityBindingRequest,
    CreateSkillBindingRequest,
    EvaluateOperationalBindingRequest,
    SkillBinding,
    UpdateCapabilityBindingRequest,
    UpdateSkillBindingRequest,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryError,
    AipAgentRegistryNotFound,
    AipAgentRegistryPersistenceError,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_binding_api_contracts import (
    BindingReadinessResponse,
    CapabilityBindingCommandResponse,
    CapabilityBindingListResponse,
    CapabilityBindingPreviewRequest,
    CapabilityBindingTransitionRequest,
    SkillBindingCommandResponse,
    SkillBindingListResponse,
    SkillBindingPreviewRequest,
    SkillBindingTransitionRequest,
)
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_binding_readiness_reader_connection import (
    ReadinessReaderConnectionFactory,
    ReadinessReaderDatabaseConfig,
)
from aos_api.aip_binding_readiness_service import (
    AipBindingReadinessService,
    PostgresBindingDependencyAuthority,
)
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_registry_issuer_connection import (
    RegistryIssuerConnectionFactory,
    RegistryIssuerDatabaseConfig,
)
from aos_api.aip_contracts import TenantContext
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip", tags=["aip-bindings"])


def build_capability_binding_service(
    environ: Mapping[str, str] | None = None,
) -> AipCapabilityBindingService:
    config = os.environ if environ is None else environ
    names = ("HOST", "PORT", "DATABASE", "PASSFILE")
    prefixes = ("AOS_AIP_BINDING_READER_", "AOS_AIP_BINDING_ISSUER_")
    values = [[config.get(prefix + name, "") for name in names] for prefix in prefixes]
    if not any(value for group in values for value in group):
        return AipCapabilityBindingService()
    if (any(not value for group in values for value in group)
            or values[0][:3] != values[1][:3]
            or values[0][3] == values[1][3]):
        raise RuntimeError("AIP_BINDING_PRIVATE_CONFIGURATION_REQUIRED")
    try:
        host, port, database = values[0][:3]
        reader = ReadinessReaderConnectionFactory(ReadinessReaderDatabaseConfig(
            host, int(port), database, Path(values[0][3]),
        ))
        issuer = RegistryIssuerConnectionFactory(RegistryIssuerDatabaseConfig(
            host, int(port), database, Path(values[1][3]),
        ), command_family="capability_lifecycle")
        if os.path.samefile(reader.config.passfile, issuer.config.passfile):
            raise RuntimeError("AIP_BINDING_PRIVATE_CONFIGURATION_REQUIRED")
    except (OSError, ValueError, RuntimeError) as exc:
        raise RuntimeError("AIP_BINDING_PRIVATE_CONFIGURATION_REQUIRED") from exc
    readiness = AipBindingReadinessService(
        authority=PostgresBindingDependencyAuthority(reader),
        model_store=AipModelRuntimeStore(reader),
    )
    return AipCapabilityBindingService(issuer, readiness_service=readiness)


_CAPABILITY_SERVICE = build_capability_binding_service()
_CAPABILITY_PRIVATE_CONFIGURED = (
    isinstance(_CAPABILITY_SERVICE._connect_factory, RegistryIssuerConnectionFactory)
    and _CAPABILITY_SERVICE._readiness_service is not None
)
_SKILL_SERVICE = AipSkillRegistry()


def get_capability_binding_service() -> AipCapabilityBindingService:
    return _CAPABILITY_SERVICE


def get_skill_binding_service() -> AipSkillRegistry:
    return _SKILL_SERVICE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _tenant(principal: Principal) -> TenantContext:
    return TenantContext(org_id=principal.org_id, project_id=principal.project_id)


def _idem(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 120:
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="Idempotency-Key must be 1..120 characters",
            status_code=400,
        )
    return cleaned


def _map_error(exc: AipAgentRegistryError) -> ApiError:
    if isinstance(exc, AipAgentRegistryNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, AipAgentRegistryConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, AipAgentRegistryTransitionBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    if isinstance(exc, AipAgentRegistryPersistenceError):
        return ApiError(
            code=exc.code,
            message="binding registry persistence failed",
            status_code=503,
        )
    return ApiError(code=exc.code, message="binding registry failed", status_code=503)


def _require_snapshot(expected: str | None, actual: str | None) -> None:
    if expected is not None and expected != actual:
        raise AipAgentRegistryConflict("dependency snapshot hash changed")


def _require_private_capability_write() -> None:
    if (os.environ.get("AOS_AIP_BINDING_REQUIRE_PRIVATE") == "1"
            and not _CAPABILITY_PRIVATE_CONFIGURED):
        raise ApiError(
            code="AIP_BINDING_PRIVATE_CONFIGURATION_REQUIRED",
            message="private capability binding identity required",
            status_code=503,
        )


@router.get(
    "/capability-bindings", response_model=CapabilityBindingListResponse
)
def list_capability_bindings(
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    service: AipCapabilityBindingService = Depends(
        get_capability_binding_service
    ),
) -> CapabilityBindingListResponse:
    try:
        items = service.list_bindings(_scope(principal), limit=limit)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return CapabilityBindingListResponse(
        tenant=_tenant(principal), items=items, count=len(items)
    )


@router.post(
    "/capability-bindings/preview", response_model=BindingReadinessResponse
)
def preview_capability_binding(
    request: CapabilityBindingPreviewRequest,
    principal: Principal = Depends(require_principal),
    service: AipCapabilityBindingService = Depends(
        get_capability_binding_service
    ),
) -> BindingReadinessResponse:
    try:
        readiness = service.preview(
            _scope(principal), request, evaluated_at=datetime.now(UTC)
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return BindingReadinessResponse(tenant=_tenant(principal), readiness=readiness)


@router.post(
    "/capability-bindings",
    response_model=CapabilityBindingCommandResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_capability_binding(
    request: CreateCapabilityBindingRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipCapabilityBindingService = Depends(
        get_capability_binding_service
    ),
) -> CapabilityBindingCommandResponse:
    _require_private_capability_write()
    try:
        binding, receipt = service.create(
            _scope(principal),
            request,
            idempotency_key=_idem(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return CapabilityBindingCommandResponse(
        tenant=_tenant(principal), binding=binding, receipt=receipt
    )


@router.get(
    "/capability-bindings/{binding_id}", response_model=CapabilityBinding
)
def get_capability_binding(
    binding_id: str,
    principal: Principal = Depends(require_principal),
    service: AipCapabilityBindingService = Depends(
        get_capability_binding_service
    ),
) -> CapabilityBinding:
    try:
        return service.get(_scope(principal), binding_id)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/capability-bindings/{binding_id}/evaluate",
    response_model=CapabilityBindingCommandResponse,
)
def evaluate_capability_binding(
    binding_id: str,
    request: EvaluateOperationalBindingRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipCapabilityBindingService = Depends(
        get_capability_binding_service
    ),
) -> CapabilityBindingCommandResponse:
    _require_private_capability_write()
    try:
        binding, readiness, receipt = service.evaluate(
            _scope(principal),
            binding_id,
            request,
            idempotency_key=_idem(idempotency_key),
            actor=principal.subject,
            evaluated_at=datetime.now(UTC),
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return CapabilityBindingCommandResponse(
        tenant=_tenant(principal),
        binding=binding,
        readiness=readiness,
        receipt=receipt,
    )


def _transition_capability(
    desired_status: str,
    binding_id: str,
    request: CapabilityBindingTransitionRequest,
    principal: Principal,
    service: AipCapabilityBindingService,
    idempotency_key: str,
) -> CapabilityBindingCommandResponse:
    _require_private_capability_write()
    try:
        current = service.get(_scope(principal), binding_id)
        _require_snapshot(
            request.expected_dependency_snapshot_hash,
            current.dependency_snapshot_hash,
        )
        binding, receipt = service.update(
            _scope(principal),
            binding_id,
            UpdateCapabilityBindingRequest(
                expected_version=request.expected_version,
                from_status=current.status,
                to_status=desired_status,
                health=request.health,
                observed_at=request.observed_at,
            ),
            idempotency_key=_idem(idempotency_key),
            actor=principal.subject,
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return CapabilityBindingCommandResponse(
        tenant=_tenant(principal), binding=binding, receipt=receipt
    )


@router.post(
    "/capability-bindings/{binding_id}/activate",
    response_model=CapabilityBindingCommandResponse,
)
def activate_capability_binding(
    binding_id: str,
    request: CapabilityBindingTransitionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipCapabilityBindingService = Depends(
        get_capability_binding_service
    ),
) -> CapabilityBindingCommandResponse:
    return _transition_capability(
        "active", binding_id, request, principal, service, idempotency_key
    )


@router.post(
    "/capability-bindings/{binding_id}/suspend",
    response_model=CapabilityBindingCommandResponse,
)
def suspend_capability_binding(
    binding_id: str,
    request: CapabilityBindingTransitionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipCapabilityBindingService = Depends(
        get_capability_binding_service
    ),
) -> CapabilityBindingCommandResponse:
    return _transition_capability(
        "suspended", binding_id, request, principal, service, idempotency_key
    )


@router.post(
    "/capability-bindings/{binding_id}/revoke",
    response_model=CapabilityBindingCommandResponse,
)
def revoke_capability_binding(
    binding_id: str,
    request: CapabilityBindingTransitionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipCapabilityBindingService = Depends(
        get_capability_binding_service
    ),
) -> CapabilityBindingCommandResponse:
    return _transition_capability(
        "revoked", binding_id, request, principal, service, idempotency_key
    )


@router.get("/skill-bindings", response_model=SkillBindingListResponse)
def list_skill_bindings(
    instance_id: str | None = Query(default=None, alias="instanceId"),
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    service: AipSkillRegistry = Depends(get_skill_binding_service),
) -> SkillBindingListResponse:
    try:
        items = service.list_bindings(
            _scope(principal), instance_id=instance_id, limit=limit
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return SkillBindingListResponse(
        tenant=_tenant(principal), items=items, count=len(items)
    )


@router.post("/skill-bindings/preview", response_model=BindingReadinessResponse)
def preview_skill_binding(
    request: SkillBindingPreviewRequest,
    principal: Principal = Depends(require_principal),
    service: AipSkillRegistry = Depends(get_skill_binding_service),
) -> BindingReadinessResponse:
    try:
        readiness = service.preview_binding(
            _scope(principal), request, evaluated_at=datetime.now(UTC)
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return BindingReadinessResponse(tenant=_tenant(principal), readiness=readiness)


@router.post(
    "/skill-bindings",
    response_model=SkillBindingCommandResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_skill_binding(
    request: CreateSkillBindingRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipSkillRegistry = Depends(get_skill_binding_service),
) -> SkillBindingCommandResponse:
    try:
        binding, receipt = service.create_binding(
            _scope(principal),
            request,
            idempotency_key=_idem(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return SkillBindingCommandResponse(
        tenant=_tenant(principal), binding=binding, receipt=receipt
    )


@router.get("/skill-bindings/{binding_id}", response_model=SkillBinding)
def get_skill_binding(
    binding_id: str,
    principal: Principal = Depends(require_principal),
    service: AipSkillRegistry = Depends(get_skill_binding_service),
) -> SkillBinding:
    try:
        return service.get_binding(_scope(principal), binding_id)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/skill-bindings/{binding_id}/evaluate",
    response_model=SkillBindingCommandResponse,
)
def evaluate_skill_binding(
    binding_id: str,
    request: EvaluateOperationalBindingRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipSkillRegistry = Depends(get_skill_binding_service),
) -> SkillBindingCommandResponse:
    try:
        binding, readiness, receipt = service.evaluate_binding(
            _scope(principal),
            binding_id,
            request,
            idempotency_key=_idem(idempotency_key),
            actor=principal.subject,
            evaluated_at=datetime.now(UTC),
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return SkillBindingCommandResponse(
        tenant=_tenant(principal),
        binding=binding,
        readiness=readiness,
        receipt=receipt,
    )


def _transition_skill(
    desired_status: str,
    binding_id: str,
    request: SkillBindingTransitionRequest,
    principal: Principal,
    service: AipSkillRegistry,
    idempotency_key: str,
) -> SkillBindingCommandResponse:
    try:
        current = service.get_binding(_scope(principal), binding_id)
        _require_snapshot(
            request.expected_dependency_snapshot_hash,
            current.dependency_snapshot_hash,
        )
        binding, receipt = service.update_binding(
            _scope(principal),
            binding_id,
            UpdateSkillBindingRequest(
                expected_version=request.expected_version,
                from_status=current.status,
                to_status=desired_status,
            ),
            idempotency_key=_idem(idempotency_key),
            actor=principal.subject,
            occurred_at=request.occurred_at,
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return SkillBindingCommandResponse(
        tenant=_tenant(principal), binding=binding, receipt=receipt
    )


@router.post(
    "/skill-bindings/{binding_id}/activate",
    response_model=SkillBindingCommandResponse,
)
def activate_skill_binding(
    binding_id: str,
    request: SkillBindingTransitionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipSkillRegistry = Depends(get_skill_binding_service),
) -> SkillBindingCommandResponse:
    return _transition_skill(
        "active", binding_id, request, principal, service, idempotency_key
    )


@router.post(
    "/skill-bindings/{binding_id}/suspend",
    response_model=SkillBindingCommandResponse,
)
def suspend_skill_binding(
    binding_id: str,
    request: SkillBindingTransitionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipSkillRegistry = Depends(get_skill_binding_service),
) -> SkillBindingCommandResponse:
    return _transition_skill(
        "suspended", binding_id, request, principal, service, idempotency_key
    )


@router.post(
    "/skill-bindings/{binding_id}/revoke",
    response_model=SkillBindingCommandResponse,
)
def revoke_skill_binding(
    binding_id: str,
    request: SkillBindingTransitionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipSkillRegistry = Depends(get_skill_binding_service),
) -> SkillBindingCommandResponse:
    return _transition_skill(
        "revoked", binding_id, request, principal, service, idempotency_key
    )
