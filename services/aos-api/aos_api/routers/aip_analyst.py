"""Canonical AIP-8 analyst read API."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header

from aos_api.aip_analyst_contracts import (
    AnalystQueryRequest,
    CreateQueryJobRequest,
    QueryJobCommand,
    QueryJobListResponse,
    QueryJobSnapshot,
    QueryResultRevision,
    RecordQueryResultRequest,
)
from aos_api.aip_analyst_query import AnalystReadAdapters, execute_analyst_query
from aos_api.aip_analyst_canonical_adapters import (
    CanonicalKnowledgeReadAdapter,
    CanonicalSemanticReadAdapter,
)
from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.aip_memory_search import AipMemoryKnowledgeSearch
from aos_api.routers.aip_memory_authority import get_aip_memory_search_service
from aos_api.auth import Principal, require_principal
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/analyst", tags=["aip-analyst"])


def get_aip_analyst_read_adapters(
    search_service: Annotated[
        AipMemoryKnowledgeSearch | None,
        Depends(get_aip_memory_search_service),
    ] = None,
) -> AnalystReadAdapters:
    """Assemble only canonical owners; unavailable owners remain blocked."""
    return AnalystReadAdapters(
        semantic=CanonicalSemanticReadAdapter(),
        knowledge=(
            CanonicalKnowledgeReadAdapter(search_service)
            if search_service is not None
            else None
        ),
        metric=None,
    )


def get_aip_analyst_query_store() -> AipAnalystQueryStore:
    return AipAnalystQueryStore()


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


@router.post("/query-jobs", response_model=QueryJobSnapshot)
def create_query_job(
    body: CreateQueryJobRequest,
    principal: Principal = Depends(require_principal),
    store: AipAnalystQueryStore = Depends(get_aip_analyst_query_store),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
) -> QueryJobSnapshot:
    return store.create(
        TenantScope(principal.org_id, principal.project_id),
        body,
        idempotency_key=idempotency_key,
        actor=principal.subject,
    )


@router.get("/query-jobs", response_model=QueryJobListResponse)
def list_query_jobs(
    limit: int = 50,
    principal: Principal = Depends(require_principal),
    store: AipAnalystQueryStore = Depends(get_aip_analyst_query_store),
) -> QueryJobListResponse:
    return store.list_jobs(
        TenantScope(principal.org_id, principal.project_id), limit=limit
    )


@router.get("/query-jobs/{query_id}", response_model=QueryJobSnapshot)
def get_query_job(
    query_id: str,
    principal: Principal = Depends(require_principal),
    store: AipAnalystQueryStore = Depends(get_aip_analyst_query_store),
) -> QueryJobSnapshot:
    return store.get(TenantScope(principal.org_id, principal.project_id), query_id)


def _command(
    operation: str,
    query_id: str,
    body: QueryJobCommand,
    principal: Principal,
    store: AipAnalystQueryStore,
    key: str,
) -> QueryJobSnapshot:
    return store.command(
        TenantScope(principal.org_id, principal.project_id),
        query_id,
        operation,
        body,
        idempotency_key=key,
        actor=principal.subject,
    )


@router.post("/query-jobs/{query_id}/start", response_model=QueryJobSnapshot)
def start_query_job(
    query_id: str,
    body: QueryJobCommand,
    principal: Principal = Depends(require_principal),
    store: AipAnalystQueryStore = Depends(get_aip_analyst_query_store),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
) -> QueryJobSnapshot:
    return _command("start", query_id, body, principal, store, idempotency_key)


@router.post("/query-jobs/{query_id}/result", response_model=QueryJobSnapshot)
def record_query_result(
    query_id: str,
    body: RecordQueryResultRequest,
    principal: Principal = Depends(require_principal),
    store: AipAnalystQueryStore = Depends(get_aip_analyst_query_store),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
) -> QueryJobSnapshot:
    return store.record_result(
        TenantScope(principal.org_id, principal.project_id),
        query_id,
        body,
        idempotency_key=idempotency_key,
        actor=principal.subject,
    )


@router.post("/query-jobs/{query_id}/cancel", response_model=QueryJobSnapshot)
def cancel_query_job(
    query_id: str,
    body: QueryJobCommand,
    principal: Principal = Depends(require_principal),
    store: AipAnalystQueryStore = Depends(get_aip_analyst_query_store),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
) -> QueryJobSnapshot:
    return _command("cancel", query_id, body, principal, store, idempotency_key)


@router.post("/query-jobs/{query_id}/timeout", response_model=QueryJobSnapshot)
def timeout_query_job(
    query_id: str,
    body: QueryJobCommand,
    principal: Principal = Depends(require_principal),
    store: AipAnalystQueryStore = Depends(get_aip_analyst_query_store),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
) -> QueryJobSnapshot:
    return _command("timeout", query_id, body, principal, store, idempotency_key)


@router.post("/query-jobs/{query_id}/fail", response_model=QueryJobSnapshot)
def fail_query_job(
    query_id: str,
    body: QueryJobCommand,
    principal: Principal = Depends(require_principal),
    store: AipAnalystQueryStore = Depends(get_aip_analyst_query_store),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
) -> QueryJobSnapshot:
    return _command("fail", query_id, body, principal, store, idempotency_key)


@router.post("/query-jobs/{query_id}/reconcile", response_model=QueryJobSnapshot)
def reconcile_query_job(
    query_id: str,
    body: QueryJobCommand,
    principal: Principal = Depends(require_principal),
    store: AipAnalystQueryStore = Depends(get_aip_analyst_query_store),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
) -> QueryJobSnapshot:
    return _command("reconcile", query_id, body, principal, store, idempotency_key)


__all__ = ["get_aip_analyst_query_store", "get_aip_analyst_read_adapters", "router"]
