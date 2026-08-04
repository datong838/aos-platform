"""Module queries router — Phase 1 Workshop backend.

GET /v1/modules/:id/queries — query functions list.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from aos_api.auth import Principal, require_principal
from aos_api.module_queries import list_queries
from aos_api.tenant_scope import TenantScope

router = APIRouter(
    prefix="/v1/modules",
    tags=["modules-queries"],
    dependencies=[Depends(require_principal)],
)


@router.get("/{module_id}/queries")
def list_module_queries(
    module_id: str, principal: Principal = Depends(require_principal)
) -> dict:
    items = list_queries(TenantScope(principal.org_id, principal.project_id), module_id)
    return {"moduleId": module_id, "items": items, "count": len(items)}
