"""Governed immutable publication endpoints for canonical AIP Logic graphs."""
# FastAPI dependency injection intentionally evaluates Depends at import time.
# ruff: noqa: B008

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from aos_api.aip_eval_store import LogicEvalEvidenceReader
from aos_api.aip_logic_publication_models import (
    LogicPublication,
    LogicPublicationListResponse,
    PublishLogicGraphRequest,
    RestoreLogicPublicationRequest,
)
from aos_api.aip_logic_graph_models import LogicGraphSnapshot, ReplaceLogicGraphRequest
from aos_api.aip_logic_graph_store import (
    LogicGraphConflict,
    LogicGraphNotFound,
    LogicGraphStore,
)
from aos_api.aip_logic_publication_store import (
    LogicPublicationDryRunRequired,
    LogicPublicationEvalEvidenceExpired,
    LogicPublicationEvalEvidenceRequired,
    LogicPublicationEvalGateRejected,
    LogicPublicationEvalTargetMismatch,
    LogicPublicationIdempotencyConflict,
    LogicPublicationIntegrityError,
    LogicPublicationNotFound,
    LogicPublicationPersistenceError,
    LogicPublicationRevisionConflict,
    LogicPublicationStore,
    LogicPublicationVersionConflict,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError

router = APIRouter(
    prefix="/v1/aip/logic/graphs",
    tags=["aip-logic-publications"],
)
_STORE = LogicPublicationStore()
_GRAPH_STORE = LogicGraphStore()
_EVIDENCE_READER = LogicEvalEvidenceReader()


def get_logic_publication_store() -> LogicPublicationStore:
    return _STORE


def get_logic_graph_store() -> LogicGraphStore:
    return _GRAPH_STORE


def get_logic_eval_evidence_reader() -> LogicEvalEvidenceReader:
    return _EVIDENCE_READER


def _map_error(exc: Exception) -> ApiError:
    if isinstance(exc, LogicGraphNotFound):
        return ApiError(code="LOGIC_GRAPH_NOT_FOUND", message="logic graph not found", status_code=404)
    if isinstance(exc, LogicGraphConflict):
        return ApiError(
            code="LOGIC_GRAPH_REVISION_CONFLICT",
            message=str(exc),
            status_code=409,
            details={"expected_revision": exc.expected_revision, "current_revision": exc.current_revision},
        )
    if isinstance(exc, LogicPublicationNotFound):
        return ApiError(code=exc.code, message="logic publication not found", status_code=404)
    if isinstance(
        exc,
        (
            LogicPublicationVersionConflict,
            LogicPublicationIdempotencyConflict,
            LogicPublicationRevisionConflict,
        ),
    ):
        details = None
        if isinstance(exc, LogicPublicationVersionConflict):
            details = {
                "expected_revision": exc.expected_revision,
                "expected_graph_hash": exc.expected_graph_hash,
                "current_revision": exc.current_revision,
                "current_graph_hash": exc.current_graph_hash,
            }
        return ApiError(code=exc.code, message=str(exc), status_code=409, details=details)
    if isinstance(
        exc,
        (
            LogicPublicationDryRunRequired,
            LogicPublicationEvalEvidenceRequired,
            LogicPublicationEvalTargetMismatch,
            LogicPublicationEvalGateRejected,
            LogicPublicationEvalEvidenceExpired,
        ),
    ):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    if isinstance(exc, LogicPublicationIntegrityError):
        return ApiError(
            code=exc.code,
            message="logic publication integrity verification failed",
            status_code=500,
        )
    if isinstance(exc, LogicPublicationPersistenceError):
        return ApiError(
            code=exc.code,
            message="logic publication persistence is unavailable",
            status_code=503,
        )
    return ApiError(
        code="LOGIC_PUBLICATION_FAILED",
        message="logic publication failed",
        status_code=500,
    )


@router.post(
    "/{graph_id}/publish",
    response_model=LogicPublication,
    status_code=status.HTTP_201_CREATED,
)
def publish_logic_graph(
    graph_id: str,
    body: PublishLogicGraphRequest,
    principal: Principal = Depends(require_principal),
    store: LogicPublicationStore = Depends(get_logic_publication_store),
    evidence_reader: LogicEvalEvidenceReader = Depends(get_logic_eval_evidence_reader),
) -> LogicPublication:
    try:
        return store.publish(
            principal.org_id,
            principal.project_id,
            principal.subject,
            graph_id,
            body,
            evidence_reader,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/{graph_id}/publications", response_model=LogicPublicationListResponse)
def list_logic_publications(
    graph_id: str,
    principal: Principal = Depends(require_principal),
    store: LogicPublicationStore = Depends(get_logic_publication_store),
) -> LogicPublicationListResponse:
    try:
        return store.list(principal.org_id, principal.project_id, graph_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/{graph_id}/publications/{publication_id}",
    response_model=LogicPublication,
)
def get_logic_publication(
    graph_id: str,
    publication_id: str,
    principal: Principal = Depends(require_principal),
    store: LogicPublicationStore = Depends(get_logic_publication_store),
) -> LogicPublication:
    try:
        return store.get(
            principal.org_id,
            principal.project_id,
            graph_id,
            publication_id,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/{graph_id}/publications/{publication_id}/restore",
    response_model=LogicGraphSnapshot,
)
def restore_logic_publication_as_draft(
    graph_id: str,
    publication_id: str,
    body: RestoreLogicPublicationRequest,
    principal: Principal = Depends(require_principal),
    publication_store: LogicPublicationStore = Depends(get_logic_publication_store),
    graph_store: LogicGraphStore = Depends(get_logic_graph_store),
) -> LogicGraphSnapshot:
    """Copy an immutable release snapshot into a new CAS-protected draft revision."""

    try:
        publication = publication_store.get(
            principal.org_id,
            principal.project_id,
            graph_id,
            publication_id,
        )
        current = graph_store.get(principal.org_id, principal.project_id, graph_id)
        if (
            current.revision != body.expected_revision
            or current.graph_hash != body.expected_graph_hash
        ):
            raise ApiError(
                code="LOGIC_GRAPH_VERSION_CONFLICT",
                message="current graph revision/hash changed; refresh before restoring publication",
                status_code=409,
                details={
                    "expected_revision": body.expected_revision,
                    "expected_graph_hash": body.expected_graph_hash,
                    "current_revision": current.revision,
                    "current_graph_hash": current.graph_hash,
                },
            )
        snapshot = publication.graph_snapshot
        return graph_store.replace(
            principal.org_id,
            principal.project_id,
            graph_id,
            principal.subject,
            ReplaceLogicGraphRequest(
                name=snapshot.name,
                description=snapshot.description,
                status="draft",
                schema_version=snapshot.schema_version,
                nodes=snapshot.nodes,
                edges=snapshot.edges,
                entry_node_ids=snapshot.entry_node_ids,
                expected_revision=current.revision,
            ),
        )
    except ApiError:
        raise
    except Exception as exc:
        raise _map_error(exc) from exc
