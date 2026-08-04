"""Phase 2 · Model Providers router (admin view).

GET /v1/aip/model-admin/providers           — provider list (masked keys + latest health)
GET /v1/aip/model-admin/providers/:id       — provider detail
GET /v1/aip/model-admin/providers/:id/health — latest health snapshot

NOTE: /v1/aip/providers is reserved by the LLM gateway facade (wave_ext);
this admin path is distinct.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from aos_api.auth import Principal, require_principal
from aos_api.model_providers import get_provider, get_provider_health, list_providers
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/model-admin", tags=["aip-providers"])


@router.get("/providers")
def list_providers_api(
    status: str | None = Query(None), principal: Principal = Depends(require_principal)
) -> dict[str, Any]:
    items = list_providers(
        TenantScope(principal.org_id, principal.project_id), status=status
    )
    return {"items": items, "count": len(items)}


@router.get("/providers/{provider_id}")
def get_provider_api(
    provider_id: str, principal: Principal = Depends(require_principal)
) -> dict[str, Any]:
    item = get_provider(
        TenantScope(principal.org_id, principal.project_id), provider_id
    )
    if not item:
        raise HTTPException(404, "Provider not found")
    return item


@router.get("/providers/{provider_id}/health")
def get_provider_health_api(
    provider_id: str, principal: Principal = Depends(require_principal)
) -> dict[str, Any]:
    item = get_provider_health(
        TenantScope(principal.org_id, principal.project_id), provider_id
    )
    if not item:
        raise HTTPException(404, "Provider not found")
    return item
