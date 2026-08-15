"""Canonical AIP-8 analyst read API."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from aos_api.aip_analyst_contracts import AnalystQueryRequest, QueryResultRevision
from aos_api.aip_analyst_query import AnalystReadAdapters, execute_analyst_query
from aos_api.auth import Principal, require_principal
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/analyst", tags=["aip-analyst"])


def get_aip_analyst_read_adapters() -> AnalystReadAdapters:
    """Fail-closed default until P8 canonical adapters are assembled."""
    return AnalystReadAdapters()


@router.post("/query", response_model=QueryResultRevision)
def analyst_query(
    body: AnalystQueryRequest,
    principal: Principal = Depends(require_principal),
    adapters: AnalystReadAdapters = Depends(get_aip_analyst_read_adapters),
) -> QueryResultRevision:
    return execute_analyst_query(
        scope=TenantScope(principal.org_id, principal.project_id),
        principal=principal,
        request=body,
        adapters=adapters,
    )


__all__ = ["get_aip_analyst_read_adapters", "router"]
