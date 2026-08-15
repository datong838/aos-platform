"""AIP-8 governed analyst read orchestration.

The old Northampton process-local SQL engine was intentionally removed.  This
module accepts typed requests and delegates only to explicitly injected,
tenant-scoped canonical read adapters.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from typing import Protocol

from aos_api.aip_analyst_contracts import (
    AnalystQueryKind,
    AnalystQueryRequest,
    AnalystQueryStatus,
    KnowledgeQueryRequest,
    MetricQueryRequest,
    QueryBlocker,
    QueryColumn,
    QueryResultRevision,
    QueryRow,
    QuerySourceRef,
    SemanticQueryRequest,
)
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class AdapterResult:
    status: AnalystQueryStatus
    columns: list[QueryColumn]
    rows: list[QueryRow]
    source_refs: list[QuerySourceRef]
    lineage_refs: list[ResourceRef]
    uncertainties: list[str]


class SemanticReadAdapter(Protocol):
    def execute(
        self, scope: TenantScope, principal: Principal, request: SemanticQueryRequest
    ) -> AdapterResult: ...


class KnowledgeReadAdapter(Protocol):
    def execute(
        self, scope: TenantScope, principal: Principal, request: KnowledgeQueryRequest
    ) -> AdapterResult: ...


class MetricReadAdapter(Protocol):
    def execute(
        self, scope: TenantScope, principal: Principal, request: MetricQueryRequest
    ) -> AdapterResult: ...


@dataclass(frozen=True)
class AnalystReadAdapters:
    semantic: SemanticReadAdapter | None = None
    knowledge: KnowledgeReadAdapter | None = None
    metric: MetricReadAdapter | None = None


def _canonical(value: object) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", by_alias=True)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _blocked(
    scope: TenantScope,
    request: AnalystQueryRequest,
    *,
    code: str,
    message: str,
) -> QueryResultRevision:
    created_at = datetime.now(UTC)
    request_hash = sha256(_canonical(request)).hexdigest()
    payload = {
        "scope": scope.key,
        "requestHash": request_hash,
        "status": AnalystQueryStatus.BLOCKED.value,
        "blocker": code,
    }
    return QueryResultRevision(
        tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
        query_id=f"qry-{request_hash[:24]}",
        revision=1,
        kind=AnalystQueryKind(request.kind),
        status=AnalystQueryStatus.BLOCKED,
        blockers=[QueryBlocker(code=code, message=message, retryable=True)],
        cutoff_at=request.cutoff_at,
        content_hash=sha256(_canonical(payload)).hexdigest(),
        created_at=created_at,
    )


def _adapter_for(
    request: AnalystQueryRequest, adapters: AnalystReadAdapters
) -> SemanticReadAdapter | KnowledgeReadAdapter | MetricReadAdapter | None:
    if request.kind == AnalystQueryKind.SEMANTIC:
        return adapters.semantic
    if request.kind == AnalystQueryKind.KNOWLEDGE:
        return adapters.knowledge
    return adapters.metric


def execute_analyst_query(
    *,
    scope: TenantScope,
    principal: Principal,
    request: AnalystQueryRequest,
    adapters: AnalystReadAdapters,
) -> QueryResultRevision:
    """Execute one typed read without accepting client tenant or arbitrary SQL."""
    if scope.key != (principal.org_id, principal.project_id):
        raise ValueError("principal and query scope must match")
    adapter = _adapter_for(request, adapters)
    if adapter is None:
        return _blocked(
            scope,
            request,
            code=f"{request.kind.value.upper()}_ADAPTER_UNAVAILABLE",
            message=f"canonical {request.kind.value} query adapter is unavailable",
        )
    result = adapter.execute(scope, principal, request)  # type: ignore[arg-type]
    if result.status == AnalystQueryStatus.BLOCKED:
        raise ValueError("canonical adapters must raise or return a non-blocked result")
    if result.status == AnalystQueryStatus.EMPTY and result.rows:
        raise ValueError("empty adapter result must not contain rows")
    request_hash = sha256(_canonical(request)).hexdigest()
    created_at = datetime.now(UTC)
    payload = {
        "scope": scope.key,
        "requestHash": request_hash,
        "status": result.status.value,
        "columns": [item.model_dump(mode="json", by_alias=True) for item in result.columns],
        "rows": [item.model_dump(mode="json", by_alias=True) for item in result.rows],
        "sources": [item.model_dump(mode="json", by_alias=True) for item in result.source_refs],
        "lineage": [item.model_dump(mode="json", by_alias=True) for item in result.lineage_refs],
        "uncertainties": result.uncertainties,
    }
    return QueryResultRevision(
        tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
        query_id=f"qry-{request_hash[:24]}",
        revision=1,
        kind=AnalystQueryKind(request.kind),
        status=result.status,
        columns=result.columns,
        rows=result.rows,
        source_refs=result.source_refs,
        lineage_refs=result.lineage_refs,
        uncertainties=result.uncertainties,
        cutoff_at=request.cutoff_at,
        content_hash=sha256(_canonical(payload)).hexdigest(),
        created_at=created_at,
    )


__all__ = [
    "AdapterResult",
    "AnalystReadAdapters",
    "KnowledgeReadAdapter",
    "MetricReadAdapter",
    "SemanticReadAdapter",
    "execute_analyst_query",
]
