"""Canonical AIP-8 Assist API."""
from __future__ import annotations

import json
from collections.abc import Iterable

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse

from aos_api.aip_assist_contracts import (
    AssistStreamEvent,
    AssistThreadSnapshot,
    AssistThreadHistory,
    AssistSubjectOptionList,
    CreateAssistThreadRequest,
    CreateAssistTurnRequest,
)
from aos_api.aip_assist_service import (
    AipAssistAuthorityUnavailable,
    AipAssistService,
    PostgresAipAssistService,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


router = APIRouter(prefix="/v1/aip/assist", tags=["aip-assist"])


def get_aip_assist_service() -> AipAssistService:
    return PostgresAipAssistService()


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _call(operation):
    try:
        return operation()
    except AipAssistAuthorityUnavailable as exc:
        raise ApiError(
            code=exc.code,
            message="Assist authority is unavailable",
            status_code=503,
        ) from exc


@router.get("/subjects", response_model=AssistSubjectOptionList)
def list_assist_subjects(
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    service: AipAssistService = Depends(get_aip_assist_service),
) -> AssistSubjectOptionList:
    return _call(lambda: service.list_subjects(_scope(principal), limit=limit))


@router.post("/threads", response_model=AssistThreadSnapshot)
def create_assist_thread(
    body: CreateAssistThreadRequest,
    principal: Principal = Depends(require_principal),
    service: AipAssistService = Depends(get_aip_assist_service),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
) -> AssistThreadSnapshot:
    return _call(
        lambda: service.create_thread(
            _scope(principal),
            principal,
            body,
            idempotency_key=idempotency_key,
        )
    )


@router.get("/threads/{thread_id}", response_model=AssistThreadSnapshot)
def get_assist_thread(
    thread_id: str,
    principal: Principal = Depends(require_principal),
    service: AipAssistService = Depends(get_aip_assist_service),
) -> AssistThreadSnapshot:
    return _call(lambda: service.get_thread(_scope(principal), thread_id))


@router.get("/threads/{thread_id}/history", response_model=AssistThreadHistory)
def get_assist_thread_history(
    thread_id: str,
    principal: Principal = Depends(require_principal),
    service: AipAssistService = Depends(get_aip_assist_service),
) -> AssistThreadHistory:
    return _call(lambda: service.get_history(_scope(principal), thread_id))


def _sse(events: Iterable[AssistStreamEvent]):
    for event in events:
        payload = event.model_dump(mode="json", by_alias=True)
        data = json.dumps(payload, ensure_ascii=False)
        yield f"event: {event.event_type.value}\ndata: {data}\n\n"


@router.post("/threads/{thread_id}/turns:stream")
def stream_assist_turn(
    thread_id: str,
    body: CreateAssistTurnRequest,
    principal: Principal = Depends(require_principal),
    service: AipAssistService = Depends(get_aip_assist_service),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
) -> StreamingResponse:
    events = _call(
        lambda: service.stream_turn(
            _scope(principal),
            principal,
            thread_id,
            body,
            idempotency_key=idempotency_key,
        )
    )
    return StreamingResponse(_sse(events), media_type="text/event-stream")


__all__ = ["get_aip_assist_service", "router"]
