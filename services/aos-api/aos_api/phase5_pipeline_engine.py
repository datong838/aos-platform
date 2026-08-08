"""Phase 5 · Pipeline 核心引擎.

Pipelines + Nodes + Edges + Proposals + Schedules + ScheduleRuns + Datasets + DatasetBuilds + HealthChecks.
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import copy
import math
import queue
import threading
import time
import uuid
from typing import Any, Callable
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from aos_api.public_contracts import redact_sensitive
from aos_api.tenant_scope import TenantScope

_LOCK = threading.RLock()


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
    write_mode: str = "SNAPSHOT"  # SNAPSHOT|APPEND|MERGE|UPDATE|DELETE|UPSERT
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
                    inst._pipelines: dict[tuple[str, str, str], Pipeline] = {}
                    inst._nodes: dict[tuple[str, str, str], PipelineNode] = {}
                    inst._edges: dict[tuple[str, str, str], PipelineEdge] = {}
                    inst._proposals: dict[tuple[str, str, str], PipelineProposal] = {}
                    inst._history: dict[tuple[str, str, str], PipelineHistory] = {}
                    inst._schedules: dict[tuple[str, str, str], Schedule] = {}
                    inst._schedule_runs: dict[tuple[str, str, str], ScheduleRun] = {}
                    inst._datasets: dict[tuple[str, str, str], Dataset] = {}
                    inst._builds: dict[tuple[str, str, str], DatasetBuild] = {}
                    inst._health: dict[tuple[str, str, str], HealthCheck] = {}
                    inst._sync_configs: dict[tuple[str, str, str], SyncConfig] = {}
                    inst._executors: dict[str, Callable[..., dict[str, Any]]] = {}
                    inst._evidence_resolvers: dict[str, Callable[[str], bool]] = {}
                    inst._persisted_graph_ids: set[tuple[str, str, str]] = set()
                    cls._instance = inst
        return cls._instance

    # ── Pipelines ──
    def create_pipeline(self, scope: TenantScope, name: str, **kwargs: Any) -> Pipeline:
        with _LOCK:
            pl = Pipeline(name=name, **kwargs)
            self._pipelines[self._tenant_key(scope, pl.id)] = pl
            self._add_history(scope, pl.id, "created", "Pipeline created")
            return pl

    def get_pipeline(self, scope: TenantScope, pl_id: str) -> Pipeline | None:
        return self._pipelines.get(self._tenant_key(scope, pl_id))

    def list_pipelines(
        self,
        scope: TenantScope,
        search: str | None = None,
        status: str | None = None,
        pipeline_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> tuple[list[Pipeline], int]:
        items = [item for key, item in self._pipelines.items() if key[:2] == scope.key]
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

    def update_pipeline(self, scope: TenantScope, pl_id: str, **kwargs: Any) -> Pipeline:
        with _LOCK:
            pl = self._pipelines.get(self._tenant_key(scope, pl_id))
            if pl is None:
                raise KeyError(f"Pipeline {pl_id} not found")
            for k, v in kwargs.items():
                if hasattr(pl, k) and k != "id":
                    setattr(pl, k, v)
            pl.updated_at = time.time()
            self._add_history(scope, pl_id, "updated", f"Updated: {list(kwargs.keys())}")
            return pl

    def delete_pipeline(self, scope: TenantScope, pl_id: str) -> bool:
        with _LOCK:
            existed = self._pipelines.pop(self._tenant_key(scope, pl_id), None) is not None
            if existed:
                for key, node in list(self._nodes.items()):
                    if key[:2] == scope.key and node.pipeline_id == pl_id:
                        self._nodes.pop(key, None)
                for key, edge in list(self._edges.items()):
                    if key[:2] == scope.key and edge.pipeline_id == pl_id:
                        self._edges.pop(key, None)
            return existed

    # ── Bundle YAML seeding (替代 demo fallback) ──
    _BUNDLE_DISPLAY_NAMES: dict[str, str] = {
        "Shop": "栖月汇-店铺", "Product": "栖月汇-商品",
        "ProductSku": "栖月汇-商品SKU", "Category": "栖月汇-类目",
        "Order": "栖月汇-订单", "OrderLine": "栖月汇-订单明细",
        "Shipment": "栖月汇-发货", "CustomerLite": "栖月汇-会员",
    }

    def seed_from_bundles(self, scope: TenantScope, bundles_dir: str) -> int:
        """从 bundles YAML 加载真实栖月汇管道（幂等）。

        替代 W3-C6 demo fallback：服务启动时从 YAML 映射文件构造
        真实的 Pipeline + Source/Transform/Sink 节点 + 连线。
        Source 节点 config 包含 site_filter 等真实过滤条件。
        """
        import os
        import yaml

        bundles_path = os.path.abspath(bundles_dir)
        if not os.path.isdir(bundles_path):
            return 0

        count = 0
        for fname in sorted(os.listdir(bundles_path)):
            if not (fname.startswith("p") and fname.endswith(".yaml")):
                continue
            fpath = os.path.join(bundles_path, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except Exception:
                continue
            if not data or not isinstance(data, dict):
                continue
            raw_pid = str(data.get("pipeline_id") or "")
            if not raw_pid:
                continue

            # 幂等：已存在则跳过
            # ID 格式：文件名首字母大写 + "-qyh"（与 d2_8 脚本对齐）
            file_stem = os.path.splitext(fname)[0]  # e.g. "p02-product"
            pl_id = f"{file_stem[0].upper()}{file_stem[1:]}-qyh"  # "P02-product-qyh"
            if self.get_pipeline(scope, pl_id) is not None:
                continue

            source_table = str(data.get("source_table") or "")
            target_ot = str(data.get("target_ot") or raw_pid)
            primary_key = str(data.get("primary_key") or "")
            site_filter = str(data.get("site_filter") or "")
            incremental_strategy = str(data.get("incremental_strategy") or "snapshot")
            unique_key_pattern = str(data.get("unique_key_pattern") or "")
            soft_delete = data.get("soft_delete") or {}
            validation = data.get("validation") or {}
            field_mappings = data.get("field_mappings") or []
            incremental_cursor = data.get("incremental_cursor") or {}
            notes = data.get("notes") or []

            display_name = self._BUNDLE_DISPLAY_NAMES.get(target_ot, f"栖月汇-{target_ot}")

            # 创建 Pipeline
            pl = self.create_pipeline(
                scope, display_name,
                description=f"栖月汇微商城 · {target_ot} · {source_table}",
                pipeline_type="Batch",
                status="active",
                owner="data-team",
                tags=["栖月汇", "niushop", target_ot],
                write_mode="SNAPSHOT",
            )
            # 删除 create_pipeline 产生的随机 ID 条目，替换为确定性 ID
            random_id = pl.id
            self._pipelines.pop(self._tenant_key(scope, random_id), None)
            pl.id = pl_id
            self._pipelines[self._tenant_key(scope, pl_id)] = pl
            self._add_history(scope, pl_id, "created", f"从 YAML 加载: {fname}")
            count += 1

            # Source 节点
            src_config = {
                "source_id": "niushop-qyh",
                "source_table": source_table,
                "primary_key": primary_key,
                "site_filter": site_filter,
                "incremental_strategy": incremental_strategy,
                "incremental_cursor": incremental_cursor,
                "unique_key_pattern": unique_key_pattern,
                "soft_delete": soft_delete,
                "validation": validation,
                "notes": notes,
            }
            src_node = self.add_node(
                scope, pl_id, "source",
                node_type="source", position_x=60.0, position_y=60.0,
                config=src_config, status="idle",
            )

            # Transform 节点
            xf_config = {
                "expression": "row",
                "filter": site_filter,
                "field_mappings": field_mappings,
                "target_ot": target_ot,
            }
            xf_node = self.add_node(
                scope, pl_id, "transform",
                node_type="transform", position_x=320.0, position_y=60.0,
                config=xf_config, status="idle",
            )

            # Sink 节点
            sink_config = {
                "target_ot": target_ot,
                "write_mode": "SNAPSHOT",
                "unique_key_pattern": unique_key_pattern,
            }
            sink_node = self.add_node(
                scope, pl_id, "sink",
                node_type="sink", position_x=580.0, position_y=60.0,
                config=sink_config, status="idle",
            )

            # 连线
            self.add_edge(scope, pl_id, src_node.id, xf_node.id, label="")
            self.add_edge(scope, pl_id, xf_node.id, sink_node.id, label="")

        return count

    # ── Nodes ──
    def add_node(self, scope: TenantScope, pipeline_id: str, name: str, **kwargs: Any) -> PipelineNode:
        with _LOCK:
            node = PipelineNode(pipeline_id=pipeline_id, name=name, **kwargs)
            self._nodes[self._tenant_key(scope, node.id)] = node
            return node

    def get_node(self, scope: TenantScope, node_id: str) -> PipelineNode | None:
        return self._nodes.get(self._tenant_key(scope, node_id))

    def list_nodes(self, scope: TenantScope, pipeline_id: str) -> list[PipelineNode]:
        return [n for key, n in self._nodes.items() if key[:2] == scope.key and n.pipeline_id == pipeline_id]

    def update_node(self, scope: TenantScope, node_id: str, **kwargs: Any) -> PipelineNode:
        with _LOCK:
            node = self._nodes.get(self._tenant_key(scope, node_id))
            if node is None:
                raise KeyError(f"Node {node_id} not found")
            for k, v in kwargs.items():
                if hasattr(node, k) and k != "id":
                    setattr(node, k, v)
            node.updated_at = time.time()
            return node

    def delete_node(self, scope: TenantScope, node_id: str) -> bool:
        with _LOCK:
            return self._nodes.pop(self._tenant_key(scope, node_id), None) is not None

    # ── Edges ──
    def add_edge(self, scope: TenantScope, pipeline_id: str, source_node_id: str, target_node_id: str, **kwargs: Any) -> PipelineEdge:
        with _LOCK:
            edge = PipelineEdge(
                pipeline_id=pipeline_id, source_node_id=source_node_id, target_node_id=target_node_id, **kwargs
            )
            self._edges[self._tenant_key(scope, edge.id)] = edge
            return edge

    def list_edges(self, scope: TenantScope, pipeline_id: str) -> list[PipelineEdge]:
        return [e for key, e in self._edges.items() if key[:2] == scope.key and e.pipeline_id == pipeline_id]

    def delete_edge(self, scope: TenantScope, edge_id: str) -> bool:
        with _LOCK:
            return self._edges.pop(self._tenant_key(scope, edge_id), None) is not None

    # ── Graph ──
    def _snapshot_graph_locked(self, scope: TenantScope, pl_id: str) -> dict[str, Any]:
        pipeline = self.get_pipeline(scope, pl_id)
        if pipeline is None:
            raise KeyError(f"Pipeline {pl_id} not found")
        nodes = self.list_nodes(scope, pl_id)
        edges = self.list_edges(scope, pl_id)
        return {
            "pipeline_id": pl_id,
            "nodes": [n.model_dump() for n in nodes],
            "edges": [e.model_dump() for e in edges],
            "node_count": len(nodes),
            "edge_count": len(edges),
            "pipeline_type": pipeline.pipeline_type,
            "write_mode": pipeline.write_mode,
        }

    def _hydrate_persisted_graph_locked(self, scope: TenantScope, payload: dict[str, Any]) -> None:
        pl_id = str(payload.get("pipeline_id") or "")
        if not pl_id:
            raise ValueError("persisted graph requires pipeline_id")
        nodes = [PipelineNode.model_validate(node) for node in payload.get("nodes") or []]
        edges = [PipelineEdge.model_validate(edge) for edge in payload.get("edges") or []]
        for node in nodes:
            current = self._nodes.get(self._tenant_key(scope, node.id))
            if current is not None and current.pipeline_id != pl_id:
                raise ValueError(f"node id belongs to another pipeline: {node.id}")
        for edge in edges:
            current = self._edges.get(self._tenant_key(scope, edge.id))
            if current is not None and current.pipeline_id != pl_id:
                raise ValueError(f"edge id belongs to another pipeline: {edge.id}")
        pipeline_key = self._tenant_key(scope, pl_id)
        pipeline = self._pipelines.get(pipeline_key)
        if pipeline is None:
            pipeline = Pipeline(id=pl_id, name=str(payload.get("name") or pl_id))
            self._pipelines[pipeline_key] = pipeline
        pipeline.pipeline_type = str(payload.get("pipeline_type") or pipeline.pipeline_type)
        pipeline.write_mode = str(payload.get("write_mode") or pipeline.write_mode)
        for key, node in list(self._nodes.items()):
            if key[:2] == scope.key and node.pipeline_id == pl_id:
                self._nodes.pop(key, None)
        for key, edge in list(self._edges.items()):
            if key[:2] == scope.key and edge.pipeline_id == pl_id:
                self._edges.pop(key, None)
        self._nodes.update({self._tenant_key(scope, node.id): node for node in nodes})
        self._edges.update({self._tenant_key(scope, edge.id): edge for edge in edges})
        self._persisted_graph_ids.add(pipeline_key)

    def get_graph(self, scope: TenantScope, pl_id: str) -> dict[str, Any]:
        from aos_api.data_os_store import load_phase5_pipeline_graph

        with _LOCK:
            persisted = load_phase5_pipeline_graph(scope, pl_id)
            if persisted is not None:
                self._hydrate_persisted_graph_locked(scope, persisted)
                return copy.deepcopy(persisted)
            return copy.deepcopy(self._snapshot_graph_locked(scope, pl_id))

    def replace_graph(
        self,
        scope: TenantScope,
        pl_id: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        *,
        pipeline_type: str | None = None,
        write_mode: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        with _LOCK:
            return self._replace_graph_locked(
                scope,
                pl_id,
                nodes,
                edges,
                pipeline_type=pipeline_type,
                write_mode=write_mode,
                name=name,
            )

    def _replace_graph_locked(
        self,
        scope: TenantScope,
        pl_id: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        *,
        pipeline_type: str | None = None,
        write_mode: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Validate and atomically replace a pipeline graph.

        Canvas pipeline ids may originate from the data-platform store rather than
        the Phase-5 store.  The first real save creates the Phase-5 graph owner with
        the same id; subsequent reads and writes therefore use one graph source.
        """
        node_ids: set[str] = set()
        prepared_nodes: list[PipelineNode] = []
        now = time.time()
        for raw in nodes:
            node_id = str(raw.get("id") or "").strip()
            node_name = str(raw.get("name") or "").strip()
            if not node_id or not node_name:
                raise ValueError("graph nodes require non-empty id and name")
            if node_id in node_ids:
                raise ValueError(f"duplicate node id: {node_id}")
            x = float(raw.get("position_x", 0.0))
            y = float(raw.get("position_y", 0.0))
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError(f"node {node_id} position must be finite")
            node_ids.add(node_id)
            prepared_nodes.append(
                PipelineNode(
                    id=node_id,
                    pipeline_id=pl_id,
                    name=node_name,
                    node_type=str(raw.get("node_type") or "transform"),
                    position_x=x,
                    position_y=y,
                    config=copy.deepcopy(raw.get("config") or {}),
                    status=str(raw.get("status") or "idle"),
                    created_at=float(raw.get("created_at") or now),
                    updated_at=now,
                )
            )

        prepared_edges: list[PipelineEdge] = []
        edge_ids: set[str] = set()
        pairs: set[tuple[str, str]] = set()
        adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for raw in edges:
            source = str(raw.get("source_node_id") or "").strip()
            target = str(raw.get("target_node_id") or "").strip()
            if source not in node_ids or target not in node_ids:
                raise ValueError(f"edge endpoint not found: {source} -> {target}")
            if source == target:
                raise ValueError(f"self edge is not allowed: {source}")
            if (source, target) in pairs:
                raise ValueError(f"duplicate edge: {source} -> {target}")
            edge_id = str(raw.get("id") or ("pe-" + uuid.uuid4().hex[:8])).strip()
            if edge_id in edge_ids:
                raise ValueError(f"duplicate edge id: {edge_id}")
            pairs.add((source, target))
            edge_ids.add(edge_id)
            adjacency[source].append(target)
            prepared_edges.append(
                PipelineEdge(
                    id=edge_id,
                    pipeline_id=pl_id,
                    source_node_id=source,
                    target_node_id=target,
                    label=str(raw.get("label") or ""),
                )
            )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise ValueError("pipeline graph must be acyclic")
            if node_id in visited:
                return
            visiting.add(node_id)
            for target in adjacency[node_id]:
                visit(target)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in node_ids:
            visit(node_id)

        allowed_modes = {"SNAPSHOT", "APPEND", "MERGE", "UPDATE", "DELETE", "UPSERT"}
        if write_mode is not None and write_mode not in allowed_modes:
            raise ValueError(f"unsupported write mode: {write_mode}")
        allowed_types = {"ETL", "ELT", "Streaming", "Batch"}
        if pipeline_type is not None and pipeline_type not in allowed_types:
            raise ValueError(f"unsupported pipeline type: {pipeline_type}")

        from aos_api.data_os_store import persist_phase5_pipeline_graph

        with _LOCK:
            for node in prepared_nodes:
                current = self._nodes.get(self._tenant_key(scope, node.id))
                if current is not None and current.pipeline_id != pl_id:
                    raise ValueError(f"node id belongs to another pipeline: {node.id}")
            for edge in prepared_edges:
                current = self._edges.get(self._tenant_key(scope, edge.id))
                if current is not None and current.pipeline_id != pl_id:
                    raise ValueError(f"edge id belongs to another pipeline: {edge.id}")
            pipeline_key = self._tenant_key(scope, pl_id)
            pipeline = self._pipelines.get(pipeline_key)
            target_name = (name or (pipeline.name if pipeline else pl_id)).strip() or pl_id
            target_type = pipeline_type or (pipeline.pipeline_type if pipeline else "ETL")
            target_write_mode = write_mode or (pipeline.write_mode if pipeline else "SNAPSHOT")
            committed = persist_phase5_pipeline_graph(
                scope,
                {
                    "pipeline_id": pl_id,
                    "name": target_name,
                    "nodes": [node.model_dump() for node in prepared_nodes],
                    "edges": [edge.model_dump() for edge in prepared_edges],
                    "node_count": len(prepared_nodes),
                    "edge_count": len(prepared_edges),
                    "pipeline_type": target_type,
                    "write_mode": target_write_mode,
                }
            )
            if pipeline is None:
                pipeline = Pipeline(id=pl_id, name=target_name)
                self._pipelines[pipeline_key] = pipeline
            pipeline.pipeline_type = target_type
            pipeline.write_mode = target_write_mode
            pipeline.updated_at = now

            for key, node in list(self._nodes.items()):
                if key[:2] == scope.key and node.pipeline_id == pl_id:
                    self._nodes.pop(key, None)
            for key, edge in list(self._edges.items()):
                if key[:2] == scope.key and edge.pipeline_id == pl_id:
                    self._edges.pop(key, None)
            self._nodes.update({self._tenant_key(scope, node.id): node for node in prepared_nodes})
            self._edges.update({self._tenant_key(scope, edge.id): edge for edge in prepared_edges})
            self._persisted_graph_ids.add(pipeline_key)
            self._add_history(scope, pl_id, "updated", "Canvas graph saved")
            return copy.deepcopy(committed)

    # ── Files tree ──
    def get_files(self, scope: TenantScope, pl_id: str) -> list[dict[str, Any]]:
        pl = self.get_pipeline(scope, pl_id)
        if pl is None:
            raise KeyError(f"Pipeline {pl_id} not found")
        nodes = self.list_nodes(scope, pl_id)
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
    def preview_node(self, scope: TenantScope, pl_id: str, node_id: str, limit: int = 20) -> dict[str, Any]:
        node = self._nodes.get(self._tenant_key(scope, node_id))
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
    def get_node_config(self, scope: TenantScope, pl_id: str, node_id: str) -> dict[str, Any]:
        node = self._nodes.get(self._tenant_key(scope, node_id))
        if node is None or node.pipeline_id != pl_id:
            raise KeyError(f"Node {node_id} not found in pipeline {pl_id}")
        return {"pipeline_id": pl_id, "node_id": node_id, "config": node.config}

    def update_node_config(self, scope: TenantScope, pl_id: str, node_id: str, config: dict[str, Any]) -> PipelineNode:
        with _LOCK:
            node = self._nodes.get(self._tenant_key(scope, node_id))
            if node is None or node.pipeline_id != pl_id:
                raise KeyError(f"Node {node_id} not found in pipeline {pl_id}")
            node.config = config
            node.updated_at = time.time()
            return node

    # ── Trial run ──
    def trial_run(self, scope: TenantScope, pl_id: str, node_id: str, sample_input: dict[str, Any] | None = None) -> dict[str, Any]:
        node = self._nodes.get(self._tenant_key(scope, node_id))
        if node is None or node.pipeline_id != pl_id:
            raise KeyError(f"Node {node_id} not found in pipeline {pl_id}")
        pl = self.get_pipeline(scope, pl_id)
        if pl is None:
            raise KeyError(f"Pipeline {pl_id} not found")
        evidence, output_rows = self._execute(
            scope,
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
    def create_proposal(self, scope: TenantScope, pipeline_id: str, title: str, **kwargs: Any) -> PipelineProposal:
        with _LOCK:
            pp = PipelineProposal(pipeline_id=pipeline_id, title=title, **kwargs)
            self._proposals[self._tenant_key(scope, pp.id)] = pp
            return pp

    def get_proposal(self, scope: TenantScope, pp_id: str) -> PipelineProposal | None:
        return self._proposals.get(self._tenant_key(scope, pp_id))

    def list_proposals(self, scope: TenantScope, pipeline_id: str, status: str | None = None) -> list[PipelineProposal]:
        items = [p for key, p in self._proposals.items() if key[:2] == scope.key and p.pipeline_id == pipeline_id]
        if status:
            items = [p for p in items if p.status == status]
        return items

    def discard_proposal(self, scope: TenantScope, pipeline_id: str, pp_id: str) -> PipelineProposal:
        with _LOCK:
            pp = self._proposals.get(self._tenant_key(scope, pp_id))
            if pp is None or pp.pipeline_id != pipeline_id:
                raise KeyError(f"Proposal {pp_id} not found in pipeline {pipeline_id}")
            pp.status = "discarded"
            pp.updated_at = time.time()
            return pp

    def approve_proposal(self, scope: TenantScope, pipeline_id: str, pp_id: str) -> PipelineProposal:
        """审批提案：pending → approved（D4 修复：补齐 approved 中间态）。"""
        with _LOCK:
            pp = self._proposals.get(self._tenant_key(scope, pp_id))
            if pp is None or pp.pipeline_id != pipeline_id:
                raise KeyError(f"Proposal {pp_id} not found in pipeline {pipeline_id}")
            if pp.status != "pending":
                raise ValueError(f"Proposal {pp_id} status is '{pp.status}', expected 'pending'")
            pp.status = "approved"
            pp.updated_at = time.time()
            return pp

    def merge_proposal(self, scope: TenantScope, pipeline_id: str, pp_id: str) -> PipelineProposal:
        with _LOCK:
            pp = self._proposals.get(self._tenant_key(scope, pp_id))
            if pp is None or pp.pipeline_id != pipeline_id:
                raise KeyError(f"Proposal {pp_id} not found in pipeline {pipeline_id}")
            # D4 修复：merge 前必须先 approve（pending → approved → merged）
            if pp.status != "approved":
                raise ValueError(
                    f"Proposal {pp_id} status is '{pp.status}', expected 'approved'. "
                    f"Call approve_proposal() first."
                )
            pp.status = "merged"
            pp.updated_at = time.time()
            self._add_history(scope, pipeline_id, "updated", f"Merged proposal {pp_id}")
            return pp

    # ── History ──
    def _add_history(self, scope: TenantScope, pipeline_id: str, action: str, detail: str = "") -> None:
        h = PipelineHistory(pipeline_id=pipeline_id, action=action, detail=detail)
        self._history[self._tenant_key(scope, h.id)] = h

    def list_history(self, scope: TenantScope, pipeline_id: str) -> list[PipelineHistory]:
        items = [h for key, h in self._history.items() if key[:2] == scope.key and h.pipeline_id == pipeline_id]
        items.sort(key=lambda h: h.created_at, reverse=True)
        return items

    # ── Schedules ──
    def create_schedule(self, scope: TenantScope, name: str, **kwargs: Any) -> Schedule:
        with _LOCK:
            sc = Schedule(name=name, **kwargs)
            self._schedules[self._tenant_key(scope, sc.id)] = sc
            return sc

    def get_schedule(self, scope: TenantScope, sc_id: str) -> Schedule | None:
        return self._schedules.get(self._tenant_key(scope, sc_id))

    def list_schedules(
        self,
        scope: TenantScope,
        search: str | None = None,
        status: str | None = None,
        trigger_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Schedule], int]:
        items = [item for key, item in self._schedules.items() if key[:2] == scope.key]
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

    def update_schedule(self, scope: TenantScope, sc_id: str, **kwargs: Any) -> Schedule:
        with _LOCK:
            sc = self._schedules.get(self._tenant_key(scope, sc_id))
            if sc is None:
                raise KeyError(f"Schedule {sc_id} not found")
            for k, v in kwargs.items():
                if hasattr(sc, k) and k != "id":
                    setattr(sc, k, v)
            sc.updated_at = time.time()
            return sc

    def run_schedule(self, scope: TenantScope, sc_id: str) -> ScheduleRun:
        started_at = time.time()
        with _LOCK:
            sc = self._schedules.get(self._tenant_key(scope, sc_id))
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
                pipeline = self.get_pipeline(scope, pipeline_id)
                if pipeline is None:
                    run = ScheduleRun(
                        schedule_id=sc_id,
                        **self._unsupported_evidence(started_at, "PIPELINE_NOT_FOUND"),
                    )
                    dispatch = None
                else:
                    preflight = self._preflight(scope, pipeline, started_at)
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
                        self._schedule_runs[self._tenant_key(scope, run.id)] = run
                        dispatch = self._start_dispatch(
                            scope,
                            pipeline,
                            node_id=None,
                            sample_input={},
                            execution_kind="schedule",
                            started_at=started_at,
                        )
            self._schedule_runs[self._tenant_key(scope, run.id)] = run

        if dispatch is not None:
            evidence, _ = self._collect_dispatch(dispatch)
            with _LOCK:
                for key, value in evidence.items():
                    setattr(run, key, value)

        with _LOCK:
            if pipeline_id:
                self._add_history(
                    scope,
                    pipeline_id,
                    "run",
                    "status={} executor={} output={}".format(
                        run.status,
                        run.executor_id or "-",
                        str(redact_sensitive(run.output_ref)) if run.output_ref else "-",
                    ),
                )
            # B2 · Schedule → SyncTask 双记录（按 pipeline_id 松散匹配）
            # 不在锁里等待外部 sync 引擎导入，锁释放后再写入。
            copied = run.model_copy(deep=True)

        self._write_syncrun_after_schedule(scope, pipeline_id, copied)
        return copied

    def _write_syncrun_after_schedule(
        self,
        scope: TenantScope,
        pipeline_id: str,
        run: ScheduleRun,
    ) -> None:
        """Phase B2: schedule run 成功后, 同 pipeline_id 的 SyncTask 写一份 SyncRun 双记录.

        找不到 SyncTask 时静默跳过（不是所有 pipeline 都有 sync 映射）.
        """
        if not pipeline_id:
            return
        try:
            from aos_api.phase6_datasource_engine import (
                get_engine as p6_get_engine,
            )
        except Exception:
            return
        try:
            p6 = p6_get_engine()
            items, _ = p6.list_sync_tasks(scope=scope)
            st = next(
                (s for s in items if (s.config or {}).get("pipeline_id") == pipeline_id),
                None,
            )
            if st is None:
                return
            finished = run.finished_at or run.started_at
            duration_ms = max(
                1,
                int(run.duration_ms or ((finished - run.started_at) * 1000)),
            )
            rows = int(
                run.rows_written
                if hasattr(run, "rows_written")
                else (getattr(run, "rows_processed", 0) or 0)
            )
            # 直接在 P6 侧构造 SyncRun 记录, 镜像 run_sync_task 路径的双写结构.
            # Phase6 _LOCK 是模块级 (aos_api.phase6_datasource_engine._LOCK).
            import aos_api.phase6_datasource_engine as _p6_mod
            from aos_api.phase6_datasource_engine import SyncRun
            sr = SyncRun(
                sync_id=st.id,
                status="success" if run.status in {"success", "succeeded"} else "failed",
                started_at=run.started_at,
                finished_at=finished,
                duration_ms=duration_ms,
                rows_synced=rows,
                error_code=(
                    "" if run.status in {"success", "succeeded"}
                    else (getattr(run, "error_code", "") or "SCHEDULE_FAILED")
                ),
                error=(
                    "" if run.status in {"success", "succeeded"}
                    else str(redact_sensitive(getattr(run, "error_message") or getattr(run, "error") or ""))[:500]
                ),
                pipeline_id=pipeline_id,
                org_id=scope.org_id,
                project_id=scope.project_id,
            )
            with _p6_mod._LOCK:
                p6._sync_runs[sr.id] = sr
                if scope.org_id and scope.project_id:
                    p6._scoped_sync_runs[(scope.org_id, scope.project_id, sr.id)] = sr
        except Exception:
            # 双记录写入失败不能影响 Schedule 主路径
            return

    def execute_pipeline_once(
        self, scope: TenantScope, pipeline_id: str,
    ) -> dict[str, Any]:
        """Phase B1: 直接执行一次 Pipeline (不经过 Schedule).

        返回: {ok, rows_written, duration_ms, error_code, error_message}
        供 Phase6 run_sync_task 直接复用.
        """
        started = time.time()
        with _LOCK:
            pipeline = self.get_pipeline(scope, pipeline_id)
            if pipeline is None:
                return {
                    "ok": False,
                    "rows_written": 0,
                    "duration_ms": 0,
                    "error_code": "PIPELINE_NOT_FOUND",
                    "error_message": f"Pipeline {pipeline_id} not found in scope {scope.key}",
                }
            preflight = self._preflight(scope, pipeline, started)
            if preflight is not None:
                return {
                    "ok": False,
                    "rows_written": 0,
                    "duration_ms": max(1, int((time.time() - started) * 1000)),
                    "error_code": str(preflight.get("error_code") or "PREFLIGHT_FAIL"),
                    "error_message": str(preflight.get("error_message") or "preflight blocked execution"),
                }
            dispatch = self._start_dispatch(
                scope,
                pipeline,
                node_id=None,
                sample_input={},
                execution_kind="direct_sync",
                started_at=started,
            )
        evidence, _ = self._collect_dispatch(dispatch)
        # ScheduleRun status 用 "succeeded"，SyncRun 用 "success"；两者都算成功。
        ok = evidence.get("status") in {"success", "succeeded"}
        finished = time.time()
        duration_ms = max(1, int((finished - started) * 1000))
        rows = int(
            evidence.get("rows_written")
            or evidence.get("rows_processed")
            or 0
        )
        return {
            "ok": ok,
            "rows_written": rows,
            "duration_ms": duration_ms,
            "error_code": "" if ok else str(evidence.get("error_code") or "PIPELINE_EXEC_FAILED"),
            "error_message": (
                "" if ok else str(
                    evidence.get("error_message")
                    or evidence.get("error")
                    or "pipeline execution failed"
                )
            ),
        }

    def pause_schedule(self, scope: TenantScope, sc_id: str) -> Schedule:
        with _LOCK:
            sc = self._schedules.get(self._tenant_key(scope, sc_id))
            if sc is None:
                raise KeyError(f"Schedule {sc_id} not found")
            sc.status = "paused"
            sc.updated_at = time.time()
            return sc

    def list_schedule_runs(self, scope: TenantScope, sc_id: str) -> list[ScheduleRun]:
        with _LOCK:
            return [
                r.model_copy(deep=True)
                for key, r in self._schedule_runs.items()
                if key[:2] == scope.key and r.schedule_id == sc_id
            ]

    # ── Datasets ──
    @staticmethod
    def _tenant_key(scope: TenantScope, resource_id: str) -> tuple[str, str, str]:
        return scope.org_id, scope.project_id, resource_id

    def create_dataset(self, scope: TenantScope, name: str, **kwargs: Any) -> Dataset:
        with _LOCK:
            ds = Dataset(name=name, **kwargs)
            self._datasets[self._tenant_key(scope, ds.id)] = ds
            return ds

    def get_dataset(self, scope: TenantScope, ds_id: str) -> Dataset | None:
        return self._datasets.get(self._tenant_key(scope, ds_id))

    def list_datasets(
        self,
        scope: TenantScope,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Dataset], int]:
        items = [
            item for key, item in self._datasets.items() if key[:2] == scope.key
        ]
        if search:
            s = search.lower()
            items = [d for d in items if s in d.name.lower() or s in d.description.lower()]
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def preview_dataset(
        self, scope: TenantScope, ds_id: str, limit: int = 50
    ) -> dict[str, Any]:
        ds = self._datasets.get(self._tenant_key(scope, ds_id))
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
    def add_build(
        self, scope: TenantScope, dataset_id: str, **kwargs: Any
    ) -> DatasetBuild:
        with _LOCK:
            if self.get_dataset(scope, dataset_id) is None:
                raise KeyError(f"Dataset {dataset_id} not found")
            b = DatasetBuild(dataset_id=dataset_id, **kwargs)
            self._builds[self._tenant_key(scope, b.id)] = b
            return b

    def list_builds(
        self, scope: TenantScope, dataset_id: str
    ) -> list[DatasetBuild]:
        return [
            build
            for key, build in self._builds.items()
            if key[:2] == scope.key and build.dataset_id == dataset_id
        ]

    # ── Health ──
    def check_health(self, scope: TenantScope, ds_id: str) -> HealthCheck:
        with _LOCK:
            ds = self.get_dataset(scope, ds_id)
            if ds is None:
                raise KeyError(f"Dataset {ds_id} not found")
            # D4 修复：读 dataset.updated_at 计算真实 freshness_hours（原硬编码 1.5）
            now = time.time()
            freshness_hours = max(0.0, (now - ds.updated_at) / 3600.0)
            hc = HealthCheck(
                dataset_id=ds_id,
                status="healthy",
                null_rate=0.02,
                duplicate_rate=0.01,
                freshness_hours=freshness_hours,
            )
            self._health[self._tenant_key(scope, hc.id)] = hc
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

    def _preflight(self, scope: TenantScope, pipeline: Pipeline, started_at: float) -> dict[str, Any] | None:
        nodes = self.list_nodes(scope, pipeline.id)
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
        scope: TenantScope,
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
        nodes_snapshot = [copy.deepcopy(n) for n in self.list_nodes(scope, pipeline.id)]
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
                        scope=scope,
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
        scope: TenantScope,
        pipeline: Pipeline,
        *,
        node_id: str | None = None,
        sample_input: dict[str, Any] | None = None,
        execution_kind: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        started_at = time.time()
        with _LOCK:
            preflight = self._preflight(scope, pipeline, started_at)
            if preflight is not None:
                return preflight, []
            dispatch = self._start_dispatch(
                scope,
                pipeline,
                node_id=node_id,
                sample_input=sample_input or {},
                execution_kind=execution_kind,
                started_at=started_at,
            )
        return self._collect_dispatch(dispatch)

    def get_latest_health(
        self, scope: TenantScope, ds_id: str
    ) -> HealthCheck | None:
        items = [
            health
            for key, health in self._health.items()
            if key[:2] == scope.key and health.dataset_id == ds_id
        ]
        if not items:
            return None
        items.sort(key=lambda h: h.checked_at, reverse=True)
        return items[0]

    # ── Sync config ──
    def get_sync_config(self, scope: TenantScope, ds_id: str) -> SyncConfig:
        if self.get_dataset(scope, ds_id) is None:
            raise KeyError(f"Dataset {ds_id} not found")
        key = self._tenant_key(scope, ds_id)
        sc = self._sync_configs.get(key)
        if sc is None:
            sc = SyncConfig(dataset_id=ds_id)
            self._sync_configs[key] = sc
        return sc

    def set_sync_config(
        self, scope: TenantScope, ds_id: str, **kwargs: Any
    ) -> SyncConfig:
        with _LOCK:
            if self.get_dataset(scope, ds_id) is None:
                raise KeyError(f"Dataset {ds_id} not found")
            key = self._tenant_key(scope, ds_id)
            sc = self._sync_configs.get(key)
            if sc is None:
                sc = SyncConfig(dataset_id=ds_id)
                self._sync_configs[key] = sc
            for k, v in kwargs.items():
                if hasattr(sc, k) and k != "dataset_id":
                    setattr(sc, k, v)
            return sc

    # ── Util ──
    def reset(
        self,
        *,
        scope: TenantScope,
        purge_persisted: bool = False,
    ) -> None:
        with _LOCK:
            persisted_graph_ids = [key for key in self._persisted_graph_ids if key[:2] == scope.key]
            for store in (
                self._pipelines,
                self._nodes,
                self._edges,
                self._proposals,
                self._history,
                self._schedules,
                self._schedule_runs,
                self._datasets,
                self._builds,
                self._health,
                self._sync_configs,
            ):
                for key in [key for key in store if key[:2] == scope.key]:
                    store.pop(key)
            self._persisted_graph_ids.difference_update(persisted_graph_ids)
            if purge_persisted:
                from aos_api.data_os_store import delete_phase5_pipeline_graph

                for _, _, pipeline_id in persisted_graph_ids:
                    delete_phase5_pipeline_graph(scope, pipeline_id)

    def reset_all_for_tests(self) -> None:
        """测试基础设施专用；清空全部进程态，不得由租户路由调用。"""
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
            self._persisted_graph_ids.clear()


_engine_instance: PipelineEngine | None = None

def get_engine() -> PipelineEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = PipelineEngine()
    return _engine_instance
