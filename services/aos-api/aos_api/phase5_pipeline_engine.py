"""Phase 5 · Pipeline 核心引擎.

Pipelines + Nodes + Edges + Proposals + Schedules + ScheduleRuns + Datasets + DatasetBuilds + HealthChecks.
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable

from pydantic import BaseModel, Field

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
        sc = self._schedules.get(sc_id)
        if sc is None:
            raise KeyError(f"Schedule {sc_id} not found")
        started = time.time()
        if sc.status != "active":
            evidence = self._unsupported_evidence(started, "SCHEDULE_NOT_ACTIVE")
        else:
            pl = self._pipelines.get(sc.pipeline_id)
            if pl is None:
                evidence = self._unsupported_evidence(started, "PIPELINE_NOT_FOUND")
            else:
                evidence, _ = self._execute(pl, execution_kind="schedule")
        run = ScheduleRun(schedule_id=sc_id, **evidence)
        with _LOCK:
            self._schedule_runs[run.id] = run
            if sc.pipeline_id:
                self._add_history(
                    sc.pipeline_id,
                    "run",
                    f"status={run.status} executor={run.executor_id or '-'} output={run.output_ref or '-'}",
                )
        return run

    def pause_schedule(self, sc_id: str) -> Schedule:
        with _LOCK:
            sc = self._schedules.get(sc_id)
            if sc is None:
                raise KeyError(f"Schedule {sc_id} not found")
            sc.status = "paused"
            sc.updated_at = time.time()
            return sc

    def list_schedule_runs(self, sc_id: str) -> list[ScheduleRun]:
        return [r for r in self._schedule_runs.values() if r.schedule_id == sc_id]

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
        # Exception text can contain credentials or input data. Public contracts own
        # recursive redaction; this boundary deliberately emits no exception text.
        return "pipeline executor failed"

    def _execute(
        self,
        pipeline: Pipeline,
        *,
        node_id: str | None = None,
        sample_input: dict[str, Any] | None = None,
        execution_kind: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        started_at = time.time()
        nodes = self.list_nodes(pipeline.id)
        if any(n.node_type == "join" or n.config.get("sql") or n.config.get("custom_sql") for n in nodes):
            return self._unsupported_evidence(started_at, "PIPELINE_NODE_UNSUPPORTED"), []
        executor = self._executors.get(pipeline.executor_id)
        if not pipeline.executor_id or executor is None:
            return self._unsupported_evidence(started_at, "PIPELINE_EXECUTOR_MISSING"), []
        try:
            result = executor(
                pipeline=pipeline,
                nodes=nodes,
                node_id=node_id,
                sample_input=sample_input or {},
                execution_kind=execution_kind,
            )
            if not isinstance(result, dict):
                raise ValueError("executor result must be a mapping")
            output_ref = str(result.get("output_ref") or "")
            if not output_ref:
                raise ValueError("executor success requires output_ref")
            rows_read = int(result.get("rows_read", 0))
            rows_written = int(result.get("rows_written", 0))
            if rows_read < 0 or rows_written < 0:
                raise ValueError("row counts must be non-negative")
            finished_at = time.time()
            evidence = {
                "mode": "live",
                "status": "succeeded",
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": max(0, int((finished_at - started_at) * 1000)),
                "executor_id": pipeline.executor_id,
                "input_ref": str(result.get("input_ref") or ""),
                "output_ref": output_ref,
                "rows_read": rows_read,
                "rows_written": rows_written,
                "lineage_ref": str(result.get("lineage_ref") or ""),
                "quality_ref": str(result.get("quality_ref") or ""),
                "error_code": "",
                "error_message": "",
                "rows_processed": rows_written,
                "error": "",
            }
            output_rows = result.get("output_rows") or []
            if not isinstance(output_rows, list) or not all(isinstance(row, dict) for row in output_rows):
                raise ValueError("output_rows must be a list of mappings")
            return evidence, output_rows
        except Exception as exc:
            finished_at = time.time()
            message = self._safe_error(exc)
            return {
                "mode": "live",
                "status": "failed",
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": max(0, int((finished_at - started_at) * 1000)),
                "executor_id": pipeline.executor_id,
                "input_ref": "",
                "output_ref": "",
                "rows_read": 0,
                "rows_written": 0,
                "lineage_ref": "",
                "quality_ref": "",
                "error_code": "PIPELINE_EXECUTOR_FAILED",
                "error_message": message,
                "rows_processed": 0,
                "error": message,
            }, []

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


def get_engine() -> PipelineEngine:
    return PipelineEngine()
