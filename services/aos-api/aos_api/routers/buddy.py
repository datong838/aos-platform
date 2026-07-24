from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.idempotency import idempotency_store
from aos_api.logging_facade import get_logger, get_trace_id

router = APIRouter(tags=["buddy"])
log = get_logger("aos-api.buddy")


class BuddyAskRequest(BaseModel):
    query: str = Field(min_length=1)
    context: dict[str, Any] | None = None


class BuddyAskResponse(BaseModel):
    answer: str
    traceId: str
    sources: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/v1/buddy/ask", response_model=BuddyAskResponse)
def buddy_ask(
    body: BuddyAskRequest,
    principal: Principal = Depends(require_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> BuddyAskResponse:
    """v0.1 compatible surface — permanent per T-API."""
    if idempotency_key:
        cached = idempotency_store.get(
            principal.org_id, principal.project_id, idempotency_key
        )
        if cached:
            return BuddyAskResponse(**cached["body"])

    tid = get_trace_id()
    log.debug(
        "buddy_ask query_len=%s subject=%s via=aip_facade",
        len(body.query),
        principal.subject,
    )
    # T3.18 — permanent surface delegates to Model Gateway Facade (no vendor SDK)
    from aos_api.routers.wave_ext import aip_chat

    facade = aip_chat({"query": body.query, "context": body.context}, principal)
    result = BuddyAskResponse(
        answer=str(facade.get("answer", "")),
        traceId=tid,
        sources=[{"provider": facade.get("provider"), "route": facade.get("route")}],
    )
    if idempotency_key:
        idempotency_store.put(
            principal.org_id,
            principal.project_id,
            idempotency_key,
            status_code=200,
            body=result.model_dump(),
        )
    return result
