"""Phase 6 · DataSource 核心引擎.

Connectors + Sources + Schemas/Tables/Columns/ForeignKeys + Syncs/SyncRuns +
Agents + MediaSets/MediaFiles + Documents/ExtractionTemplates/Projects.
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
import hashlib
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()


# ───────────────────────── Pydantic Models ─────────────────────────


class Connector(BaseModel):
    id: str = Field(default_factory=lambda: "conn-" + uuid.uuid4().hex[:8])
    name: str
    connector_type: str = "database"  # database|stream|file|api|warehouse|nosql
    version: str = "1.0.0"
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)  # read|write|stream|cdc|preview|schema
    config_schema: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"  # active|deprecated|beta
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class DataSource(BaseModel):
    id: str = Field(default_factory=lambda: "src-" + uuid.uuid4().hex[:8])
    name: str
    connector_id: str = ""
    source_type: str = "database"  # database|stream|file|api|warehouse|nosql
    host: str = ""
    port: int = 0
    database: str = ""
    username: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"  # active|inactive|error|testing
    tags: list[str] = Field(default_factory=list)
    owner: str = "system"
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class SchemaInfo(BaseModel):
    id: str = Field(default_factory=lambda: "sch-" + uuid.uuid4().hex[:8])
    source_id: str
    name: str
    description: str = ""
    table_count: int = 0
    created_at: float = Field(default_factory=lambda: time.time())


class TableInfo(BaseModel):
    id: str = Field(default_factory=lambda: "tbl-" + uuid.uuid4().hex[:8])
    source_id: str
    schema_name: str
    name: str
    row_count: int = 0
    size_bytes: int = 0
    description: str = ""
    created_at: float = Field(default_factory=lambda: time.time())


class ColumnInfo(BaseModel):
    id: str = Field(default_factory=lambda: "col-" + uuid.uuid4().hex[:8])
    source_id: str
    schema_name: str
    table_name: str
    name: str
    datatype: str = "string"
    nullable: bool = True
    primary_key: bool = False
    default_value: str = ""
    description: str = ""


class ForeignKey(BaseModel):
    id: str = Field(default_factory=lambda: "fk-" + uuid.uuid4().hex[:8])
    source_id: str
    schema_name: str
    table_name: str
    column_name: str
    ref_schema: str
    ref_table: str
    ref_column: str


class SyncTask(BaseModel):
    id: str = Field(default_factory=lambda: "sync-" + uuid.uuid4().hex[:8])
    name: str
    source_id: str
    target_dataset: str = ""
    mode: str = "full"  # full|incremental|cdc
    cron_expr: str = "0 * * * *"
    status: str = "active"  # active|paused|error
    owner: str = "system"
    config: dict[str, Any] = Field(default_factory=dict)
    org_id: str = ""
    project_id: str = ""
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class SyncRun(BaseModel):
    id: str = Field(default_factory=lambda: "run-" + uuid.uuid4().hex[:8])
    sync_id: str
    status: str = "success"  # success|failed|running
    started_at: float = Field(default_factory=lambda: time.time())
    finished_at: float = 0.0
    duration_ms: int = 0
    rows_synced: int = 0
    error: str = ""
    error_code: str = ""
    pipeline_id: str = ""
    org_id: str = ""
    project_id: str = ""


class EdgeAgent(BaseModel):
    id: str = Field(default_factory=lambda: "agent-" + uuid.uuid4().hex[:8])
    name: str
    hostname: str = ""
    ip_address: str = ""
    region: str = ""
    version: str = "2.0.0"
    status: str = "online"  # online|offline|degraded
    config: dict[str, Any] = Field(default_factory=dict)
    last_heartbeat: float = Field(default_factory=lambda: time.time())
    source_ids: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class MediaSet(BaseModel):
    id: str = Field(default_factory=lambda: "ms-" + uuid.uuid4().hex[:8])
    name: str
    description: str = ""
    source_id: str = ""
    file_count: int = 0
    total_size_bytes: int = 0
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class MediaFile(BaseModel):
    id: str = Field(default_factory=lambda: "mf-" + uuid.uuid4().hex[:8])
    media_set_id: str
    filename: str
    file_type: str = ""  # image|video|audio|document|archive
    mime_type: str = ""
    size_bytes: int = 0
    url: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())


class Document(BaseModel):
    id: str = Field(default_factory=lambda: "doc-" + uuid.uuid4().hex[:8])
    name: str
    source_id: str = ""
    template_id: str = ""
    file_type: str = "pdf"  # pdf|docx|image|html
    status: str = "pending"  # pending|extracted|failed
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    size_bytes: int = 0
    content_type: str = "application/octet-stream"
    content_sha256: str = ""
    ocr_text: str = ""
    parser: str = ""
    error_message: str = ""
    ontology_object_id: str = ""
    history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class ExtractionTemplate(BaseModel):
    id: str = Field(default_factory=lambda: "tpl-" + uuid.uuid4().hex[:8])
    name: str
    description: str = ""
    fields: list[dict[str, Any]] = Field(default_factory=list)
    doc_type: str = "invoice"  # invoice|contract|receipt|form|custom
    created_at: float = Field(default_factory=lambda: time.time())


class DataProject(BaseModel):
    id: str = Field(default_factory=lambda: "prj-" + uuid.uuid4().hex[:8])
    name: str
    description: str = ""
    owner: str = "system"
    status: str = "active"  # active|archived
    source_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


# ───────────────────────── Engine ─────────────────────────


class DataSourceEngine:
    """Phase 6 DataSource 核心引擎."""

    _instance: "DataSourceEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "DataSourceEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._connectors: dict[str, Connector] = {}
                    inst._sources: dict[str, DataSource] = {}
                    inst._schemas: dict[str, SchemaInfo] = {}
                    inst._tables: dict[str, TableInfo] = {}
                    inst._columns: dict[str, ColumnInfo] = {}
                    inst._foreign_keys: dict[str, ForeignKey] = {}
                    inst._sync_tasks: dict[str, SyncTask] = {}
                    inst._sync_runs: dict[str, SyncRun] = {}
                    inst._scoped_sync_tasks: dict[tuple[str, str, str], SyncTask] = {}
                    inst._scoped_sync_runs: dict[tuple[str, str, str], SyncRun] = {}
                    inst._agents: dict[str, EdgeAgent] = {}
                    inst._media_sets: dict[str, MediaSet] = {}
                    inst._media_files: dict[str, MediaFile] = {}
                    inst._documents: dict[str, Document] = {}
                    inst._document_bytes: dict[str, bytes] = {}
                    inst._templates: dict[str, ExtractionTemplate] = {}
                    inst._projects: dict[str, DataProject] = {}
                    cls._instance = inst
        return cls._instance

    # ── Connectors ──
    def create_connector(self, name: str, **kwargs: Any) -> Connector:
        with _LOCK:
            c = Connector(name=name, **kwargs)
            self._connectors[c.id] = c
            return c

    def get_connector(self, cid: str) -> Connector | None:
        return self._connectors.get(cid)

    def list_connectors(
        self, connector_type: str | None = None, page: int = 1, page_size: int = 50,
    ) -> tuple[list[Connector], int]:
        items = list(self._connectors.values())
        if connector_type:
            items = [c for c in items if c.connector_type == connector_type]
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def update_connector(self, cid: str, **kwargs: Any) -> Connector:
        with _LOCK:
            c = self._connectors.get(cid)
            if c is None:
                raise KeyError(f"Connector {cid} not found")
            for k, v in kwargs.items():
                if hasattr(c, k) and k != "id":
                    setattr(c, k, v)
            c.updated_at = time.time()
            return c

    def get_connector_capabilities(self, cid: str) -> list[str]:
        c = self._connectors.get(cid)
        if c is None:
            raise KeyError(f"Connector {cid} not found")
        return c.capabilities

    def delete_connector(self, cid: str) -> bool:
        with _LOCK:
            return self._connectors.pop(cid, None) is not None

    # ── Sources ──
    def create_source(self, name: str, **kwargs: Any) -> DataSource:
        with _LOCK:
            s = DataSource(name=name, **kwargs)
            self._sources[s.id] = s
            return s

    def get_source(self, sid: str) -> DataSource | None:
        return self._sources.get(sid)

    def list_sources(
        self, search: str | None = None, source_type: str | None = None,
        page: int = 1, page_size: int = 20,
    ) -> tuple[list[DataSource], int]:
        items = list(self._sources.values())
        if source_type:
            items = [s for s in items if s.source_type == source_type]
        if search:
            s = search.lower()
            items = [src for src in items if s in src.name.lower()]
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def update_source(self, sid: str, **kwargs: Any) -> DataSource:
        with _LOCK:
            s = self._sources.get(sid)
            if s is None:
                raise KeyError(f"Source {sid} not found")
            for k, v in kwargs.items():
                if hasattr(s, k) and k != "id":
                    setattr(s, k, v)
            s.updated_at = time.time()
            return s

    def delete_source(self, sid: str) -> bool:
        with _LOCK:
            return self._sources.pop(sid, None) is not None

    def test_connection(self, sid: str) -> dict[str, Any]:
        s = self._sources.get(sid)
        if s is None:
            raise KeyError(f"Source {sid} not found")
        return {
            "source_id": sid,
            "status": "ok",
            "latency_ms": 45,
            "tested_at": time.time(),
            "details": {"host": s.host, "database": s.database},
        }

    def get_source_capabilities(self, sid: str) -> list[str]:
        s = self._sources.get(sid)
        if s is None:
            raise KeyError(f"Source {sid} not found")
        connector = self._connectors.get(s.connector_id)
        if connector:
            return connector.capabilities
        return ["read", "write", "schema"]

    # ── Schemas ──
    def add_schema(self, source_id: str, name: str, **kwargs: Any) -> SchemaInfo:
        with _LOCK:
            sch = SchemaInfo(source_id=source_id, name=name, **kwargs)
            self._schemas[sch.id] = sch
            return sch

    def list_schemas(self, source_id: str) -> list[SchemaInfo]:
        return [s for s in self._schemas.values() if s.source_id == source_id]

    def list_tables(self, source_id: str, schema_name: str) -> list[TableInfo]:
        return [
            t for t in self._tables.values()
            if t.source_id == source_id and t.schema_name == schema_name
        ]

    def list_columns(self, source_id: str, schema_name: str, table_name: str) -> list[ColumnInfo]:
        return [
            c for c in self._columns.values()
            if c.source_id == source_id and c.schema_name == schema_name and c.table_name == table_name
        ]

    def list_foreign_keys(self, source_id: str, schema_name: str, table_name: str) -> list[ForeignKey]:
        return [
            fk for fk in self._foreign_keys.values()
            if fk.source_id == source_id and fk.schema_name == schema_name and fk.table_name == table_name
        ]

    def preview_data(self, source_id: str, schema_name: str = "", table_name: str = "", limit: int = 50) -> dict[str, Any]:
        s = self._sources.get(source_id)
        if s is None:
            raise KeyError(f"Source {source_id} not found")
        cols = [c.name for c in self._columns.values()
                if c.source_id == source_id and c.schema_name == schema_name and c.table_name == table_name]
        if not cols:
            cols = ["id", "name", "value", "created_at"]
        rows = []
        for i in range(min(limit, 10)):
            row = {}
            for cname in cols:
                if cname in ("id",):
                    row[cname] = i + 1
                elif cname in ("value", "amount", "price", "qty", "count"):
                    row[cname] = i * 10.5
                else:
                    row[cname] = f"{cname}_{i}"
            rows.append(row)
        return {
            "source_id": source_id,
            "schema": schema_name,
            "table": table_name,
            "columns": cols,
            "rows": rows,
            "total": len(rows),
            "returned": len(rows),
        }

    def add_table(self, source_id: str, schema_name: str, name: str, **kwargs: Any) -> TableInfo:
        with _LOCK:
            t = TableInfo(source_id=source_id, schema_name=schema_name, name=name, **kwargs)
            self._tables[t.id] = t
            return t

    def add_column(self, source_id: str, schema_name: str, table_name: str, name: str, **kwargs: Any) -> ColumnInfo:
        with _LOCK:
            c = ColumnInfo(source_id=source_id, schema_name=schema_name, table_name=table_name, name=name, **kwargs)
            self._columns[c.id] = c
            return c

    def add_foreign_key(self, source_id: str, schema_name: str, table_name: str, column_name: str,
                        ref_schema: str, ref_table: str, ref_column: str) -> ForeignKey:
        with _LOCK:
            fk = ForeignKey(
                source_id=source_id, schema_name=schema_name, table_name=table_name,
                column_name=column_name, ref_schema=ref_schema, ref_table=ref_table, ref_column=ref_column,
            )
            self._foreign_keys[fk.id] = fk
            return fk

    # ── Sync Tasks ──

    @staticmethod
    def _sync_scope_tuple(
        scope: Any | None, org_id: str = "", project_id: str = "",
    ) -> tuple[str, str]:
        """Return (org_id, project_id) preferring scope.* fields."""
        if scope is not None:
            o = getattr(scope, "org_id", None) or org_id or ""
            p = getattr(scope, "project_id", None) or project_id or ""
            return o, p
        return org_id or "", project_id or ""

    def _resolve_sync_task(
        self, sid: str, scope: Any | None,
    ) -> SyncTask | None:
        """Look up sync task. 显式 scope 且 org/proj 非空时 → 禁止 fallback,
        保证越租户隔离 (G13)."""
        org, proj = self._sync_scope_tuple(scope)
        if org and proj:
            # Strict: 只查 scoped dict, 不 fallback 全局 (越租户隔离 D 门)
            return self._scoped_sync_tasks.get((org, proj, sid))
        return self._sync_tasks.get(sid)

    def create_sync_task(
        self, name: str, *, org_id: str = "", project_id: str = "",
        scope: Any | None = None, **kwargs: Any,
    ) -> SyncTask:
        with _LOCK:
            o, p = self._sync_scope_tuple(scope, org_id, project_id)
            kwargs.pop("org_id", None)
            kwargs.pop("project_id", None)
            st = SyncTask(name=name, org_id=o, project_id=p, **kwargs)
            self._sync_tasks[st.id] = st
            if o and p:
                self._scoped_sync_tasks[(o, p, st.id)] = st
            return st

    def get_sync_task(self, sid: str, scope: Any | None = None) -> SyncTask | None:
        return self._resolve_sync_task(sid, scope)

    def list_sync_tasks(
        self,
        search: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
        scope: Any | None = None,
    ) -> tuple[list[SyncTask], int]:
        org, proj = self._sync_scope_tuple(scope)
        if org and proj:
            items = [
                st for st in self._scoped_sync_tasks.values()
                if st.org_id == org and st.project_id == proj
            ]
        else:
            items = list(self._sync_tasks.values())
        if status:
            items = [s for s in items if s.status == status]
        if search:
            s = search.lower()
            items = [st for st in items if s in st.name.lower()]
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def update_sync_task(
        self, sid: str, *, scope: Any | None = None, **kwargs: Any,
    ) -> SyncTask:
        with _LOCK:
            st = self._resolve_sync_task(sid, scope)
            if st is None:
                raise KeyError(f"SyncTask {sid} not found")
            for k, v in kwargs.items():
                if hasattr(st, k) and k != "id":
                    setattr(st, k, v)
            st.updated_at = time.time()
            return st

    def run_sync_task(
        self, sid: str, scope: Any | None = None,
    ) -> SyncRun:
        with _LOCK:
            st = self._resolve_sync_task(sid, scope)
            if st is None:
                raise KeyError(f"SyncTask {sid} not found")
            pipeline_id = (st.config or {}).get("pipeline_id", "")
            org, proj = (
                self._sync_scope_tuple(scope, st.org_id, st.project_id)
            )
            started = time.time()
            run = SyncRun(
                sync_id=sid,
                status="running",
                started_at=started,
                pipeline_id=pipeline_id,
                org_id=org,
                project_id=proj,
            )
            self._sync_runs[run.id] = run
            if org and proj:
                self._scoped_sync_runs[(org, proj, run.id)] = run

        # Release lock during real pipeline execution to avoid deadlock.
        if pipeline_id and org and proj:
            result = self._execute_pipeline_via_phase5(
                pipeline_id, org, proj,
            )
            status = "success" if result.get("ok") else "failed"
            rows = int(result.get("rows_written") or 0)
            finished = time.time()
            duration_ms = max(1, int((finished - started) * 1000))
            err_code = "" if result.get("ok") else (result.get("error_code") or "SYNC_FAILED")
            err_msg = "" if result.get("ok") else self._sanitize_error(result.get("error_message") or err_code)
        else:
            # Legacy: no pipeline binding → best-effort, do not claim 5000 rows any more
            status = "success"
            rows = 0
            finished = time.time()
            duration_ms = max(1, int((finished - started) * 1000))
            err_code = ""
            err_msg = ""

        with _LOCK:
            run.status = status
            run.finished_at = finished
            run.duration_ms = duration_ms
            run.rows_synced = rows
            run.error_code = err_code
            run.error = err_msg
            # Also propagate status on SyncTask (active / error)
            st.status = "error" if status == "failed" else "active"
            st.updated_at = time.time()
            return run.model_copy(deep=True)

    @staticmethod
    def _sanitize_error(raw: str) -> str:
        """DLQ-safe: redact PII before crossing service boundaries."""
        try:
            from aos_api.public_contracts import redact_sensitive
            out = str(redact_sensitive(raw))
            return out[:500]
        except Exception:
            return (raw or "sync failed")[:500]

    @staticmethod
    def _execute_pipeline_via_phase5(
        pipeline_id: str, org_id: str, project_id: str,
    ) -> dict[str, Any]:
        """Delegate to Phase5 PipelineEngine.execute_pipeline_once for real run."""
        try:
            from aos_api.phase5_pipeline_engine import TenantScope, get_engine as p5_get_engine
            scope = TenantScope(org_id=org_id, project_id=project_id)
            eng = p5_get_engine()
            if not hasattr(eng, "execute_pipeline_once"):
                return {
                    "ok": False,
                    "rows_written": 0,
                    "error_code": "P5_NO_DIRECT_EXEC",
                    "error_message": (
                        "Phase5 engine missing execute_pipeline_once; "
                        "run_schedule path available but SyncTask real execution "
                        "requires the new direct method."
                    ),
                }
            return eng.execute_pipeline_once(scope, pipeline_id)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "rows_written": 0,
                "error_code": "SYNC_EXEC_EXCEPTION",
                "error_message": f"{type(exc).__name__}: {exc}",
            }

    def list_sync_runs(
        self, sid: str, scope: Any | None = None,
    ) -> list[SyncRun]:
        org, proj = self._sync_scope_tuple(scope)
        if org and proj:
            items = [
                r for r in self._scoped_sync_runs.values()
                if r.sync_id == sid and r.org_id == org and r.project_id == proj
            ]
        else:
            items = [r for r in self._sync_runs.values() if r.sync_id == sid]
        return [r.model_copy(deep=True) for r in items]

    # ── Edge Agents ──
    def create_agent(self, name: str, **kwargs: Any) -> EdgeAgent:
        with _LOCK:
            a = EdgeAgent(name=name, **kwargs)
            self._agents[a.id] = a
            return a

    def get_agent(self, aid: str) -> EdgeAgent | None:
        return self._agents.get(aid)

    def list_agents(
        self, status: str | None = None, region: str | None = None,
        page: int = 1, page_size: int = 20,
    ) -> tuple[list[EdgeAgent], int]:
        items = list(self._agents.values())
        if status:
            items = [a for a in items if a.status == status]
        if region:
            items = [a for a in items if a.region == region]
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def get_agent_metrics(self, aid: str) -> dict[str, Any]:
        a = self._agents.get(aid)
        if a is None:
            raise KeyError(f"Agent {aid} not found")
        return {
            "agent_id": aid,
            "cpu_usage": 35.5,
            "memory_usage": 62.3,
            "disk_usage": 45.0,
            "network_in_mbps": 12.5,
            "network_out_mbps": 8.3,
            "active_connections": 15,
            "uptime_seconds": 86400,
            "collected_at": time.time(),
        }

    def get_agent_sources(self, aid: str) -> list[DataSource]:
        a = self._agents.get(aid)
        if a is None:
            raise KeyError(f"Agent {aid} not found")
        return [self._sources[sid] for sid in a.source_ids if sid in self._sources]

    def get_agent_health(self, aid: str) -> dict[str, Any]:
        a = self._agents.get(aid)
        if a is None:
            raise KeyError(f"Agent {aid} not found")
        return {
            "agent_id": aid,
            "status": a.status,
            "last_heartbeat": a.last_heartbeat,
            "healthy": a.status == "online",
            "checked_at": time.time(),
        }

    def update_agent_config(self, aid: str, config: dict[str, Any]) -> EdgeAgent:
        with _LOCK:
            a = self._agents.get(aid)
            if a is None:
                raise KeyError(f"Agent {aid} not found")
            a.config = config
            a.updated_at = time.time()
            return a

    # ── Media Sets ──
    def create_media_set(self, name: str, **kwargs: Any) -> MediaSet:
        with _LOCK:
            ms = MediaSet(name=name, **kwargs)
            self._media_sets[ms.id] = ms
            return ms

    def get_media_set(self, msid: str) -> MediaSet | None:
        return self._media_sets.get(msid)

    def list_media_set_files(self, msid: str) -> list[MediaFile]:
        return [f for f in self._media_files.values() if f.media_set_id == msid]

    def transform_media_files(self, msid: str, operation: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        ms = self._media_sets.get(msid)
        if ms is None:
            raise KeyError(f"MediaSet {msid} not found")
        files = self.list_media_set_files(msid)
        return {
            "media_set_id": msid,
            "operation": operation,
            "params": params or {},
            "files_transformed": len(files),
            "status": "completed",
            "completed_at": time.time(),
        }

    def add_media_file(self, media_set_id: str, filename: str, **kwargs: Any) -> MediaFile:
        with _LOCK:
            f = MediaFile(media_set_id=media_set_id, filename=filename, **kwargs)
            self._media_files[f.id] = f
            return f

    # ── Documents ──
    def create_document(self, name: str, **kwargs: Any) -> Document:
        with _LOCK:
            d = Document(name=name, **kwargs)
            self._documents[d.id] = d
            return d

    def upload_document(self, name: str, data: bytes, content_type: str) -> Document:
        """保存调用方实际提交的文件字节；空内容必须拒绝。"""
        if not data:
            raise ValueError("文件内容为空")
        if len(data) > 50 * 1024 * 1024:
            raise ValueError("文件大小超过限制（最大 50MB）")
        with _LOCK:
            now = time.time()
            d = Document(
                name=name,
                file_type=(name.rsplit(".", 1)[-1].lower() if "." in name else "bin"),
                status="uploaded",
                size_bytes=len(data),
                content_type=content_type or "application/octet-stream",
                content_sha256=hashlib.sha256(data).hexdigest(),
                history=[{"state": "uploaded", "timestamp": now, "note": "服务端已接收文件字节"}],
            )
            self._documents[d.id] = d
            self._document_bytes[d.id] = bytes(data)
            return d

    def get_document(self, did: str) -> Document | None:
        return self._documents.get(did)

    def list_documents(
        self, search: str | None = None, status: str | None = None,
        page: int = 1, page_size: int = 20,
    ) -> tuple[list[Document], int]:
        items = list(self._documents.values())
        if status:
            items = [d for d in items if d.status == status]
        if search:
            s = search.lower()
            items = [d for d in items if s in d.name.lower()]
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def extract_document(self, did: str, fields: list[str] | None = None) -> Document:
        with _LOCK:
            d = self._documents.get(did)
            if d is None:
                raise KeyError(f"Document {did} not found")
            extracted = {}
            target_fields = fields or ["vendor", "amount", "date", "invoice_number"]
            for f in target_fields:
                extracted[f] = f"value_{f}"
            d.extracted_fields = extracted
            d.status = "extracted"
            d.updated_at = time.time()
            return d

    def process_document(self, did: str, template_id: str) -> Document:
        """从服务端保存的原始字节重新解析并执行现有 DocIntel 抽取。"""
        from aos_api.aip_docintel_extract import get_engine as get_extract_engine
        from aos_api.file_parsers import extract

        d = self._documents.get(did)
        if d is None:
            raise KeyError(f"Document {did} not found")
        data = self._document_bytes.get(did)
        if not data:
            raise ValueError("文档没有可重处理的服务端文件字节")
        parsed = extract(data=data, name=d.name, content_type=d.content_type)
        if not parsed.get("ok"):
            raise ValueError(str(parsed.get("hint") or "文档解析失败"))
        text = str(parsed.get("text") or "")
        if not text.strip():
            raise ValueError("文档解析结果为空")
        result = get_extract_engine().run_extract(template_id=template_id, text=text, name=d.name)
        raw_fields = result.get("fields") or []
        extracted_fields = {
            str(field.get("id") or field.get("name") or index): dict(field)
            for index, field in enumerate(raw_fields)
            if isinstance(field, dict)
        }
        with _LOCK:
            current = self._documents.get(did)
            if current is None:
                raise KeyError(f"Document {did} not found")
            current.template_id = str(result.get("template_id") or template_id)
            current.ocr_text = text
            current.parser = str(parsed.get("parser") or "")
            current.extracted_fields = extracted_fields
            confidences = [
                float(field.get("confidence", 0))
                for field in extracted_fields.values()
                if isinstance(field.get("confidence"), (int, float))
            ]
            current.status = "needs_correction" if confidences and min(confidences) < 0.7 else "review"
            current.error_message = ""
            current.updated_at = time.time()
            current.history.append({
                "state": current.status,
                "timestamp": current.updated_at,
                "note": f"服务端解析并抽取 {len(extracted_fields)} 个字段",
            })
            return current

    def update_document(
        self,
        did: str,
        *,
        ocr_text: str | None = None,
        extracted_fields: list[dict[str, Any]] | None = None,
    ) -> Document:
        with _LOCK:
            d = self._documents.get(did)
            if d is None:
                raise KeyError(f"Document {did} not found")
            if ocr_text is not None:
                d.ocr_text = ocr_text
            if extracted_fields is not None:
                d.extracted_fields = {
                    str(field.get("id") or field.get("name") or index): dict(field)
                    for index, field in enumerate(extracted_fields)
                }
            d.updated_at = time.time()
            return d

    def review_document(self, did: str, action: str) -> Document:
        if action != "reject":
            raise ValueError("仅支持 reject；入库请调用 ontology-write")
        with _LOCK:
            d = self._documents.get(did)
            if d is None:
                raise KeyError(f"Document {did} not found")
            d.status = "needs_correction"
            d.updated_at = time.time()
            d.history.append({"state": d.status, "timestamp": d.updated_at, "note": "审核退回修正"})
            return d

    def write_document_to_ontology(self, did: str, object_type_id: str) -> tuple[Document, Any]:
        from aos_api.ontology_engine import get_engine as get_ontology_engine

        # 查重、创建 Object、回写 document 必须处于同一临界区；否则并发审核会各自创建对象。
        with _LOCK:
            document = self._documents.get(did)
            if document is None:
                raise KeyError(f"Document {did} not found")
            if not document.extracted_fields:
                raise ValueError("没有可写入本体的提取字段")
            ontology = get_ontology_engine()
            if ontology.get_object_type(object_type_id) is None:
                raise ValueError(f"Object Type {object_type_id} 不存在")
            if document.ontology_object_id:
                existing = ontology.get_object(document.ontology_object_id)
                if existing is not None:
                    if existing.object_type_id != object_type_id:
                        raise ValueError(
                            f"文档已写入 Object Type {existing.object_type_id}，不能重复写入 {object_type_id}"
                        )
                    return document, existing
            properties = {
                str(field.get("name") or key): field.get("value")
                for key, field in document.extracted_fields.items()
            }
            properties.update({"document_id": document.id, "content_sha256": document.content_sha256})
            obj = ontology.create_object(object_type_id, document.name, properties=properties)
            document.ontology_object_id = obj.id
            document.status = "review"
            document.updated_at = time.time()
            document.history.append({
                "state": "review",
                "timestamp": document.updated_at,
                "note": f"已写入本体 Object {obj.id}",
            })
            return document, obj

    def delete_document(self, did: str) -> bool:
        with _LOCK:
            deleted = self._documents.pop(did, None)
            self._document_bytes.pop(did, None)
            return deleted is not None

    def document_stats(self) -> dict[str, Any]:
        items = list(self._documents.values())
        confidences: list[float] = []
        for d in items:
            for field in d.extracted_fields.values():
                value = field.get("confidence") if isinstance(field, dict) else None
                if isinstance(value, (int, float)):
                    confidences.append(float(value))
        return {
            "total": len(items),
            "processing": sum(1 for d in items if d.status in {"processing_ocr", "extracting"}),
            "average_confidence": (sum(confidences) / len(confidences)) if confidences else None,
            "template_count": len(self._templates),
        }

    def import_document(self, name: str, **kwargs: Any) -> Document:
        with _LOCK:
            d = Document(name=name, **kwargs)
            self._documents[d.id] = d
            return d

    def create_template(self, name: str, **kwargs: Any) -> ExtractionTemplate:
        with _LOCK:
            t = ExtractionTemplate(name=name, **kwargs)
            self._templates[t.id] = t
            return t

    def list_templates(self) -> list[ExtractionTemplate]:
        return list(self._templates.values())

    def create_project(self, name: str, **kwargs: Any) -> DataProject:
        with _LOCK:
            p = DataProject(name=name, **kwargs)
            self._projects[p.id] = p
            return p

    def list_projects(self) -> list[DataProject]:
        return list(self._projects.values())

    # ── Util ──
    def reset(self) -> None:
        with _LOCK:
            self._connectors.clear()
            self._sources.clear()
            self._schemas.clear()
            self._tables.clear()
            self._columns.clear()
            self._foreign_keys.clear()
            self._sync_tasks.clear()
            self._sync_runs.clear()
            self._scoped_sync_tasks.clear()
            self._scoped_sync_runs.clear()
            self._agents.clear()
            self._media_sets.clear()
            self._media_files.clear()
            self._documents.clear()
            self._document_bytes.clear()
            self._templates.clear()
            self._projects.clear()


def get_engine() -> DataSourceEngine:
    return DataSourceEngine()
