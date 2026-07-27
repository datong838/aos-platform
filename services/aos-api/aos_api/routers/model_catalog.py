"""Phase 2 · Model Catalog router.

GET    /v1/aip/model-catalog                    — list discoverable models
GET    /v1/aip/model-catalog/:id                — detail
POST   /v1/aip/model-catalog/:id/register       — register into org (with quota)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.model_catalog import (
    delete_catalog,
    get_catalog,
    list_catalog,
)
from aos_api.registered_models import register_model, update_registered

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
) -> dict[str, Any]:
    items = list_catalog(provider=provider, status=status, capability=capability)
    return {"items": items, "count": len(items)}


@router.get("/model-catalog/{model_id}")
def get_catalog_api(model_id: str) -> dict[str, Any]:
    item = get_catalog(model_id)
    if not item:
        raise HTTPException(404, "Model not found in catalog")
    return item


@router.post("/model-catalog/{model_id}/register")
def register_model_api(model_id: str, body: RegisterRequest) -> dict[str, Any]:
    """Register a catalog model into the org with quota."""
    cat = get_catalog(model_id)
    if not cat:
        raise HTTPException(404, "Model not found in catalog")
    payload = {
        "modelId": model_id,
        "alias": body.alias or cat.get("displayName") or cat["model"],
        "quota": body.quota,
        "status": body.status,
    }
    item = register_model(payload)
    return {"ok": True, "item": item}


# Convenience: registered-models list lives here for the "已注册模型（配额/状态）" API
from aos_api.registered_models import list_registered, get_registered, unregister_model  # noqa: E402


@router.get("/registered-models")
def list_registered_api(status: str | None = Query(None)) -> dict[str, Any]:
    items = list_registered(status=status)
    return {"items": items, "count": len(items)}


@router.get("/registered-models/{reg_id}")
def get_registered_api(reg_id: str) -> dict[str, Any]:
    item = get_registered(reg_id)
    if not item:
        raise HTTPException(404, "Registered model not found")
    return item


@router.patch("/registered-models/{reg_id}")
def update_registered_api(reg_id: str, body: dict[str, Any]) -> dict[str, Any]:
    item = update_registered(reg_id, body)
    if not item:
        raise HTTPException(404, "Registered model not found")
    return item


@router.delete("/registered-models/{reg_id}")
def unregister_model_api(reg_id: str) -> dict[str, Any]:
    ok = unregister_model(reg_id)
    if not ok:
        raise HTTPException(404, "Registered model not found")
    return {"ok": True}


# /v1/aip/model-admin/models — flat model list (joins catalog + registered status)
# Uses model-admin prefix to avoid clash with the runtime /v1/aip/models gateway facade.
from aos_api.registered_models import list_registered as _list_registered  # noqa: E402


@router.get("/model-admin/models")
def list_models_api(
    provider: str | None = Query(None),
    status: str | None = Query(None),
) -> dict[str, Any]:
    """Return a unified view: catalog models enriched with registration info."""
    catalog = list_catalog(provider=provider, status=status)
    registered = {r["modelId"]: r for r in _list_registered()}
    items = []
    for c in catalog:
        reg = registered.get(c["id"])
        items.append({
            **c,
            "registered": reg is not None,
            "registration": reg,
        })
    return {"items": items, "count": len(items)}
