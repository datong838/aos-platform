"""Trusted dry-run and immutable history endpoints for persisted AIP Logic graphs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from aos_api.aip_logic_dry_run_executor import (
    LogicDryRunExecutor,
    LogicDryRunPreflightError,
)
from aos_api.aip_logic_dry_run_models import (
    LogicDryRun,
    LogicDryRunRequest,
    LogicRunListResponse,
)
from aos_api.aip_logic_graph_models import LogicGraphValidationError
from aos_api.aip_logic_graph_store import (
    LogicGraphIntegrityError,
    LogicGraphNotFound,
    LogicGraphStore,
)
from aos_api.aip_logic_run_store import (
    LogicRunIdempotencyConflict,
    LogicRunNotFound,
    LogicRunPersistenceError,
    LogicRunStore,
)
from aos_api.aip_logic_runtime_adapters import RuntimeAdapterRegistry
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError


class _UnprocessableRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                return await original(request)
            except RequestValidationError as exc:
                safe_errors = [
                    {
                        "loc": [str(part) for part in error.get("loc", ())],
                        "type": str(error.get("type") or "validation_error"),
                        "message": str(error.get("msg") or "invalid value"),
                    }
                    for error in exc.errors()
                ]
                raise ApiError(
                    code=(
                        "LOGIC_DRY_RUN_REQUEST_INVALID"
                        if request.method == "POST"
                        and request.url.path.endswith("/dry-run")
                        else "LOGIC_RUN_QUERY_INVALID"
                    ),
                    message="logic run request validation failed",
                    status_code=422,
                    details={"errors": safe_errors},
                ) from exc

        return handler


router = APIRouter(
    prefix="/v1/aip/logic/graphs",
    tags=["aip-logic-runs"],
    route_class=_UnprocessableRoute,
)
_GRAPH_STORE = LogicGraphStore()
_RUN_STORE = LogicRunStore()
_ADAPTERS = RuntimeAdapterRegistry()
_STALE_RUN_SECONDS = 45


def get_logic_run_graph_store() -> LogicGraphStore:
    return _GRAPH_STORE


def get_logic_run_store() -> LogicRunStore:
    return _RUN_STORE


def get_logic_runtime_adapters() -> RuntimeAdapterRegistry:
    return _ADAPTERS


def _graph_or_404(store: LogicGraphStore, principal: Principal, graph_id: str):
    try:
        return store.get(principal.org_id, principal.project_id, graph_id)
    except LogicGraphNotFound as exc:
        raise ApiError(
            code="LOGIC_GRAPH_NOT_FOUND",
            message="logic graph not found",
            status_code=404,
        ) from exc
    except LogicGraphIntegrityError as exc:
        raise ApiError(
            code=exc.code,
            message="stored logic graph failed checksum verification",
            status_code=500,
        ) from exc


def _history_unavailable(exc: Exception) -> ApiError:
    return ApiError(
        code="LOGIC_RUN_PERSISTENCE_FAILED",
        message="logic run history is unavailable",
        status_code=503,
    )


def _recover_stale_runs(run_store: LogicRunStore, principal: Principal) -> None:
    try:
        run_store.recover_interrupted(
            principal.org_id,
            principal.project_id,
            stale_before=datetime.now(UTC) - timedelta(seconds=_STALE_RUN_SECONDS),
        )
    except LogicRunPersistenceError as exc:
        raise _history_unavailable(exc) from exc


@router.post("/{graph_id}/dry-run", response_model=LogicDryRun)
def dry_run_logic_graph(
    graph_id: str,
    body: LogicDryRunRequest,
    principal: Principal = Depends(require_principal),
    graph_store: LogicGraphStore = Depends(get_logic_run_graph_store),
    run_store: LogicRunStore = Depends(get_logic_run_store),
    adapters: RuntimeAdapterRegistry = Depends(get_logic_runtime_adapters),
) -> LogicDryRun:
    graph = _graph_or_404(graph_store, principal, graph_id)
    if (
        body.expected_revision != graph.revision
        or body.expected_graph_hash != graph.graph_hash
    ):
        raise ApiError(
            code="LOGIC_GRAPH_VERSION_CONFLICT",
            message="saved logic graph revision or hash changed",
            status_code=409,
            details={
                "expected_revision": body.expected_revision,
                "current_revision": graph.revision,
                "expected_graph_hash": body.expected_graph_hash,
                "current_graph_hash": graph.graph_hash,
            },
        )
    executor = LogicDryRunExecutor(adapters)
    try:
        executor.preflight(graph)
    except LogicGraphValidationError as exc:
        raise ApiError(
            code="LOGIC_GRAPH_INVALID",
            message="saved logic graph validation failed",
            status_code=422,
            details={
                "issues": [issue.model_dump(exclude_none=True) for issue in exc.issues]
            },
        ) from exc
    except LogicDryRunPreflightError as exc:
        raise ApiError(
            code=exc.code,
            message=exc.safe_message,
            status_code=422,
            details={"node_id": exc.node_id} if exc.node_id else None,
        ) from exc
    _recover_stale_runs(run_store, principal)
    run_id = f"logic-run-{uuid.uuid4().hex}"
    try:
        started = run_store.start_run(
            principal.org_id,
            principal.project_id,
            principal.subject,
            graph,
            body,
            run_id,
        )
    except LogicRunIdempotencyConflict as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=409) from exc
    except LogicRunPersistenceError as exc:
        raise _history_unavailable(exc) from exc
    if started.replay is not None:
        return started.replay
    assert started.started_at is not None
    result = executor.execute_guarded(
        graph, body.inputs, run_id=started.run_id, started_at=started.started_at
    )
    try:
        run_store.finalize_run(principal.org_id, principal.project_id, result)
        return run_store.get_run(
            principal.org_id, principal.project_id, graph_id, result.run_id
        )
    except LogicRunPersistenceError as exc:
        raise _history_unavailable(exc) from exc


@router.get("/{graph_id}/runs", response_model=LogicRunListResponse)
def list_logic_runs(
    graph_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    before: str | None = Query(default=None, min_length=1, max_length=200),
    principal: Principal = Depends(require_principal),
    graph_store: LogicGraphStore = Depends(get_logic_run_graph_store),
    run_store: LogicRunStore = Depends(get_logic_run_store),
) -> LogicRunListResponse:
    _graph_or_404(graph_store, principal, graph_id)
    _recover_stale_runs(run_store, principal)
    try:
        return run_store.list_runs(
            principal.org_id, principal.project_id, graph_id, limit=limit, before=before
        )
    except LogicRunNotFound as exc:
        raise ApiError(
            code=exc.code, message="logic run not found", status_code=404
        ) from exc
    except LogicRunPersistenceError as exc:
        raise _history_unavailable(exc) from exc


@router.get("/{graph_id}/runs/{run_id}", response_model=LogicDryRun)
def get_logic_run(
    graph_id: str,
    run_id: str,
    principal: Principal = Depends(require_principal),
    graph_store: LogicGraphStore = Depends(get_logic_run_graph_store),
    run_store: LogicRunStore = Depends(get_logic_run_store),
) -> LogicDryRun:
    _graph_or_404(graph_store, principal, graph_id)
    _recover_stale_runs(run_store, principal)
    try:
        return run_store.get_run(
            principal.org_id, principal.project_id, graph_id, run_id
        )
    except LogicRunNotFound as exc:
        raise ApiError(
            code=exc.code, message="logic run not found", status_code=404
        ) from exc
    except LogicRunPersistenceError as exc:
        raise _history_unavailable(exc) from exc
