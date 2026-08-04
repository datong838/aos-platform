"""Provider Security Router — 222plan Phase A.

供应商安全策略 API：GET/PUT。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.provider_security import get_security_engine

router = APIRouter(
    prefix="/api/models/providers",
    tags=["model-provider-security"],
    dependencies=[Depends(require_principal)],
)

class UpdateSecurityRequest(BaseModel):
    content_filter: bool | None = None
    max_tokens: int | None = None
    qps_limit: int | None = None
    ip_allowlist: list[str] | None = None
    audit_log: bool | None = None
    data_residency: str | None = None


@router.get("/{provider_id}/security")
def get_security(provider_id: str) -> dict[str, Any]:
    return get_security_engine().get_security(provider_id).model_dump()


@router.put("/{provider_id}/security")
def update_security(provider_id: str, req: UpdateSecurityRequest) -> dict[str, Any]:
    sec = get_security_engine().update_security(
        provider_id, **req.model_dump(exclude_none=True)
    )
    return sec.model_dump()
