"""PostgreSQL current-snapshot and immutable-revision store for AIP Logic graphs."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from aos_api.aip_logic_graph_models import (
    CreateLogicGraphRequest,
    LogicGraphSnapshot,
    ReplaceLogicGraphRequest,
    compute_logic_graph_payload_hash,
    logic_graph_content_payload,
    require_valid_logic_graph,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[[], AbstractContextManager[Any]]


class LogicGraphStoreError(RuntimeError):
    code = "LOGIC_GRAPH_STORE_ERROR"


class LogicGraphNotFound(LogicGraphStoreError):
    code = "LOGIC_GRAPH_NOT_FOUND"


class LogicGraphConflict(LogicGraphStoreError):
    code = "LOGIC_GRAPH_REVISION_CONFLICT"

    def __init__(self, expected_revision: int, current_revision: int | None) -> None:
        self.expected_revision = expected_revision
        self.current_revision = current_revision
        super().__init__(
            f"expected revision {expected_revision}, current revision is {current_revision}"
        )


class LogicGraphIntegrityError(LogicGraphStoreError):
    code = "LOGIC_GRAPH_CHECKSUM_MISMATCH"


class LogicGraphStore:
    """Stateless store; every read comes from PostgreSQL and survives API restart."""

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def create(
        self,
        org_id: str,
        project_id: str,
        actor: str,
        request: CreateLogicGraphRequest,
    ) -> LogicGraphSnapshot:
        self._require_scope(org_id, project_id)
        graph_hash = require_valid_logic_graph(request)
        graph_id = (request.id or f"lg-{uuid.uuid4().hex[:16]}").strip()
        payload = logic_graph_content_payload(request)
        with self._connect(org_id, project_id) as conn:
            row = conn.execute(
                """
                INSERT INTO aip_logic_graph (
                  org_id, project_id, graph_id, name, description, status,
                  schema_version, revision, published_version, graph_hash, payload,
                  created_at, updated_at, deleted_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,1,NULL,%s,%s::jsonb,NOW(),NOW(),NULL)
                ON CONFLICT (org_id, project_id, graph_id) DO NOTHING
                RETURNING graph_id, name, description, status, schema_version,
                          revision, published_version, graph_hash, payload,
                          created_at, updated_at
                """,
                (
                    org_id,
                    project_id,
                    graph_id,
                    request.name,
                    request.description,
                    request.status,
                    request.schema_version,
                    graph_hash,
                    json.dumps(payload, ensure_ascii=False),
                ),
            ).fetchone()
            if row is None:
                current = self._current_revision(conn, org_id, project_id, graph_id)
                raise LogicGraphConflict(0, current)
            snapshot = self._snapshot_from_current_row(row)
            self._insert_revision(conn, org_id, project_id, actor, snapshot)
            conn.commit()
        return snapshot

    def list(self, org_id: str, project_id: str) -> list[LogicGraphSnapshot]:
        self._require_scope(org_id, project_id)
        with self._connect(org_id, project_id) as conn:
            rows = conn.execute(
                """
                SELECT graph_id, name, description, status, schema_version,
                       revision, published_version, graph_hash, payload,
                       created_at, updated_at
                FROM aip_logic_graph
                WHERE org_id=%s AND project_id=%s AND deleted_at IS NULL
                ORDER BY updated_at DESC, graph_id ASC
                """,
                (org_id, project_id),
            ).fetchall()
        return [self._snapshot_from_current_row(row) for row in rows]

    def get(self, org_id: str, project_id: str, graph_id: str) -> LogicGraphSnapshot:
        self._require_scope(org_id, project_id)
        with self._connect(org_id, project_id) as conn:
            row = conn.execute(
                """
                SELECT graph_id, name, description, status, schema_version,
                       revision, published_version, graph_hash, payload,
                       created_at, updated_at
                FROM aip_logic_graph
                WHERE org_id=%s AND project_id=%s AND graph_id=%s
                  AND deleted_at IS NULL
                """,
                (org_id, project_id, graph_id),
            ).fetchone()
        if row is None:
            raise LogicGraphNotFound(f"logic graph {graph_id} not found")
        return self._snapshot_from_current_row(row)

    def replace(
        self,
        org_id: str,
        project_id: str,
        graph_id: str,
        actor: str,
        request: ReplaceLogicGraphRequest,
    ) -> LogicGraphSnapshot:
        self._require_scope(org_id, project_id)
        graph_hash = require_valid_logic_graph(request)
        payload = logic_graph_content_payload(request)
        with self._connect(org_id, project_id) as conn:
            row = conn.execute(
                """
                UPDATE aip_logic_graph
                SET name=%s,
                    description=%s,
                    status=%s,
                    schema_version=%s,
                    revision=revision+1,
                    graph_hash=%s,
                    payload=%s::jsonb,
                    updated_at=NOW()
                WHERE org_id=%s AND project_id=%s AND graph_id=%s
                  AND deleted_at IS NULL AND revision=%s
                RETURNING graph_id, name, description, status, schema_version,
                          revision, published_version, graph_hash, payload,
                          created_at, updated_at
                """,
                (
                    request.name,
                    request.description,
                    request.status,
                    request.schema_version,
                    graph_hash,
                    json.dumps(payload, ensure_ascii=False),
                    org_id,
                    project_id,
                    graph_id,
                    request.expected_revision,
                ),
            ).fetchone()
            if row is None:
                current = self._current_revision(conn, org_id, project_id, graph_id)
                if current is None:
                    raise LogicGraphNotFound(f"logic graph {graph_id} not found")
                raise LogicGraphConflict(request.expected_revision, current)
            snapshot = self._snapshot_from_current_row(row)
            self._insert_revision(conn, org_id, project_id, actor, snapshot)
            conn.commit()
        return snapshot

    def list_revisions(
        self, org_id: str, project_id: str, graph_id: str
    ) -> list[LogicGraphSnapshot]:
        self._require_scope(org_id, project_id)
        with self._connect(org_id, project_id) as conn:
            exists = self._current_revision(conn, org_id, project_id, graph_id)
            if exists is None:
                raise LogicGraphNotFound(f"logic graph {graph_id} not found")
            rows = conn.execute(
                """
                SELECT snapshot, graph_hash
                FROM aip_logic_graph_revision
                WHERE org_id=%s AND project_id=%s AND graph_id=%s
                ORDER BY revision ASC
                """,
                (org_id, project_id, graph_id),
            ).fetchall()
        snapshots: list[LogicGraphSnapshot] = []
        for row in rows:
            snapshot = LogicGraphSnapshot.model_validate(dict(row["snapshot"] or {}))
            self._verify_hash(
                self._content_from_snapshot(snapshot), str(row["graph_hash"])
            )
            snapshots.append(snapshot)
        return snapshots

    def _insert_revision(
        self,
        conn: Any,
        org_id: str,
        project_id: str,
        actor: str,
        snapshot: LogicGraphSnapshot,
    ) -> None:
        conn.execute(
            """
            INSERT INTO aip_logic_graph_revision (
              org_id, project_id, graph_id, revision, graph_hash, snapshot, actor,
              created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,NOW())
            """,
            (
                org_id,
                project_id,
                snapshot.id,
                snapshot.revision,
                snapshot.graph_hash,
                json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False),
                actor,
            ),
        )

    @staticmethod
    def _current_revision(
        conn: Any, org_id: str, project_id: str, graph_id: str
    ) -> int | None:
        row = conn.execute(
            """
            SELECT revision FROM aip_logic_graph
            WHERE org_id=%s AND project_id=%s AND graph_id=%s
              AND deleted_at IS NULL
            """,
            (org_id, project_id, graph_id),
        ).fetchone()
        return int(row["revision"]) if row else None

    @classmethod
    def _snapshot_from_current_row(cls, row: Any) -> LogicGraphSnapshot:
        payload = dict(row["payload"] or {})
        cls._verify_hash(payload, str(row["graph_hash"]))
        for field in ("name", "description", "status", "schema_version"):
            if payload.get(field) != row[field]:
                raise LogicGraphIntegrityError(
                    f"logic graph current metadata mismatch: {field}"
                )
        return LogicGraphSnapshot(
            id=str(row["graph_id"]),
            name=str(row["name"]),
            description=str(row["description"]),
            status=str(row["status"]),
            schema_version=int(row["schema_version"]),
            revision=int(row["revision"]),
            published_version=(
                int(row["published_version"])
                if row["published_version"] is not None
                else None
            ),
            graph_hash=str(row["graph_hash"]),
            nodes=payload.get("nodes") or [],
            edges=payload.get("edges") or [],
            entry_node_ids=payload.get("entry_node_ids") or [],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            persisted=True,
        )

    @staticmethod
    def _content_from_snapshot(snapshot: LogicGraphSnapshot) -> dict[str, Any]:
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
    def _verify_hash(payload: dict[str, Any], expected_hash: str) -> None:
        actual_hash = compute_logic_graph_payload_hash(payload)
        if actual_hash != expected_hash:
            raise LogicGraphIntegrityError("logic graph checksum mismatch")

    @staticmethod
    def _require_scope(org_id: str, project_id: str) -> None:
        if not org_id or not project_id:
            raise ValueError("org_id and project_id are required")

    def _connect(self, org_id: str, project_id: str) -> AbstractContextManager[Any]:
        if self._connect_factory is db_connect:
            return db_connect(TenantScope(org_id, project_id))
        return self._connect_factory()
