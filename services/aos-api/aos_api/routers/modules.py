from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.idempotency import idempotency_store
from aos_api.logging_facade import get_logger
from aos_api.marking import ensure_markings
from aos_api import module_store

router = APIRouter(tags=["modules"])
log = get_logger("aos-api.modules")


class CreateModuleRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    objectType: str | None = None
    markings: list[str] | None = None
    entryPath: str | None = None
    # 75 W1: may be string[] (legacy) or layout node objects
    widgets: list[Any] | None = None
    buddyBound: bool | None = None


class PatchModuleRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    objectType: str | None = None
    markings: list[str] | None = None
    entryPath: str | None = None
    widgets: list[Any] | None = None
    buddyBound: bool | None = None
    status: str | None = None


def _visible(principal: Principal, mod: dict[str, Any]) -> bool:
    if "admin" in principal.roles:
        return True
    try:
        ensure_markings(principal, mod.get("markings") or ["public"])
        return True
    except ApiError:
        return False


@router.get("/v1/modules")
def list_modules(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    items = module_store.list_modules(principal.org_id, principal.project_id)
    visible = [m for m in items if _visible(principal, m)]
    log.info(
        "list_modules store=pg visible=%s subject=%s org=%s project=%s",
        len(visible),
        principal.subject,
        principal.org_id,
        principal.project_id,
    )
    return {"items": visible, "store": "postgres"}


@router.post("/v1/modules")
def create_module(
    body: CreateModuleRequest,
    principal: Principal = Depends(require_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    if idempotency_key:
        cached = idempotency_store.get(
            principal.org_id, principal.project_id, idempotency_key
        )
        if cached:
            return JSONResponse(
                status_code=cached["status_code"],
                content={**cached["body"], "idempotentReplay": True},
            )
    created = module_store.create_module(
        body.model_dump(),
        org_id=principal.org_id,
        project_id=principal.project_id,
    )
    if idempotency_key:
        idempotency_store.put(
            principal.org_id,
            principal.project_id,
            idempotency_key,
            status_code=201,
            body=created,
        )
    return JSONResponse(status_code=201, content=created)


@router.get("/v1/modules/{module_id}")
def get_module(
    module_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    mod = module_store.get_module(
        module_id, principal.org_id, principal.project_id
    )
    if not mod:
        raise ApiError(code="NOT_FOUND", message=f"module {module_id} not found", status_code=404)
    ensure_markings(principal, mod.get("markings") or ["public"])
    return mod


@router.patch("/v1/modules/{module_id}")
def patch_module(
    module_id: str,
    body: PatchModuleRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    mod = module_store.get_module(
        module_id, principal.org_id, principal.project_id
    )
    if not mod:
        raise ApiError(code="NOT_FOUND", message=f"module {module_id} not found", status_code=404)
    ensure_markings(principal, mod.get("markings") or ["public"])
    updated = module_store.update_module(
        module_id,
        body.model_dump(exclude_unset=True),
        org_id=principal.org_id,
        project_id=principal.project_id,
    )
    assert updated is not None
    return updated


@router.post("/v1/modules/{module_id}/publish")
def publish_module(
    module_id: str,
    principal: Principal = Depends(require_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    """T-API · Apollo Publish Adapter (Lite)."""
    if idempotency_key:
        cached = idempotency_store.get(
            principal.org_id, principal.project_id, idempotency_key
        )
        if cached:
            return JSONResponse(
                status_code=cached["status_code"],
                content={**cached["body"], "idempotentReplay": True},
            )
    mod = module_store.get_module(
        module_id, principal.org_id, principal.project_id
    )
    if not mod:
        raise ApiError(code="NOT_FOUND", message=f"module {module_id} not found", status_code=404)
    ensure_markings(principal, mod.get("markings") or ["public"])
    published = module_store.publish_module(
        module_id, org_id=principal.org_id, project_id=principal.project_id
    )
    assert published is not None
    log.info(
        "module_publish id=%s subject=%s org=%s project=%s",
        module_id,
        principal.subject,
        principal.org_id,
        principal.project_id,
    )
    if idempotency_key:
        idempotency_store.put(
            principal.org_id,
            principal.project_id,
            idempotency_key,
            status_code=200,
            body=published,
        )
    return JSONResponse(status_code=200, content=published)


@router.get("/v1/modules/{module_id}/runtime")
def get_runtime(
    module_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    mod = module_store.get_module(
        module_id, principal.org_id, principal.project_id
    )
    if not mod:
        raise ApiError(code="NOT_FOUND", message=f"module {module_id} not found", status_code=404)
    ensure_markings(principal, mod.get("markings") or ["public"])
    rt = module_store.module_runtime(
        module_id, org_id=principal.org_id, project_id=principal.project_id
    )
    if not rt:
        raise ApiError(code="NOT_FOUND", message=f"module {module_id} not found", status_code=404)
    return rt
