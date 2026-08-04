"""Phase 2 · Model Catalog router.

GET    /v1/aip/model-catalog                    — list discoverable models
GET    /v1/aip/model-catalog/:id                — detail
POST   /v1/aip/model-catalog/:id/register       — register into org (with quota)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.model_catalog import get_catalog, list_catalog
from aos_api.registered_models import (
    get_registered,
    list_registered,
    register_model,
    unregister_model,
    update_registered,
)
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip", tags=["aip-model-catalog"])


class RegisterRequest(BaseModel):
    alias: str = ""
    quota: dict[str, Any] = {}
    status: str = "enabled"


@router.get("/model-catalog")
def list_catalog_api(
    provider: str | None = Query(None),
    status: str | None = Query(None),
    capability: str | None = Query(None),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    scope = TenantScope(principal.org_id, principal.project_id)
    items = list_catalog(scope, provider=provider, status=status, capability=capability)
    return {"items": items, "count": len(items)}


@router.get("/model-catalog/{model_id}")
def get_catalog_api(
    model_id: str, principal: Principal = Depends(require_principal)
) -> dict[str, Any]:
    item = get_catalog(TenantScope(principal.org_id, principal.project_id), model_id)
    if not item:
        raise HTTPException(404, "Model not found in catalog")
    return item


@router.post("/model-catalog/{model_id}/register")
def register_model_api(
    model_id: str,
    body: RegisterRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """Register a catalog model into the org with quota."""
    scope = TenantScope(principal.org_id, principal.project_id)
    cat = get_catalog(scope, model_id)
    if not cat:
        raise HTTPException(404, "Model not found in catalog")
    payload = {
        "modelId": model_id,
        "alias": body.alias or cat.get("displayName") or cat["model"],
        "quota": body.quota,
        "status": body.status,
    }
    item = register_model(scope, payload)
    return {"ok": True, "item": item}


@router.get("/registered-models")
def list_registered_api(
    status: str | None = Query(None), principal: Principal = Depends(require_principal)
) -> dict[str, Any]:
    items = list_registered(
        TenantScope(principal.org_id, principal.project_id), status=status
    )
    return {"items": items, "count": len(items)}


@router.get("/registered-models/{reg_id}")
def get_registered_api(
    reg_id: str, principal: Principal = Depends(require_principal)
) -> dict[str, Any]:
    item = get_registered(TenantScope(principal.org_id, principal.project_id), reg_id)
    if not item:
        raise HTTPException(404, "Registered model not found")
    return item


@router.patch("/registered-models/{reg_id}")
def update_registered_api(
    reg_id: str, body: dict[str, Any], principal: Principal = Depends(require_principal)
) -> dict[str, Any]:
    item = update_registered(
        TenantScope(principal.org_id, principal.project_id), reg_id, body
    )
    if not item:
        raise HTTPException(404, "Registered model not found")
    return item


@router.delete("/registered-models/{reg_id}")
def unregister_model_api(
    reg_id: str, principal: Principal = Depends(require_principal)
) -> dict[str, Any]:
    ok = unregister_model(TenantScope(principal.org_id, principal.project_id), reg_id)
    if not ok:
        raise HTTPException(404, "Registered model not found")
    return {"ok": True}


@router.get("/model-admin/models")
def list_models_api(
    provider: str | None = Query(None),
    status: str | None = Query(None),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """Return a unified view: catalog models enriched with registration info."""
    scope = TenantScope(principal.org_id, principal.project_id)
    catalog = list_catalog(scope, provider=provider, status=status)
    registered = {r["modelId"]: r for r in list_registered(scope)}
    items = []
    for c in catalog:
        reg = registered.get(c["id"])
        items.append(
            {
                **c,
                "registered": reg is not None,
                "registration": reg,
            }
        )
    return {"items": items, "count": len(items)}
