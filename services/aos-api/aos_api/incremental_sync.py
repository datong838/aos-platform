"""W2-23 · Data Connection 增量同步。

单调递增列 + WHERE 过滤增量提取 + 同步状态追踪。

详见 docs/palantier/20_tech/220tech_w2-wave-plan.md 第一批。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return "sync-" + uuid.uuid4().hex[:10]


class IncrementalConfig(BaseModel):
    incremental_column: str = "updated_at"
    where_clause: str = ""
    batch_size: int = 1000


class SyncState(BaseModel):
    last_synced_value: Any = None
    last_synced_at: str | None = None
    total_synced: int = 0


class SyncConnection(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    source_dataset_rid: str
    target_dataset_rid: str
    config: IncrementalConfig = Field(default_factory=IncrementalConfig)
    state: SyncState = Field(default_factory=SyncState)
    created_at: str = Field(default_factory=_now_iso)


class SyncResult(BaseModel):
    connection_id: str
    rows_extracted: int
    new_last_value: Any = None
    synced_at: str = Field(default_factory=_now_iso)


class IncrementalSyncError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class IncrementalSyncEngine:
    def __init__(self) -> None:
        self._connections: dict[str, SyncConnection] = {}
        self._sources: dict[str, list[dict[str, Any]]] = {}

    def create_connection(self, conn: SyncConnection) -> SyncConnection:
        self._connections[conn.id] = conn
        return conn

    def get_connection(self, conn_id: str) -> SyncConnection | None:
        return self._connections.get(conn_id)

    def list_connections(self) -> list[SyncConnection]:
        return list(self._connections.values())

    def seed_source(self, rid: str, rows: list[dict[str, Any]]) -> None:
        self._sources[rid] = [dict(r) for r in rows]

    def sync(self, conn_id: str) -> SyncResult:
        conn = self._connections.get(conn_id)
        if conn is None:
            raise IncrementalSyncError("NOT_FOUND", f"同步连接 {conn_id} 不存在")
        col = conn.config.incremental_column
        all_rows = self._sources.get(conn.source_dataset_rid, [])

        filtered = all_rows
        if conn.state.last_synced_value is not None:
            filtered = [
                r for r in all_rows
                if _compare(r.get(col), conn.state.last_synced_value) > 0
            ]

        if conn.config.where_clause:
            filtered = _apply_where(filtered, conn.config.where_clause)

        batch = filtered[:conn.config.batch_size]
        new_last = max(
            (r.get(col) for r in batch if r.get(col) is not None),
            default=conn.state.last_synced_value,
        )

        conn.state.last_synced_value = new_last
        conn.state.last_synced_at = _now_iso()
        conn.state.total_synced += len(batch)

        return SyncResult(
            connection_id=conn_id,
            rows_extracted=len(batch),
            new_last_value=new_last,
        )

    def reset_state(self, conn_id: str) -> SyncConnection:
        conn = self._connections.get(conn_id)
        if conn is None:
            raise IncrementalSyncError("NOT_FOUND", f"同步连接 {conn_id} 不存在")
        conn.state = SyncState()
        return conn


def _compare(a: Any, b: Any) -> int:
    try:
        if a < b:
            return -1
        if a > b:
            return 1
        return 0
    except TypeError:
        sa, sb = str(a), str(b)
        if sa < sb:
            return -1
        if sa > sb:
            return 1
        return 0


def _apply_where(rows: list[dict[str, Any]], clause: str) -> list[dict[str, Any]]:
    clause = clause.strip()
    if not clause:
        return rows
    if clause.upper().startswith("WHERE "):
        clause = clause[6:]
    try:
        return [r for r in rows if _eval_condition(r, clause)]
    except Exception:
        return rows


def _eval_condition(row: dict[str, Any], clause: str) -> bool:
    for op in [" == ", " != ", " >= ", " <= ", " > ", " < "]:
        if op in clause:
            left, right = clause.split(op, 1)
            left = left.strip()
            right = right.strip().strip("'\"")
            val = row.get(left)
            if op == " == ":
                return str(val) == right
            if op == " != ":
                return str(val) != right
            try:
                lv, rv = float(val), float(right)
                if op == " > ":
                    return lv > rv
                if op == " < ":
                    return lv < rv
                if op == " >= ":
                    return lv >= rv
                if op == " <= ":
                    return lv <= rv
            except (TypeError, ValueError):
                return False
    return True


_engine = IncrementalSyncEngine()


def get_engine() -> IncrementalSyncEngine:
    return _engine
