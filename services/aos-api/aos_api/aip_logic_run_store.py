"""Transactional PostgreSQL history store for AIP Logic dry-runs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_logic_dry_run_models import (
    LogicDryRun,
    LogicDryRunRequest,
    LogicNodeCounts,
    LogicNodeResult,
    LogicRunListResponse,
    LogicRunSummary,
    sanitize_runtime_value,
)
from aos_api.aip_logic_graph_models import LogicGraphSnapshot
from aos_api.db import connect as db_connect

ConnectFactory = Callable[[], AbstractContextManager[Any]]


class LogicRunStoreError(RuntimeError):
    code = "LOGIC_RUN_STORE_ERROR"


class LogicRunNotFound(LogicRunStoreError):
    code = "LOGIC_RUN_NOT_FOUND"


class LogicRunPersistenceError(LogicRunStoreError):
    code = "LOGIC_RUN_PERSISTENCE_FAILED"


class LogicRunIdempotencyConflict(LogicRunStoreError):
    code = "LOGIC_RUN_IDEMPOTENCY_CONFLICT"


@dataclass(frozen=True)
class LogicRunStart:
    run_id: str
    started_at: datetime | None = None
    replay: LogicDryRun | None = None


class LogicRunStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def start_run(
        self,
        org_id: str,
        project_id: str,
        actor: str,
        graph: LogicGraphSnapshot,
        request: LogicDryRunRequest,
        run_id: str,
    ) -> LogicRunStart:
        self._scope(org_id, project_id)
        safe_inputs, _ = sanitize_runtime_value(request.inputs, max_bytes=256 * 1024)
        request_hash = self._request_hash(request)
        try:
            with self._connect_factory() as conn:
                row = conn.execute(
                    """
                    INSERT INTO aip_logic_graph_runs (
                      org_id,project_id,graph_id,run_id,evaluated_revision,graph_hash,
                      mode,status,production_written,started_at,inputs_snapshot,actor,
                      idempotency_key,request_hash
                    ) VALUES (%s,%s,%s,%s,%s,%s,'dry_run','running',FALSE,NOW(),%s::jsonb,%s,%s,%s)
                    ON CONFLICT (org_id,project_id,graph_id,idempotency_key)
                      WHERE idempotency_key IS NOT NULL DO NOTHING
                    RETURNING run_id,started_at
                    """,
                    (
                        org_id,
                        project_id,
                        graph.id,
                        run_id,
                        graph.revision,
                        graph.graph_hash,
                        self._json(safe_inputs),
                        actor,
                        request.idempotency_key,
                        request_hash,
                    ),
                ).fetchone()
                if row is not None:
                    conn.commit()
                    return LogicRunStart(run_id=run_id, started_at=row["started_at"])
                existing = conn.execute(
                    """SELECT run_id,request_hash,status FROM aip_logic_graph_runs
                       WHERE org_id=%s AND project_id=%s AND graph_id=%s AND idempotency_key=%s""",
                    (org_id, project_id, graph.id, request.idempotency_key),
                ).fetchone()
                if existing is None or str(existing["request_hash"]) != request_hash:
                    raise LogicRunIdempotencyConflict(
                        "idempotency key was reused for a different request"
                    )
                if existing["status"] == "running":
                    raise LogicRunIdempotencyConflict(
                        "idempotent dry-run is still running"
                    )
                replay = self._get_with_conn(
                    conn, org_id, project_id, graph.id, str(existing["run_id"])
                )
                return LogicRunStart(
                    run_id=replay.run_id, started_at=replay.started_at, replay=replay
                )
        except LogicRunStoreError:
            raise
        except Exception as exc:
            raise LogicRunPersistenceError("failed to start logic run history") from exc

    def finalize_run(self, org_id: str, project_id: str, result: LogicDryRun) -> None:
        self._scope(org_id, project_id)
        try:
            with self._connect_factory() as conn:
                for index, node in enumerate(result.node_results):
                    conn.execute(
                        """
                        INSERT INTO aip_logic_graph_run_nodes (
                          org_id,project_id,graph_id,run_id,node_id,topo_index,kind,status,
                          started_at,finished_at,elapsed_ms,summary,output_summary,usage,
                          tool_call,selected_branch_path,proposed_edits,error,truncated
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s)
                        """,
                        (
                            org_id,
                            project_id,
                            result.graph_id,
                            result.run_id,
                            node.node_id,
                            index,
                            node.kind,
                            node.status,
                            node.started_at,
                            node.finished_at,
                            node.elapsed_ms,
                            node.summary,
                            self._json(node.output)
                            if node.output is not None
                            else None,
                            self._json(node.usage.model_dump(mode="json"))
                            if node.usage
                            else None,
                            self._json(node.tool_call.model_dump(mode="json"))
                            if node.tool_call
                            else None,
                            node.selected_branch_path,
                            self._json(
                                [
                                    edit.model_dump(mode="json")
                                    for edit in node.proposed_edits
                                ]
                            ),
                            self._json(node.error.model_dump(mode="json"))
                            if node.error
                            else None,
                            node.truncated,
                        ),
                    )
                row = conn.execute(
                    """
                    UPDATE aip_logic_graph_runs
                    SET status=%s,finished_at=%s,elapsed_ms=%s,total_tokens=%s,
                        output_summary=%s::jsonb,proposed_edits=%s::jsonb,error=%s::jsonb
                    WHERE org_id=%s AND project_id=%s AND graph_id=%s AND run_id=%s
                      AND status='running'
                    RETURNING run_id
                    """,
                    (
                        result.status,
                        result.finished_at,
                        result.elapsed_ms,
                        result.total_tokens,
                        self._json(
                            {
                                "status": result.status,
                                "node_count": len(result.node_results),
                                "proposed_edit_count": len(result.proposed_edits),
                            }
                        ),
                        self._json(
                            [
                                edit.model_dump(mode="json")
                                for edit in result.proposed_edits
                            ]
                        ),
                        self._json(result.error.model_dump(mode="json"))
                        if result.error
                        else None,
                        org_id,
                        project_id,
                        result.graph_id,
                        result.run_id,
                    ),
                ).fetchone()
                if row is None:
                    raise LogicRunPersistenceError("logic run was not in running state")
                conn.commit()
        except LogicRunStoreError:
            raise
        except Exception as exc:
            raise LogicRunPersistenceError(
                "failed to finalize logic run history"
            ) from exc

    def get_run(
        self, org_id: str, project_id: str, graph_id: str, run_id: str
    ) -> LogicDryRun:
        self._scope(org_id, project_id)
        try:
            with self._connect_factory() as conn:
                return self._get_with_conn(conn, org_id, project_id, graph_id, run_id)
        except LogicRunNotFound:
            raise
        except Exception as exc:
            raise LogicRunPersistenceError("failed to read logic run history") from exc

    def list_runs(
        self,
        org_id: str,
        project_id: str,
        graph_id: str,
        *,
        limit: int = 20,
        before: str | None = None,
    ) -> LogicRunListResponse:
        self._scope(org_id, project_id)
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        try:
            with self._connect_factory() as conn:
                params: list[Any] = [org_id, project_id, graph_id]
                cursor_sql = ""
                if before:
                    cursor = conn.execute(
                        "SELECT started_at,run_id FROM aip_logic_graph_runs WHERE org_id=%s AND project_id=%s AND graph_id=%s AND run_id=%s",
                        (org_id, project_id, graph_id, before),
                    ).fetchone()
                    if cursor is None:
                        raise LogicRunNotFound("logic run cursor not found")
                    cursor_sql = "AND (r.started_at,r.run_id) < (%s,%s)"
                    params.extend([cursor["started_at"], cursor["run_id"]])
                params.append(limit + 1)
                rows = conn.execute(
                    f"""SELECT r.*,
                        COUNT(*) FILTER (WHERE n.status='executed') AS executed_count,
                        COUNT(*) FILTER (WHERE n.status='skipped') AS skipped_count,
                        COUNT(*) FILTER (WHERE n.status='failed') AS failed_count,
                        COUNT(*) FILTER (WHERE n.status='canceled') AS canceled_count
                      FROM aip_logic_graph_runs r LEFT JOIN aip_logic_graph_run_nodes n
                        ON n.org_id=r.org_id AND n.project_id=r.project_id AND n.graph_id=r.graph_id AND n.run_id=r.run_id
                      WHERE r.org_id=%s AND r.project_id=%s AND r.graph_id=%s AND r.status <> 'running' {cursor_sql}
                      GROUP BY r.org_id,r.project_id,r.graph_id,r.run_id
                      ORDER BY r.started_at DESC,r.run_id DESC LIMIT %s""",
                    params,
                ).fetchall()
            has_more = len(rows) > limit
            visible = rows[:limit]
            items = [self._summary(row) for row in visible]
            return LogicRunListResponse(
                items=items,
                count=len(items),
                next_cursor=str(visible[-1]["run_id"])
                if has_more and visible
                else None,
            )
        except LogicRunStoreError:
            raise
        except Exception as exc:
            raise LogicRunPersistenceError("failed to list logic run history") from exc

    def recover_interrupted(
        self, org_id: str, project_id: str, *, stale_before: datetime
    ) -> int:
        self._scope(org_id, project_id)
        cutoff = stale_before or datetime.now(UTC)
        error = {
            "code": "INTERRUPTED",
            "message": "run interrupted before terminal persistence",
            "node_id": None,
            "reason": "process_restart",
        }
        try:
            with self._connect_factory() as conn:
                rows = conn.execute(
                    "UPDATE aip_logic_graph_runs SET status='failed',finished_at=NOW(),elapsed_ms=GREATEST(0,EXTRACT(EPOCH FROM (NOW()-started_at))*1000)::bigint,error=%s::jsonb WHERE org_id=%s AND project_id=%s AND status='running' AND started_at < %s RETURNING run_id",
                    (self._json(error), org_id, project_id, cutoff),
                ).fetchall()
                conn.commit()
                return len(rows)
        except Exception as exc:
            raise LogicRunPersistenceError(
                "failed to recover interrupted logic runs"
            ) from exc

    def _get_with_conn(self, conn, org_id, project_id, graph_id, run_id) -> LogicDryRun:
        row = conn.execute(
            "SELECT * FROM aip_logic_graph_runs WHERE org_id=%s AND project_id=%s AND graph_id=%s AND run_id=%s AND status <> 'running'",
            (org_id, project_id, graph_id, run_id),
        ).fetchone()
        if row is None:
            raise LogicRunNotFound(f"logic run {run_id} not found")
        nodes = conn.execute(
            "SELECT * FROM aip_logic_graph_run_nodes WHERE org_id=%s AND project_id=%s AND graph_id=%s AND run_id=%s ORDER BY topo_index",
            (org_id, project_id, graph_id, run_id),
        ).fetchall()
        return LogicDryRun(
            run_id=str(row["run_id"]),
            graph_id=str(row["graph_id"]),
            status=row["status"],
            evaluated_revision=int(row["evaluated_revision"]),
            graph_hash=str(row["graph_hash"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            elapsed_ms=int(row["elapsed_ms"]),
            total_tokens=int(row["total_tokens"])
            if row["total_tokens"] is not None
            else None,
            node_results=[
                LogicNodeResult(
                    node_id=str(n["node_id"]),
                    kind=n["kind"],
                    status=n["status"],
                    started_at=n["started_at"],
                    finished_at=n["finished_at"],
                    elapsed_ms=int(n["elapsed_ms"])
                    if n["elapsed_ms"] is not None
                    else None,
                    summary=str(n["summary"]),
                    output=n["output_summary"],
                    usage=n["usage"],
                    tool_call=n["tool_call"],
                    selected_branch_path=n["selected_branch_path"],
                    proposed_edits=n["proposed_edits"] or [],
                    error=n["error"],
                    truncated=bool(n["truncated"]),
                )
                for n in nodes
            ],
            proposed_edits=row["proposed_edits"] or [],
            error=row["error"],
        )

    @staticmethod
    def _summary(row) -> LogicRunSummary:
        error = row["error"] or {}
        return LogicRunSummary(
            run_id=str(row["run_id"]),
            graph_id=str(row["graph_id"]),
            status=row["status"],
            evaluated_revision=int(row["evaluated_revision"]),
            graph_hash=str(row["graph_hash"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            elapsed_ms=int(row["elapsed_ms"]),
            total_tokens=int(row["total_tokens"])
            if row["total_tokens"] is not None
            else None,
            node_counts=LogicNodeCounts(
                executed=int(row["executed_count"]),
                skipped=int(row["skipped_count"]),
                failed=int(row["failed_count"]),
                canceled=int(row["canceled_count"]),
            ),
            error_code=error.get("code"),
        )

    @staticmethod
    def _request_hash(request: LogicDryRunRequest) -> str:
        payload = request.model_dump(mode="json", exclude={"idempotency_key"})
        return hashlib.sha256(LogicRunStore._json(payload).encode()).hexdigest()

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    @staticmethod
    def _scope(org_id: str, project_id: str) -> None:
        if not org_id or not project_id:
            raise ValueError("org_id and project_id are required")
