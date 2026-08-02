"""Atomic PostgreSQL store for immutable, governed AIP Logic publications."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, Protocol

from aos_api.aip_logic_graph_models import (
    LogicGraphContent,
    LogicGraphSnapshot,
    compute_logic_graph_payload_hash,
    require_valid_logic_graph,
)
from aos_api.aip_logic_publication_models import (
    LogicEvalEvidence,
    LogicPublication,
    LogicPublicationGateSummary,
    LogicPublicationListResponse,
    PublishLogicGraphRequest,
)
from aos_api.db import connect as db_connect

ConnectFactory = Callable[[], AbstractContextManager[Any]]


class LogicEvalEvidenceReader(Protocol):
    """Loads durable evidence through the publication transaction's connection."""

    def get_evidence(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        suite_id: str,
        report_id: str,
    ) -> LogicEvalEvidence | None: ...


class LogicPublicationStoreError(RuntimeError):
    code = "LOGIC_PUBLICATION_STORE_ERROR"


class LogicPublicationNotFound(LogicPublicationStoreError):
    code = "LOGIC_PUBLICATION_NOT_FOUND"


class LogicPublicationVersionConflict(LogicPublicationStoreError):
    code = "LOGIC_GRAPH_VERSION_CONFLICT"

    def __init__(
        self,
        *,
        expected_revision: int,
        expected_graph_hash: str,
        current_revision: int | None,
        current_graph_hash: str | None,
    ) -> None:
        self.expected_revision = expected_revision
        self.expected_graph_hash = expected_graph_hash
        self.current_revision = current_revision
        self.current_graph_hash = current_graph_hash
        super().__init__("saved logic graph revision or hash changed")


class LogicPublicationIdempotencyConflict(LogicPublicationStoreError):
    code = "LOGIC_PUBLICATION_IDEMPOTENCY_CONFLICT"


class LogicPublicationRevisionConflict(LogicPublicationStoreError):
    code = "LOGIC_GRAPH_REVISION_ALREADY_PUBLISHED"


class LogicPublicationIntegrityError(LogicPublicationStoreError):
    code = "LOGIC_PUBLICATION_INTEGRITY_ERROR"


class LogicPublicationDryRunRequired(LogicPublicationStoreError):
    code = "LOGIC_PUBLICATION_DRY_RUN_REQUIRED"


class LogicPublicationEvalEvidenceRequired(LogicPublicationStoreError):
    code = "LOGIC_PUBLICATION_EVAL_EVIDENCE_REQUIRED"


class LogicPublicationEvalTargetMismatch(LogicPublicationStoreError):
    code = "LOGIC_PUBLICATION_EVAL_TARGET_MISMATCH"


class LogicPublicationEvalGateRejected(LogicPublicationStoreError):
    code = "LOGIC_PUBLICATION_EVAL_GATE_REJECTED"


class LogicPublicationEvalEvidenceExpired(LogicPublicationStoreError):
    code = "LOGIC_PUBLICATION_EVAL_EVIDENCE_EXPIRED"


class LogicPublicationPersistenceError(LogicPublicationStoreError):
    code = "LOGIC_PUBLICATION_PERSISTENCE_ERROR"


class LogicPublicationStore:
    """All publication checks and writes occur in one database transaction."""

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def publish(
        self,
        org_id: str,
        project_id: str,
        actor: str,
        graph_id: str,
        request: PublishLogicGraphRequest,
        evidence_reader: LogicEvalEvidenceReader,
    ) -> LogicPublication:
        self._require_scope(org_id, project_id)
        if not actor.strip() or not graph_id.strip():
            raise ValueError("actor and graph_id are required")
        request_hash = self._request_hash(request)
        try:
            with self._connect_factory() as conn:
                replay = self._find_by_idempotency_key(
                    conn, org_id, project_id, graph_id, request.idempotency_key
                )
                if replay is not None:
                    if str(replay["request_hash"]) != request_hash:
                        raise LogicPublicationIdempotencyConflict(
                            "idempotency key was reused for a different request"
                        )
                    return self._publication_from_row(replay)

                current = conn.execute(
                    """
                    SELECT revision,graph_hash
                    FROM aip_logic_graph
                    WHERE org_id=%s AND project_id=%s AND graph_id=%s
                      AND deleted_at IS NULL
                    FOR UPDATE
                    """,
                    (org_id, project_id, graph_id),
                ).fetchone()
                if current is None:
                    raise LogicPublicationNotFound(
                        f"logic graph {graph_id} not found"
                    )
                current_revision = int(current["revision"])
                current_hash = str(current["graph_hash"])
                if (
                    current_revision != request.expected_revision
                    or current_hash != request.expected_graph_hash
                ):
                    raise LogicPublicationVersionConflict(
                        expected_revision=request.expected_revision,
                        expected_graph_hash=request.expected_graph_hash,
                        current_revision=current_revision,
                        current_graph_hash=current_hash,
                    )

                existing = self._find_by_revision(
                    conn, org_id, project_id, graph_id, request.expected_revision
                )
                if existing is not None:
                    if str(existing["request_hash"]) == request_hash:
                        return self._publication_from_row(existing)
                    raise LogicPublicationRevisionConflict(
                        "logic graph revision is already published with other evidence"
                    )

                revision = conn.execute(
                    """
                    SELECT graph_hash,snapshot
                    FROM aip_logic_graph_revision
                    WHERE org_id=%s AND project_id=%s AND graph_id=%s AND revision=%s
                    """,
                    (org_id, project_id, graph_id, request.expected_revision),
                ).fetchone()
                if revision is None:
                    raise LogicPublicationIntegrityError(
                        "immutable logic graph revision is missing"
                    )
                snapshot = self._validated_snapshot(
                    revision["snapshot"],
                    graph_id=graph_id,
                    expected_revision=request.expected_revision,
                    expected_hash=request.expected_graph_hash,
                    stored_hash=str(revision["graph_hash"]),
                )

                dry_run = conn.execute(
                    """
                    SELECT run_id
                    FROM aip_logic_graph_runs
                    WHERE org_id=%s AND project_id=%s AND graph_id=%s
                      AND evaluated_revision=%s AND graph_hash=%s
                      AND mode='dry_run' AND status='succeeded'
                      AND production_written=FALSE AND finished_at IS NOT NULL
                    ORDER BY finished_at DESC,run_id DESC
                    LIMIT 1
                    """,
                    (
                        org_id,
                        project_id,
                        graph_id,
                        request.expected_revision,
                        request.expected_graph_hash,
                    ),
                ).fetchone()
                if dry_run is None:
                    raise LogicPublicationDryRunRequired(
                        "a successful canonical dry-run is required"
                    )

                evidence = evidence_reader.get_evidence(
                    conn,
                    org_id=org_id,
                    project_id=project_id,
                    suite_id=request.eval_suite_id,
                    report_id=request.eval_report_id,
                )
                self._validate_evidence(
                    evidence,
                    graph_id=graph_id,
                    request=request,
                    now=datetime.now(UTC),
                )
                assert evidence is not None
                eval_gate = LogicPublicationGateSummary(
                    gate_passed=True,
                    pass_rate=evidence.pass_rate,
                    threshold=evidence.threshold,
                    passed=evidence.passed,
                    failed=evidence.failed,
                    total=evidence.total,
                    run_at=evidence.run_at,
                )
                publication_id = f"logic-pub-{uuid.uuid4().hex}"
                row = conn.execute(
                    """
                    INSERT INTO aip_logic_publication (
                      org_id,project_id,publication_id,graph_id,graph_revision,
                      graph_hash,graph_snapshot,dry_run_id,eval_suite_id,
                      eval_report_id,eval_gate,actor,idempotency_key,request_hash,
                      created_at
                    ) VALUES (
                      %s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb,%s,%s,%s,NOW()
                    )
                    RETURNING publication_id,graph_id,graph_revision,graph_hash,
                              graph_snapshot,dry_run_id,eval_suite_id,eval_report_id,
                              eval_gate,actor,request_hash,created_at
                    """,
                    (
                        org_id,
                        project_id,
                        publication_id,
                        graph_id,
                        request.expected_revision,
                        request.expected_graph_hash,
                        self._json(snapshot.model_dump(mode="json")),
                        str(dry_run["run_id"]),
                        request.eval_suite_id,
                        request.eval_report_id,
                        self._json(eval_gate.model_dump(mode="json")),
                        actor.strip(),
                        request.idempotency_key,
                        request_hash,
                    ),
                ).fetchone()
                updated = conn.execute(
                    """
                    UPDATE aip_logic_graph
                    SET published_version=%s,updated_at=NOW()
                    WHERE org_id=%s AND project_id=%s AND graph_id=%s
                      AND revision=%s AND graph_hash=%s AND deleted_at IS NULL
                    RETURNING graph_id
                    """,
                    (
                        request.expected_revision,
                        org_id,
                        project_id,
                        graph_id,
                        request.expected_revision,
                        request.expected_graph_hash,
                    ),
                ).fetchone()
                if updated is None:
                    raise LogicPublicationVersionConflict(
                        expected_revision=request.expected_revision,
                        expected_graph_hash=request.expected_graph_hash,
                        current_revision=None,
                        current_graph_hash=None,
                    )
                conn.commit()
                return self._publication_from_row(row)
        except LogicPublicationStoreError:
            raise
        except Exception as exc:
            raise LogicPublicationPersistenceError(
                "failed to publish logic graph"
            ) from exc

    def get(
        self,
        org_id: str,
        project_id: str,
        graph_id: str,
        publication_id: str,
    ) -> LogicPublication:
        self._require_scope(org_id, project_id)
        try:
            with self._connect_factory() as conn:
                row = conn.execute(
                    """
                    SELECT publication_id,graph_id,graph_revision,graph_hash,
                           graph_snapshot,dry_run_id,eval_suite_id,eval_report_id,
                           eval_gate,actor,request_hash,created_at
                    FROM aip_logic_publication
                    WHERE org_id=%s AND project_id=%s AND graph_id=%s
                      AND publication_id=%s
                    """,
                    (org_id, project_id, graph_id, publication_id),
                ).fetchone()
            if row is None:
                raise LogicPublicationNotFound("logic publication not found")
            return self._publication_from_row(row)
        except LogicPublicationStoreError:
            raise
        except Exception as exc:
            raise LogicPublicationPersistenceError(
                "failed to read logic publication"
            ) from exc

    def list(
        self, org_id: str, project_id: str, graph_id: str
    ) -> LogicPublicationListResponse:
        self._require_scope(org_id, project_id)
        try:
            with self._connect_factory() as conn:
                graph = conn.execute(
                    """SELECT 1 FROM aip_logic_graph
                       WHERE org_id=%s AND project_id=%s AND graph_id=%s
                         AND deleted_at IS NULL""",
                    (org_id, project_id, graph_id),
                ).fetchone()
                if graph is None:
                    raise LogicPublicationNotFound(
                        f"logic graph {graph_id} not found"
                    )
                rows = conn.execute(
                    """
                    SELECT publication_id,graph_id,graph_revision,graph_hash,
                           graph_snapshot,dry_run_id,eval_suite_id,eval_report_id,
                           eval_gate,actor,request_hash,created_at
                    FROM aip_logic_publication
                    WHERE org_id=%s AND project_id=%s AND graph_id=%s
                    ORDER BY graph_revision DESC,created_at DESC,publication_id DESC
                    """,
                    (org_id, project_id, graph_id),
                ).fetchall()
            items = [self._publication_from_row(row) for row in rows]
            return LogicPublicationListResponse(items=items, count=len(items))
        except LogicPublicationStoreError:
            raise
        except Exception as exc:
            raise LogicPublicationPersistenceError(
                "failed to list logic publications"
            ) from exc

    @staticmethod
    def _find_by_idempotency_key(
        conn: Any, org_id: str, project_id: str, graph_id: str, key: str
    ) -> Any | None:
        return conn.execute(
            """
            SELECT publication_id,graph_id,graph_revision,graph_hash,
                   graph_snapshot,dry_run_id,eval_suite_id,eval_report_id,
                   eval_gate,actor,request_hash,created_at
            FROM aip_logic_publication
            WHERE org_id=%s AND project_id=%s AND graph_id=%s
              AND idempotency_key=%s
            """,
            (org_id, project_id, graph_id, key),
        ).fetchone()

    @staticmethod
    def _find_by_revision(
        conn: Any, org_id: str, project_id: str, graph_id: str, revision: int
    ) -> Any | None:
        return conn.execute(
            """
            SELECT publication_id,graph_id,graph_revision,graph_hash,
                   graph_snapshot,dry_run_id,eval_suite_id,eval_report_id,
                   eval_gate,actor,request_hash,created_at
            FROM aip_logic_publication
            WHERE org_id=%s AND project_id=%s AND graph_id=%s
              AND graph_revision=%s
            """,
            (org_id, project_id, graph_id, revision),
        ).fetchone()

    @classmethod
    def _validated_snapshot(
        cls,
        raw_snapshot: Any,
        *,
        graph_id: str,
        expected_revision: int,
        expected_hash: str,
        stored_hash: str,
    ) -> LogicGraphSnapshot:
        try:
            snapshot = LogicGraphSnapshot.model_validate(dict(raw_snapshot or {}))
        except Exception as exc:
            raise LogicPublicationIntegrityError(
                "immutable logic graph snapshot is invalid"
            ) from exc
        if (
            snapshot.id != graph_id
            or snapshot.revision != expected_revision
            or snapshot.graph_hash != expected_hash
            or stored_hash != expected_hash
        ):
            raise LogicPublicationIntegrityError(
                "immutable logic graph revision metadata mismatch"
            )
        payload = cls._snapshot_content(snapshot)
        if compute_logic_graph_payload_hash(payload) != expected_hash:
            raise LogicPublicationIntegrityError(
                "immutable logic graph revision checksum mismatch"
            )
        try:
            validated_hash = require_valid_logic_graph(
                LogicGraphContent.model_validate(payload)
            )
        except Exception as exc:
            raise LogicPublicationIntegrityError(
                "immutable logic graph revision failed canonical validation"
            ) from exc
        if validated_hash != expected_hash:
            raise LogicPublicationIntegrityError(
                "canonical validation produced a different graph hash"
            )
        return snapshot

    @staticmethod
    def _validate_evidence(
        evidence: LogicEvalEvidence | None,
        *,
        graph_id: str,
        request: PublishLogicGraphRequest,
        now: datetime,
    ) -> None:
        if evidence is None:
            raise LogicPublicationEvalEvidenceRequired(
                "durable Evals evidence was not found"
            )
        if (
            evidence.suite_id != request.eval_suite_id
            or evidence.report_id != request.eval_report_id
            or evidence.target_type != "logic_graph"
            or evidence.target_id != graph_id
            or evidence.target_revision != request.expected_revision
            or evidence.target_hash != request.expected_graph_hash
        ):
            raise LogicPublicationEvalTargetMismatch(
                "Evals evidence does not target the requested logic graph revision"
            )
        if evidence.expires_at is not None and evidence.expires_at <= now:
            raise LogicPublicationEvalEvidenceExpired("Evals evidence has expired")
        if not evidence.gate_passed or evidence.pass_rate < evidence.threshold:
            raise LogicPublicationEvalGateRejected("Evals gate did not pass")

    @classmethod
    def _publication_from_row(cls, row: Any) -> LogicPublication:
        try:
            publication = LogicPublication(
                publication_id=str(row["publication_id"]),
                graph_id=str(row["graph_id"]),
                graph_revision=int(row["graph_revision"]),
                graph_hash=str(row["graph_hash"]),
                graph_snapshot=dict(row["graph_snapshot"] or {}),
                dry_run_id=str(row["dry_run_id"]),
                eval_suite_id=str(row["eval_suite_id"]),
                eval_report_id=str(row["eval_report_id"]),
                eval_gate=dict(row["eval_gate"] or {}),
                actor=str(row["actor"]),
                created_at=row["created_at"],
            )
        except Exception as exc:
            raise LogicPublicationIntegrityError(
                "stored logic publication is invalid"
            ) from exc
        payload = cls._snapshot_content(publication.graph_snapshot)
        if compute_logic_graph_payload_hash(payload) != publication.graph_hash:
            raise LogicPublicationIntegrityError(
                "stored logic publication snapshot checksum mismatch"
            )
        return publication

    @staticmethod
    def _snapshot_content(snapshot: LogicGraphSnapshot) -> dict[str, Any]:
        return {
            "name": snapshot.name,
            "description": snapshot.description,
            "status": snapshot.status,
            "schema_version": snapshot.schema_version,
            "nodes": [node.model_dump(mode="json") for node in snapshot.nodes],
            "edges": [edge.model_dump(mode="json") for edge in snapshot.edges],
            "entry_node_ids": list(snapshot.entry_node_ids),
        }

    @staticmethod
    def _request_hash(request: PublishLogicGraphRequest) -> str:
        payload = request.model_dump(mode="json", exclude={"idempotency_key"})
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    @staticmethod
    def _require_scope(org_id: str, project_id: str) -> None:
        if not org_id or not project_id:
            raise ValueError("org_id and project_id are required")
