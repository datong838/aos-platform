"""Phase 5 · Pipeline 核心引擎.

Pipelines + Nodes + Edges + Proposals + Schedules + ScheduleRuns + Datasets + DatasetBuilds + HealthChecks.
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import copy
import queue
import threading
import time
import uuid
from typing import Any, Callable
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from aos_api.public_contracts import redact_sensitive

_LOCK = threading.Lock()


# ───────────────────────── Pydantic Models ─────────────────────────


class PipelineNode(BaseModel):
    id: str = Field(default_factory=lambda: "pn-" + uuid.uuid4().hex[:8])
    pipeline_id: str = ""
    name: str
    node_type: str = "source"  # source|transform|join|filter|sink|llm
    position_x: float = 0.0
    position_y: float = 0.0
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "idle"  # idle|running|ok|error
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class PipelineEdge(BaseModel):
    id: str = Field(default_factory=lambda: "pe-" + uuid.uuid4().hex[:8])
    pipeline_id: str = ""
    source_node_id: str
    target_node_id: str
    label: str = ""
    created_at: float = Field(default_factory=lambda: time.time())


class Pipeline(BaseModel):
    id: str = Field(default_factory=lambda: "pl-" + uuid.uuid4().hex[:8])
    name: str
    description: str = ""
    pipeline_type: str = "ETL"  # ETL|ELT|Streaming|Batch
    status: str = "draft"  # draft|active|scheduled|failed
    owner: str = "system"
    tags: list[str] = Field(default_factory=list)
    executor_id: str = ""
    # Internal control plane only. Public create/update requests do not expose it.
    execution_mode: str = "disabled"  # disabled|live|demo
    execution_timeout_seconds: float = 30.0
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class PipelineProposal(BaseModel):
    id: str = Field(default_factory=lambda: "pp-" + uuid.uuid4().hex[:8])
    pipeline_id: str
    title: str
    description: str = ""
    proposed_by: str = "system"
    status: str = "pending"  # pending|approved|rejected|discarded|merged
    diff_summary: str = ""
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class PipelineHistory(BaseModel):
    id: str = Field(default_factory=lambda: "ph-" + uuid.uuid4().hex[:8])
    pipeline_id: str
    action: str = "updated"  # created|updated|run|deployed
    actor: str = "system"
    detail: str = ""
    created_at: float = Field(default_factory=lambda: time.time())


class Schedule(BaseModel):
    id: str = Field(default_factory=lambda: "sc-" + uuid.uuid4().hex[:8])
    name: str
    pipeline_id: str = ""
    trigger_type: str = "cron"  # cron|manual|event
    cron_expr: str = ""
    status: str = "active"  # active|paused|error
    owner: str = "system"
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class ScheduleRun(BaseModel):
    id: str = Field(default_factory=lambda: "sr-" + uuid.uuid4().hex[:8])
    schedule_id: str
    mode: str = "live"  # live|demo
    status: str = "pending"  # pending|running|succeeded|failed|unsupported|cancelled
    started_at: float = Field(default_factory=lambda: time.time())
    finished_at: float = 0.0
    duration_ms: int = 0
    executor_id: str = ""
    input_ref: str = ""
    output_ref: str = ""
    rows_read: int = 0
    rows_written: int = 0
    lineage_ref: str = ""
    quality_ref: str = ""
    error_code: str = ""
    error_message: str = ""
    # Legacy read compatibility. New execution semantics use rows_read/rows_written.
    rows_processed: int = 0
    error: str = ""


class DatasetSchema(BaseModel):
    columns: list[dict[str, Any]] = Field(default_factory=list)


class Dataset(BaseModel):
    id: str = Field(default_factory=lambda: "ds-" + uuid.uuid4().hex[:8])
    name: str
    description: str = ""
    source_type: str = "database"  # database|file|api|stream
    source_uri: str = ""
    status: str = "active"  # active|deprecated|building
    schema: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    size_bytes: int = 0
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class DatasetBuild(BaseModel):
    id: str = Field(default_factory=lambda: "db-" + uuid.uuid4().hex[:8])
    dataset_id: str
    status: str = "success"  # success|failed|running
    started_at: float = Field(default_factory=lambda: time.time())
    finished_at: float = 0.0
    rows_written: int = 0
    error: str = ""


class HealthCheck(BaseModel):
    id: str = Field(default_factory=lambda: "hc-" + uuid.uuid4().hex[:8])
    dataset_id: str
    status: str = "healthy"  # healthy|warning|critical
    null_rate: float = 0.0
    duplicate_rate: float = 0.0
    freshness_hours: float = 0.0
    mode: str = "demo"
    synthetic: bool = True
    checked_at: float = Field(default_factory=lambda: time.time())


class SyncConfig(BaseModel):
    dataset_id: str
    mode: str = "full"  # full|incremental|cdc
    interval_minutes: int = 60
    enabled: bool = True


# ───────────────────────── Engine ─────────────────────────


class PipelineEngine:
    """Phase 5 Pipeline 核心引擎."""

    _instance: "PipelineEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "PipelineEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._pipelines: dict[str, Pipeline] = {}
                    inst._nodes: dict[str, PipelineNode] = {}
                    inst._edges: dict[str, PipelineEdge] = {}
                    inst._proposals: dict[str, PipelineProposal] = {}
                    inst._history: dict[str, PipelineHistory] = {}
                    inst._schedules: dict[str, Schedule] = {}
                    inst._schedule_runs: dict[str, ScheduleRun] = {}
                    inst._datasets: dict[str, Dataset] = {}
                    inst._builds: dict[str, DatasetBuild] = {}
                    inst._health: dict[str, HealthCheck] = {}
                    inst._sync_configs: dict[str, SyncConfig] = {}
                    inst._executors: dict[str, Callable[..., dict[str, Any]]] = {}
                    inst._evidence_resolvers: dict[str, Callable[[str], bool]] = {}
                    cls._instance = inst
        return cls._instance

    # ── Pipelines ──
    def create_pipeline(self, name: str, **kwargs: Any) -> Pipeline:
        with _LOCK:
            pl = Pipeline(name=name, **kwargs)
            self._pipelines[pl.id] = pl
            self._add_history(pl.id, "created", "Pipeline created")
            return pl

    def get_pipeline(self, pl_id: str) -> Pipeline | None:
        return self._pipelines.get(pl_id)

    def list_pipelines(
        self,
        search: str | None = None,
        status: str | None = None,
        pipeline_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> tuple[list[Pipeline], int]:
        items = list(self._pipelines.values())
        if status:
            items = [p for p in items if p.status == status]
        if pipeline_type:
            items = [p for p in items if p.pipeline_type == pipeline_type]
        if search:
            s = search.lower()
            items = [p for p in items if s in p.name.lower() or s in p.description.lower()]
        reverse = sort_order == "desc"
        try:
            items.sort(key=lambda p: getattr(p, sort_by, 0), reverse=reverse)
        except Exception:
            items.sort(key=lambda p: p.updated_at, reverse=reverse)
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def update_pipeline(self, pl_id: str, **kwargs: Any) -> Pipeline:
        with _LOCK:
            pl = self._pipelines.get(pl_id)
            if pl is None:
                raise KeyError(f"Pipeline {pl_id} not found")
            for k, v in kwargs.items():
                if hasattr(pl, k) and k != "id":
                    setattr(pl, k, v)
            pl.updated_at = time.time()
            self._add_history(pl_id, "updated", f"Updated: {list(kwargs.keys())}")
            return pl

    def delete_pipeline(self, pl_id: str) -> bool:
        with _LOCK:
            existed = self._pipelines.pop(pl_id, None) is not None
            if existed:
                for nid in [n.id for n in self._nodes.values() if n.pipeline_id == pl_id]:
                    self._nodes.pop(nid, None)
                for eid in [e.id for e in self._edges.values() if e.pipeline_id == pl_id]:
                    self._edges.pop(eid, None)
            return existed

    # ── Nodes ──
    def add_node(self, pipeline_id: str, name: str, **kwargs: Any) -> PipelineNode:
        with _LOCK:
            node = PipelineNode(pipeline_id=pipeline_id, name=name, **kwargs)
            self._nodes[node.id] = node
            return node

    def get_node(self, node_id: str) -> PipelineNode | None:
        return self._nodes.get(node_id)

    def list_nodes(self, pipeline_id: str) -> list[PipelineNode]:
        return [n for n in self._nodes.values() if n.pipeline_id == pipeline_id]

    def update_node(self, node_id: str, **kwargs: Any) -> PipelineNode:
        with _LOCK:
            node = self._nodes.get(node_id)
            if node is None:
                raise KeyError(f"Node {node_id} not found")
            for k, v in kwargs.items():
                if hasattr(node, k) and k != "id":
                    setattr(node, k, v)
            node.updated_at = time.time()
            return node

    def delete_node(self, node_id: str) -> bool:
        with _LOCK:
            return self._nodes.pop(node_id, None) is not None

    # ── Edges ──
    def add_edge(self, pipeline_id: str, source_node_id: str, target_node_id: str, **kwargs: Any) -> PipelineEdge:
        with _LOCK:
            edge = PipelineEdge(
                pipeline_id=pipeline_id, source_node_id=source_node_id, target_node_id=target_node_id, **kwargs
            )
            self._edges[edge.id] = edge
            return edge

    def list_edges(self, pipeline_id: str) -> list[PipelineEdge]:
        return [e for e in self._edges.values() if e.pipeline_id == pipeline_id]

    def delete_edge(self, edge_id: str) -> bool:
        with _LOCK:
            return self._edges.pop(edge_id, None) is not None

    # ── Graph ──
    def get_graph(self, pl_id: str) -> dict[str, Any]:
        if pl_id not in self._pipelines:
            raise KeyError(f"Pipeline {pl_id} not found")
        nodes = self.list_nodes(pl_id)
        edges = self.list_edges(pl_id)
        return {
            "pipeline_id": pl_id,
            "nodes": [n.model_dump() for n in nodes],
            "edges": [e.model_dump() for e in edges],
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    # ── Files tree ──
    def get_files(self, pl_id: str) -> list[dict[str, Any]]:
        if pl_id not in self._pipelines:
            raise KeyError(f"Pipeline {pl_id} not found")
        pl = self._pipelines[pl_id]
        nodes = self.list_nodes(pl_id)
        tree: list[dict[str, Any]] = [
            {
                "name": pl.name,
                "path": f"/pipelines/{pl_id}",
                "type": "folder",
                "children": [
                    {
                        "name": "nodes",
                        "path": f"/pipelines/{pl_id}/nodes",
                        "type": "folder",
                        "children": [
                            {
                                "name": f"{n.name}.json",
                                "path": f"/pipelines/{pl_id}/nodes/{n.id}.json",
                                "type": "file",
                                "node_type": n.node_type,
                            }
                            for n in nodes
                        ],
                    },
                    {
                        "name": "config.yaml",
                        "path": f"/pipelines/{pl_id}/config.yaml",
                        "type": "file",
                    },
                ],
            }
        ]
        return tree

    # ── Node preview ──
    def preview_node(self, pl_id: str, node_id: str, limit: int = 20) -> dict[str, Any]:
        node = self._nodes.get(node_id)
        if node is None or node.pipeline_id != pl_id:
            raise KeyError(f"Node {node_id} not found in pipeline {pl_id}")
        cols = ["id", "name", "value", "ts"]
        rows = [
            {"id": i, "name": f"row_{i}", "value": i * 10, "ts": time.time() - i * 60}
            for i in range(min(limit, 5))
        ]
        return {
            "pipeline_id": pl_id,
            "node_id": node_id,
            "node_type": node.node_type,
            "columns": cols,
            "rows": rows,
            "total": 5,
            "mode": "demo",
            "synthetic": True,
        }

    # ── Node config (LLM) ──
    def get_node_config(self, pl_id: str, node_id: str) -> dict[str, Any]:
        node = self._nodes.get(node_id)
        if node is None or node.pipeline_id != pl_id:
            raise KeyError(f"Node {node_id} not found in pipeline {pl_id}")
        return {"pipeline_id": pl_id, "node_id": node_id, "config": node.config}

    def update_node_config(self, pl_id: str, node_id: str, config: dict[str, Any]) -> PipelineNode:
        with _LOCK:
            node = self._nodes.get(node_id)
            if node is None or node.pipeline_id != pl_id:
                raise KeyError(f"Node {node_id} not found in pipeline {pl_id}")
            node.config = config
            node.updated_at = time.time()
            return node

    # ── Trial run ──
    def trial_run(self, pl_id: str, node_id: str, sample_input: dict[str, Any] | None = None) -> dict[str, Any]:
        node = self._nodes.get(node_id)
        if node is None or node.pipeline_id != pl_id:
            raise KeyError(f"Node {node_id} not found in pipeline {pl_id}")
        pl = self._pipelines.get(pl_id)
        if pl is None:
            raise KeyError(f"Pipeline {pl_id} not found")
        evidence, output_rows = self._execute(
            pl,
            node_id=node_id,
            sample_input=sample_input or {},
            execution_kind="trial",
        )
        return {
            "pipeline_id": pl_id,
            "node_id": node_id,
            **evidence,
            "latency_ms": evidence["duration_ms"],
            "output_rows": output_rows,
            "ran_at": evidence["finished_at"],
        }

    # ── Proposals ──
    def create_proposal(self, pipeline_id: str, title: str, **kwargs: Any) -> PipelineProposal:
        with _LOCK:
            pp = PipelineProposal(pipeline_id=pipeline_id, title=title, **kwargs)
            self._proposals[pp.id] = pp
            return pp

    def get_proposal(self, pp_id: str) -> PipelineProposal | None:
        return self._proposals.get(pp_id)

    def list_proposals(self, pipeline_id: str, status: str | None = None) -> list[PipelineProposal]:
        items = [p for p in self._proposals.values() if p.pipeline_id == pipeline_id]
        if status:
            items = [p for p in items if p.status == status]
        return items

    def discard_proposal(self, pipeline_id: str, pp_id: str) -> PipelineProposal:
        with _LOCK:
            pp = self._proposals.get(pp_id)
            if pp is None or pp.pipeline_id != pipeline_id:
                raise KeyError(f"Proposal {pp_id} not found in pipeline {pipeline_id}")
            pp.status = "discarded"
            pp.updated_at = time.time()
            return pp

    def merge_proposal(self, pipeline_id: str, pp_id: str) -> PipelineProposal:
        with _LOCK:
            pp = self._proposals.get(pp_id)
            if pp is None or pp.pipeline_id != pipeline_id:
                raise KeyError(f"Proposal {pp_id} not found in pipeline {pipeline_id}")
            pp.status = "merged"
            pp.updated_at = time.time()
            self._add_history(pipeline_id, "updated", f"Merged proposal {pp_id}")
            return pp

    # ── History ──
    def _add_history(self, pipeline_id: str, action: str, detail: str = "") -> None:
        h = PipelineHistory(pipeline_id=pipeline_id, action=action, detail=detail)
        self._history[h.id] = h

    def list_history(self, pipeline_id: str) -> list[PipelineHistory]:
        items = [h for h in self._history.values() if h.pipeline_id == pipeline_id]
        items.sort(key=lambda h: h.created_at, reverse=True)
        return items

    # ── Schedules ──
    def create_schedule(self, name: str, **kwargs: Any) -> Schedule:
        with _LOCK:
            sc = Schedule(name=name, **kwargs)
            self._schedules[sc.id] = sc
            return sc

    def get_schedule(self, sc_id: str) -> Schedule | None:
        return self._schedules.get(sc_id)

    def list_schedules(
        self,
        search: str | None = None,
        status: str | None = None,
        trigger_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Schedule], int]:
        items = list(self._schedules.values())
        if status:
            items = [s for s in items if s.status == status]
        if trigger_type:
            items = [s for s in items if s.trigger_type == trigger_type]
        if search:
            s = search.lower()
            items = [sc for sc in items if s in sc.name.lower()]
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def update_schedule(self, sc_id: str, **kwargs: Any) -> Schedule:
        with _LOCK:
            sc = self._schedules.get(sc_id)
            if sc is None:
                raise KeyError(f"Schedule {sc_id} not found")
            for k, v in kwargs.items():
                if hasattr(sc, k) and k != "id":
                    setattr(sc, k, v)
            sc.updated_at = time.time()
            return sc

    def run_schedule(self, sc_id: str) -> ScheduleRun:
        started_at = time.time()
        with _LOCK:
            sc = self._schedules.get(sc_id)
            if sc is None:
                raise KeyError(f"Schedule {sc_id} not found")
            pipeline_id = sc.pipeline_id
            if sc.status != "active":
                run = ScheduleRun(
                    schedule_id=sc_id,
                    **self._unsupported_evidence(started_at, "SCHEDULE_NOT_ACTIVE"),
                )
                dispatch = None
            else:
                pipeline = self._pipelines.get(pipeline_id)
                if pipeline is None:
                    run = ScheduleRun(
                        schedule_id=sc_id,
                        **self._unsupported_evidence(started_at, "PIPELINE_NOT_FOUND"),
                    )
                    dispatch = None
                else:
                    preflight = self._preflight(pipeline, started_at)
                    if preflight is not None:
                        run = ScheduleRun(schedule_id=sc_id, **preflight)
                        dispatch = None
                    else:
                        executor_id = pipeline.executor_id
                        run = ScheduleRun(
                            schedule_id=sc_id,
                            mode="live",
                            status="running",
                            started_at=started_at,
                            executor_id=executor_id,
                        )
                        # Store running before starting the external callback. Starting
                        # under the same lock closes the pause/check dispatch race.
                        self._schedule_runs[run.id] = run
                        dispatch = self._start_dispatch(
                            pipeline,
                            node_id=None,
                            sample_input={},
                            execution_kind="schedule",
                            started_at=started_at,
                        )
            self._schedule_runs[run.id] = run

        if dispatch is not None:
            evidence, _ = self._collect_dispatch(dispatch)
            with _LOCK:
                for key, value in evidence.items():
                    setattr(run, key, value)

        with _LOCK:
            if pipeline_id:
                self._add_history(
                    pipeline_id,
                    "run",
                    "status={} executor={} output={}".format(
                        run.status,
                        run.executor_id or "-",
                        str(redact_sensitive(run.output_ref)) if run.output_ref else "-",
                    ),
                )
            return run.model_copy(deep=True)

    def pause_schedule(self, sc_id: str) -> Schedule:
        with _LOCK:
            sc = self._schedules.get(sc_id)
            if sc is None:
                raise KeyError(f"Schedule {sc_id} not found")
            sc.status = "paused"
            sc.updated_at = time.time()
            return sc

    def list_schedule_runs(self, sc_id: str) -> list[ScheduleRun]:
        with _LOCK:
            return [
                r.model_copy(deep=True)
                for r in self._schedule_runs.values()
                if r.schedule_id == sc_id
            ]

    # ── Datasets ──
    def create_dataset(self, name: str, **kwargs: Any) -> Dataset:
        with _LOCK:
            ds = Dataset(name=name, **kwargs)
            self._datasets[ds.id] = ds
            return ds

    def get_dataset(self, ds_id: str) -> Dataset | None:
        return self._datasets.get(ds_id)

    def list_datasets(
        self, search: str | None = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[Dataset], int]:
        items = list(self._datasets.values())
        if search:
            s = search.lower()
            items = [d for d in items if s in d.name.lower() or s in d.description.lower()]
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def preview_dataset(self, ds_id: str, limit: int = 50) -> dict[str, Any]:
        ds = self._datasets.get(ds_id)
        if ds is None:
            raise KeyError(f"Dataset {ds_id} not found")
        cols = [c.get("name", f"col_{i}") for i, c in enumerate(ds.schema)]
        rows = []
        for i in range(min(limit, 10)):
            row = {}
            for ci, col in enumerate(ds.schema):
                cname = col.get("name", f"col_{ci}")
                dt = col.get("datatype", "string")
                if dt == "int":
                    row[cname] = i
                elif dt == "double":
                    row[cname] = i * 1.5
                elif dt == "boolean":
                    row[cname] = i % 2 == 0
                else:
                    row[cname] = f"{cname}_{i}"
            rows.append(row)
        return {
            "dataset_id": ds_id,
            "columns": cols,
            "rows": rows,
            "total": ds.row_count,
            "returned": len(rows),
            "mode": "demo",
            "synthetic": True,
        }

    # ── Dataset builds ──
    def add_build(self, dataset_id: str, **kwargs: Any) -> DatasetBuild:
        with _LOCK:
            b = DatasetBuild(dataset_id=dataset_id, **kwargs)
            self._builds[b.id] = b
            return b

    def list_builds(self, dataset_id: str) -> list[DatasetBuild]:
        return [b for b in self._builds.values() if b.dataset_id == dataset_id]

    # ── Health ──
    def check_health(self, ds_id: str) -> HealthCheck:
        with _LOCK:
            if ds_id not in self._datasets:
                raise KeyError(f"Dataset {ds_id} not found")
            hc = HealthCheck(
                dataset_id=ds_id,
                status="healthy",
                null_rate=0.02,
                duplicate_rate=0.01,
                freshness_hours=1.5,
            )
            self._health[hc.id] = hc
            return hc

    # ── Honest execution ──
    def register_executor(self, executor_id: str, executor: Callable[..., dict[str, Any]]) -> None:
        if not executor_id.strip() or not callable(executor):
            raise ValueError("executor_id and callable executor are required")
        with _LOCK:
            self._executors[executor_id] = executor

    def unregister_executor(self, executor_id: str) -> None:
        with _LOCK:
            self._executors.pop(executor_id, None)

    def register_evidence_resolver(
        self,
        scheme: str,
        resolver: Callable[[str], bool],
    ) -> None:
        normalized = scheme.strip().lower()
        if normalized not in {"dataset", "artifact", "lineage", "quality", "object"}:
            raise ValueError("unsupported evidence scheme")
        if not callable(resolver):
            raise ValueError("evidence resolver must be callable")
        with _LOCK:
            self._evidence_resolvers[normalized] = resolver

    @staticmethod
    def _unsupported_evidence(started_at: float, code: str) -> dict[str, Any]:
        finished_at = time.time()
        return {
            "mode": "live",
            "status": "unsupported",
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": max(0, int((finished_at - started_at) * 1000)),
            "executor_id": "",
            "input_ref": "",
            "output_ref": "",
            "rows_read": 0,
            "rows_written": 0,
            "lineage_ref": "",
            "quality_ref": "",
            "error_code": code,
            "error_message": "pipeline execution is unavailable",
            "rows_processed": 0,
            "error": "pipeline execution is unavailable",
        }

    @staticmethod
    def _safe_error(_exc: Exception) -> str:
        redacted = str(redact_sensitive(str(_exc)))
        # Even redacted arbitrary exception text can contain business data. Only a
        # bounded generic message crosses the execution boundary.
        return "pipeline executor failed" if redacted else "pipeline executor failed"

    @staticmethod
    def _contains_unsupported_config(value: Any) -> bool:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).strip().lower() in {"sql", "custom_sql", "customsql", "query"}:
                    return True
                if PipelineEngine._contains_unsupported_config(child):
                    return True
        elif isinstance(value, (list, tuple)):
            return any(PipelineEngine._contains_unsupported_config(child) for child in value)
        return False

    def _valid_ref(
        self,
        value: str,
        *,
        allowed_schemes: set[str],
        required: bool = False,
    ) -> bool:
        if not value:
            return not required
        if len(value) > 512 or any(char.isspace() for char in value):
            return False
        if str(redact_sensitive(value)) != value:
            return False
        parsed = urlsplit(value)
        syntax_valid = (
            parsed.scheme in allowed_schemes
            and bool(parsed.netloc)
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
        )
        if not syntax_valid:
            return False
        resolver = self._evidence_resolvers.get(parsed.scheme)
        if resolver is None:
            return False
        try:
            return resolver(value) is True
        except Exception:
            return False

    def _preflight(self, pipeline: Pipeline, started_at: float) -> dict[str, Any] | None:
        nodes = [n for n in self._nodes.values() if n.pipeline_id == pipeline.id]
        supported_node_types = {"source", "transform", "filter", "sink", "llm"}
        if any(
            n.node_type.strip().lower() not in supported_node_types
            or self._contains_unsupported_config(n.config)
            for n in nodes
        ):
            return self._unsupported_evidence(started_at, "PIPELINE_NODE_UNSUPPORTED")
        if not pipeline.executor_id or pipeline.executor_id not in self._executors:
            return self._unsupported_evidence(started_at, "PIPELINE_EXECUTOR_MISSING")
        if pipeline.execution_mode != "live":
            return self._unsupported_evidence(started_at, "PIPELINE_MODE_UNSUPPORTED")
        if pipeline.execution_timeout_seconds <= 0 or pipeline.execution_timeout_seconds > 300:
            return self._unsupported_evidence(started_at, "PIPELINE_TIMEOUT_INVALID")
        return None

    def _start_dispatch(
        self,
        pipeline: Pipeline,
        *,
        node_id: str | None,
        sample_input: dict[str, Any],
        execution_kind: str,
        started_at: float,
    ) -> tuple[threading.Thread, queue.Queue, threading.Event, float, str, float]:
        executor_id = pipeline.executor_id
        executor = self._executors[executor_id]
        pipeline_snapshot = pipeline.model_copy(deep=True)
        nodes_snapshot = [
            copy.deepcopy(n) for n in self._nodes.values() if n.pipeline_id == pipeline.id
        ]
        result_queue: queue.Queue = queue.Queue(maxsize=1)
        cancel_event = threading.Event()
        deadline = time.monotonic() + pipeline.execution_timeout_seconds

        def invoke() -> None:
            try:
                result_queue.put(
                    (True, executor(
                        pipeline=pipeline_snapshot,
                        nodes=nodes_snapshot,
                        node_id=node_id,
                        sample_input=copy.deepcopy(sample_input),
                        execution_kind=execution_kind,
                        cancel_event=cancel_event,
                        deadline=deadline,
                    ))
                )
            except Exception as exc:
                result_queue.put((False, exc))

        thread = threading.Thread(
            target=invoke,
            name=f"pipeline-executor-{executor_id}",
            daemon=True,
        )
        thread.start()
        return thread, result_queue, cancel_event, deadline, executor_id, started_at

    def _collect_dispatch(
        self,
        dispatch: tuple[threading.Thread, queue.Queue, threading.Event, float, str, float],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        thread, result_queue, cancel_event, deadline, executor_id, started_at = dispatch
        timeout = max(0.0, deadline - time.monotonic())
        thread.join(timeout)
        if thread.is_alive():
            cancel_event.set()
            finished_at = time.time()
            return self._failed_evidence(
                started_at,
                finished_at,
                executor_id,
                "PIPELINE_EXECUTOR_TIMEOUT",
                "pipeline executor timed out",
            ), []
        try:
            ok, payload = result_queue.get_nowait()
        except queue.Empty:
            finished_at = time.time()
            return self._failed_evidence(
                started_at,
                finished_at,
                executor_id,
                "PIPELINE_EXECUTOR_FAILED",
                "pipeline executor failed",
            ), []
        if not ok:
            finished_at = time.time()
            return self._failed_evidence(
                started_at,
                finished_at,
                executor_id,
                "PIPELINE_EXECUTOR_FAILED",
                self._safe_error(payload),
            ), []
        return self._evidence_from_result(payload, started_at, executor_id)

    @staticmethod
    def _failed_evidence(
        started_at: float,
        finished_at: float,
        executor_id: str,
        code: str,
        message: str,
    ) -> dict[str, Any]:
        return {
            "mode": "live",
            "status": "failed",
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": max(0, int((finished_at - started_at) * 1000)),
            "executor_id": executor_id,
            "input_ref": "",
            "output_ref": "",
            "rows_read": 0,
            "rows_written": 0,
            "lineage_ref": "",
            "quality_ref": "",
            "error_code": code,
            "error_message": message,
            "rows_processed": 0,
            "error": message,
        }

    def _evidence_from_result(
        self,
        result: Any,
        started_at: float,
        executor_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        try:
            if not isinstance(result, dict):
                raise ValueError("executor result must be a mapping")
            refs = {
                name: str(result.get(name) or "")
                for name in ("input_ref", "output_ref", "lineage_ref", "quality_ref")
            }
            ref_schemes = {
                "input_ref": {"dataset", "artifact", "object"},
                "output_ref": {"dataset", "artifact", "object"},
                "lineage_ref": {"lineage"},
                "quality_ref": {"quality"},
            }
            if any(
                not self._valid_ref(
                    value,
                    allowed_schemes=ref_schemes[name],
                    required=name == "output_ref",
                )
                for name, value in refs.items()
            ):
                raise ValueError("executor references are invalid")
            rows_read = int(result.get("rows_read", 0))
            rows_written = int(result.get("rows_written", 0))
            if rows_read < 0 or rows_written < 0:
                raise ValueError("row counts must be non-negative")
            output_rows = result.get("output_rows") or []
            if not isinstance(output_rows, list) or not all(isinstance(row, dict) for row in output_rows):
                raise ValueError("output_rows must be a list of mappings")
            finished_at = time.time()
            return {
                "mode": "live",
                "status": "succeeded",
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": max(0, int((finished_at - started_at) * 1000)),
                "executor_id": executor_id,
                **refs,
                "rows_read": rows_read,
                "rows_written": rows_written,
                "error_code": "",
                "error_message": "",
                "rows_processed": rows_written,
                "error": "",
            }, output_rows
        except Exception as exc:
            finished_at = time.time()
            return self._failed_evidence(
                started_at,
                finished_at,
                executor_id,
                "PIPELINE_EVIDENCE_INVALID",
                self._safe_error(exc),
            ), []

    def _execute(
        self,
        pipeline: Pipeline,
        *,
        node_id: str | None = None,
        sample_input: dict[str, Any] | None = None,
        execution_kind: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        started_at = time.time()
        with _LOCK:
            preflight = self._preflight(pipeline, started_at)
            if preflight is not None:
                return preflight, []
            dispatch = self._start_dispatch(
                pipeline,
                node_id=node_id,
                sample_input=sample_input or {},
                execution_kind=execution_kind,
                started_at=started_at,
            )
        return self._collect_dispatch(dispatch)

    def get_latest_health(self, ds_id: str) -> HealthCheck | None:
        items = [h for h in self._health.values() if h.dataset_id == ds_id]
        if not items:
            return None
        items.sort(key=lambda h: h.checked_at, reverse=True)
        return items[0]

    # ── Sync config ──
    def get_sync_config(self, ds_id: str) -> SyncConfig:
        if ds_id not in self._datasets:
            raise KeyError(f"Dataset {ds_id} not found")
        sc = self._sync_configs.get(ds_id)
        if sc is None:
            sc = SyncConfig(dataset_id=ds_id)
            self._sync_configs[ds_id] = sc
        return sc

    def set_sync_config(self, ds_id: str, **kwargs: Any) -> SyncConfig:
        with _LOCK:
            if ds_id not in self._datasets:
                raise KeyError(f"Dataset {ds_id} not found")
            sc = self._sync_configs.get(ds_id)
            if sc is None:
                sc = SyncConfig(dataset_id=ds_id)
                self._sync_configs[ds_id] = sc
            for k, v in kwargs.items():
                if hasattr(sc, k) and k != "dataset_id":
                    setattr(sc, k, v)
            return sc

    # ── Util ──
    def reset(self) -> None:
        with _LOCK:
            self._pipelines.clear()
            self._nodes.clear()
            self._edges.clear()
            self._proposals.clear()
            self._history.clear()
            self._schedules.clear()
            self._schedule_runs.clear()
            self._datasets.clear()
            self._builds.clear()
            self._health.clear()
            self._sync_configs.clear()
            self._executors.clear()
            self._evidence_resolvers.clear()


def get_engine() -> PipelineEngine:
    return PipelineEngine()
