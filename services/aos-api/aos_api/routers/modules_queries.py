"""Module queries router — Phase 1 Workshop backend.

GET /v1/modules/:id/queries — query functions list.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from aos_api.auth import require_principal
from aos_api.module_queries import list_queries

router = APIRouter(
    prefix="/v1/modules",
    tags=["modules-queries"],
    dependencies=[Depends(require_principal)],
)


@router.get("/{module_id}/queries")
def list_module_queries(module_id: str) -> dict:
    items = list_queries(module_id)
    return {"moduleId": module_id, "items": items, "count": len(items)}
