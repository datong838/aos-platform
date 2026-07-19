"""TWB.6 — SaaS ops tenant provisioning APIs."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api import provisioning as prov
from aos_api.errors import ApiError

router = APIRouter(tags=["ops-saas"])


class ProvisionIn(BaseModel):
    orgId: str
    orgName: str = ""
    ownerSubject: str
    plan: str = "starter"
    quota: dict[str, Any] | None = None


class QuotaIn(BaseModel):
    maxWorkspaces: int | None = None
    maxMembers: int | None = None
    maxStorageGb: int | None = None


@router.get("/v1/ops/tenants")
def list_tenants(principal: Principal = Depends(require_principal)) -> dict:
    prov.require_ops(principal.roles)
    return {"items": prov.list_tenants()}


@router.post("/v1/ops/tenants")
def create_tenant(
    body: ProvisionIn,
    principal: Principal = Depends(require_principal),
) -> dict:
    prov.require_ops(principal.roles)
    return prov.provision_tenant(
        org_id=body.orgId,
        org_name=body.orgName or body.orgId,
        owner_subject=body.ownerSubject,
        plan=body.plan,
        quota=body.quota,
        actor_id=principal.subject,
    )


@router.get("/v1/ops/tenants/{org_id}")
def get_tenant(
    org_id: str,
    principal: Principal = Depends(require_principal),
) -> dict:
    prov.require_ops(principal.roles)
    row = prov.get_tenant(org_id)
    if not row:
        raise ApiError(code="NOT_FOUND", message="tenant not found", status_code=404)
    return row


@router.patch("/v1/ops/tenants/{org_id}/quota")
def patch_tenant_quota(
    org_id: str,
    body: QuotaIn,
    principal: Principal = Depends(require_principal),
) -> dict:
    prov.require_ops(principal.roles)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    return prov.patch_quota(org_id, patch, actor_id=principal.subject)
