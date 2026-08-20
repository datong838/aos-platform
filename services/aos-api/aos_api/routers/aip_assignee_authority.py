"""Assignee resolution API (W-L20)."""

# ruff: noqa: B008
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from aos_api.aip_assignee_resolution import (
    AssigneeResolutionReceipt,
    ResolveAssigneeRequest,
    ToolBindingRecord,
    UpsertToolBindingRequest,
)
from aos_api.aip_assignee_resolution_store import AipAssigneeResolutionStore
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(
    prefix="/v1/aip/assignee-authority", tags=["aip-assignee-authority"]
)
_STORE = AipAssigneeResolutionStore()


def get_aip_assignee_resolution_store() -> AipAssigneeResolutionStore:
    return _STORE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _require_role(principal: Principal) -> None:
    if not {role.lower() for role in principal.roles}.intersection(
        {"admin", "executor", "aip_executor"}
    ):
        raise ApiError(
            code="AIP_SCOPE_FORBIDDEN",
            message="trusted assignee authority role required",
            status_code=403,
        )


@router.post("/tool-bindings", response_model=ToolBindingRecord)
def upsert_tool_binding(
    body: UpsertToolBindingRequest,
    principal: Principal = Depends(require_principal),
    store: AipAssigneeResolutionStore = Depends(get_aip_assignee_resolution_store),
) -> ToolBindingRecord:
    _require_role(principal)
    return store.upsert_tool_binding(
        _scope(principal), body, now=datetime.now(UTC)
    )


@router.post("/resolutions", response_model=AssigneeResolutionReceipt)
def resolve_assignee(
    body: ResolveAssigneeRequest,
    principal: Principal = Depends(require_principal),
    store: AipAssigneeResolutionStore = Depends(get_aip_assignee_resolution_store),
) -> AssigneeResolutionReceipt:
    _require_role(principal)
    return store.resolve(
        _scope(principal), body, principal.subject, now=datetime.now(UTC)
    )
