"""W2-AL · Data Lineage 可视化引擎（#130 #131 #132）."""
from __future__ import annotations

import threading
import uuid
from datetime import date, datetime, timedelta

from pydantic import BaseModel

_MAX_VIEWS = 200
_MAX_COLUMN_INDEX = 200
_MAX_SCHEDULES = 200
_MAX_RUNS = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class LineageVisualizationError(Exception):
    """血缘可视化错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ColumnLineageSearchError(Exception):
    """列级血缘搜索错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LineageBuildTimelineError(Exception):
    """搭建时间线错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════ #130 Lineage Visualization ════════════════════

class LineageView(BaseModel):
    view_id: str = ""
    name: str
    description: str = ""
    root_dataset_rid: str
    graph_mode: str = "graph"
    direction: str = "both"
    depth: int = 3
    layout: str = "horizontal"
    color_by: str = "type"
    collapsed_nodes: list[str] = []
    highlighted_nodes: list[str] = []
    saved_by: str = ""
    is_public: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LineageGraphNode(BaseModel):
    node_id: str
    label: str
    node_type: str
    health_status: str = "healthy"
    color: str = ""
    x: float = 0.0
    y: float = 0.0


class LineageGraphEdge(BaseModel):
    edge_id: str
    source: str
    target: str
    label: str = ""
    edge_type: str = "reads"


class LineageGraph(BaseModel):
    view_id: str
    nodes: list[LineageGraphNode] = []
    edges: list[LineageGraphEdge] = []
    stats: dict = {}


_VALID_GRAPH_MODES = {"graph", "tree"}
_VALID_DIRECTIONS = {"upstream", "downstream", "both"}
_VALID_LAYOUTS = {"horizontal", "vertical", "radial"}
_VALID_COLOR_BY = {"type", "health", "status", "owner"}
_TYPE_COLORS = {
    "dataset": "#4A90D9",
    "transform": "#7B68EE",
    "ontology": "#20B2AA",
    "pipeline": "#FF8C00",
}
_HEALTH_COLORS = {
    "healthy": "#3CB371",
    "warning": "#FFD700",
    "critical": "#FF6347",
    "unknown": "#A9A9A9",
}
_NODE_TYPES = ["dataset", "transform", "ontology", "pipeline"]
_HEALTH_STATUSES = ["healthy", "warning", "critical", "unknown"]


def _fuzzy_match(keyword: str, text: str) -> bool:
    if not keyword:
        return True
    kw = keyword.lower()
    return kw in text.lower()


class LineageVisualizationEngine:
    """血缘可视化引擎（视图管理 + 图生成 + 着色/展开/分享）."""

    _instance: LineageVisualizationEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._views: dict[str, LineageView] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> LineageVisualizationEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── CRUD ──

    def register(self, view: LineageView) -> LineageView:
        if not view.name or not view.name.strip():
            raise LineageVisualizationError("MISSING_NAME", "view name is required")
        if not view.root_dataset_rid or not view.root_dataset_rid.strip():
            raise LineageVisualizationError("MISSING_DATASET", "root_dataset_rid is required")
        if view.graph_mode not in _VALID_GRAPH_MODES:
            raise LineageVisualizationError("INVALID_GRAPH_MODE",
                                            f"graph_mode must be one of {_VALID_GRAPH_MODES}")
        if view.direction not in _VALID_DIRECTIONS:
            raise LineageVisualizationError("INVALID_DIRECTION",
                                            f"direction must be one of {_VALID_DIRECTIONS}")
        if view.layout not in _VALID_LAYOUTS:
            raise LineageVisualizationError("INVALID_LAYOUT",
                                            f"layout must be one of {_VALID_LAYOUTS}")
        if not (1 <= view.depth <= 10):
            raise LineageVisualizationError("INVALID_DEPTH", "depth must be in [1, 10]")
        if view.color_by not in _VALID_COLOR_BY:
            raise LineageVisualizationError("INVALID_COLOR_BY",
                                            f"color_by must be one of {_VALID_COLOR_BY}")

        now = _utcnow()
        vid = f"lv-{uuid.uuid4().hex[:8]}"
        v = view.model_copy(update={"view_id": vid, "created_at": now, "updated_at": now})
        with self._lock:
            if len(self._views) >= _MAX_VIEWS:
                oldest = min(self._views.values(), key=lambda x: x.created_at)
                del self._views[oldest.view_id]
            self._views[vid] = v
        return v

    def get(self, view_id: str) -> LineageView:
        with self._lock:
            v = self._views.get(view_id)
        if v is None:
            raise LineageVisualizationError("NOT_FOUND", f"view {view_id} not found")
        return v

    def list(self, saved_by: str | None = None, graph_mode: str | None = None) -> list[LineageView]:
        with self._lock:
            results = list(self._views.values())
        if saved_by:
            results = [v for v in results if v.saved_by == saved_by]
        if graph_mode:
            results = [v for v in results if v.graph_mode == graph_mode]
        return sorted(results, key=lambda v: v.created_at, reverse=True)

    def update(self, view_id: str, updates: dict) -> LineageView:
        with self._lock:
            v = self._views.get(view_id)
            if v is None:
                raise LineageVisualizationError("NOT_FOUND", f"view {view_id} not found")
            if "graph_mode" in updates and updates["graph_mode"] not in _VALID_GRAPH_MODES:
                raise LineageVisualizationError("INVALID_GRAPH_MODE",
                                                f"graph_mode must be one of {_VALID_GRAPH_MODES}")
            if "direction" in updates and updates["direction"] not in _VALID_DIRECTIONS:
                raise LineageVisualizationError("INVALID_DIRECTION",
                                                f"direction must be one of {_VALID_DIRECTIONS}")
            if "layout" in updates and updates["layout"] not in _VALID_LAYOUTS:
                raise LineageVisualizationError("INVALID_LAYOUT",
                                                f"layout must be one of {_VALID_LAYOUTS}")
            if "depth" in updates and not (1 <= updates["depth"] <= 10):
                raise LineageVisualizationError("INVALID_DEPTH", "depth must be in [1, 10]")
            if "color_by" in updates and updates["color_by"] not in _VALID_COLOR_BY:
                raise LineageVisualizationError("INVALID_COLOR_BY",
                                                f"color_by must be one of {_VALID_COLOR_BY}")
            data = v.model_dump()
            data.update(updates)
            updated = LineageView(**{**data, "updated_at": _utcnow()})
            self._views[view_id] = updated
        return updated

    def delete(self, view_id: str) -> bool:
        with self._lock:
            if view_id in self._views:
                del self._views[view_id]
                return True
        return False

    # ── 图生成 ──

    def _generate_nodes_edges(self, view: LineageView) -> tuple[list[LineageGraphNode], list[LineageGraphEdge]]:
        nodes: list[LineageGraphNode] = []
        edges: list[LineageGraphEdge] = []
        root_id = view.root_dataset_rid

        nodes.append(LineageGraphNode(
            node_id=root_id,
            label=f"Dataset-{root_id[-6:]}",
            node_type="dataset",
            health_status="healthy",
        ))

        depth = view.depth
        directions: list[str] = []
        if view.direction in ("upstream", "both"):
            directions.append("upstream")
        if view.direction in ("downstream", "both"):
            directions.append("downstream")

        node_counter = 0
        for d in range(1, depth + 1):
            for direction in directions:
                nodes_per_level = 2 + (d % 2)
                for i in range(nodes_per_level):
                    node_counter += 1
                    node_type = _NODE_TYPES[node_counter % len(_NODE_TYPES)]
                    health = _HEALTH_STATUSES[node_counter % len(_HEALTH_STATUSES)]
                    node_id = f"{direction[:3]}-d{d}-{i}-{uuid.uuid4().hex[:4]}"
                    nodes.append(LineageGraphNode(
                        node_id=node_id,
                        label=f"{node_type.capitalize()}-{node_counter}",
                        node_type=node_type,
                        health_status=health,
                    ))

                    if d == 1:
                        if direction == "upstream":
                            edges.append(LineageGraphEdge(
                                edge_id=f"e-{uuid.uuid4().hex[:6]}",
                                source=node_id,
                                target=root_id,
                                edge_type="reads",
                            ))
                        else:
                            edges.append(LineageGraphEdge(
                                edge_id=f"e-{uuid.uuid4().hex[:6]}",
                                source=root_id,
                                target=node_id,
                                edge_type="produces",
                            ))
                    else:
                        prev_level_start = (d - 2) * len(directions) * 3 + 1
                        if prev_level_start < len(nodes):
                            parent_idx = prev_level_start + (i % max(1, d - 1))
                            if parent_idx < len(nodes):
                                parent_id = nodes[parent_idx].node_id
                                if direction == "upstream":
                                    edges.append(LineageGraphEdge(
                                        edge_id=f"e-{uuid.uuid4().hex[:6]}",
                                        source=node_id,
                                        target=parent_id,
                                        edge_type="reads",
                                    ))
                                else:
                                    edges.append(LineageGraphEdge(
                                        edge_id=f"e-{uuid.uuid4().hex[:6]}",
                                        source=parent_id,
                                        target=node_id,
                                        edge_type="produces",
                                    ))

        return nodes, edges

    def _apply_color_scheme(self, nodes: list[LineageGraphNode], color_by: str) -> None:
        for node in nodes:
            if color_by == "type":
                node.color = _TYPE_COLORS.get(node.node_type, "#A9A9A9")
            elif color_by == "health":
                node.color = _HEALTH_COLORS.get(node.health_status, "#A9A9A9")
            elif color_by == "status":
                node.color = "#3CB371" if node.health_status == "healthy" else "#FF6347"
            elif color_by == "owner":
                node.color = "#4A90D9"

    def _apply_layout(self, nodes: list[LineageGraphNode], layout: str,
                      collapsed: set[str]) -> None:
        visible = [n for n in nodes if n.node_id not in collapsed]
        n = len(visible)
        if n == 0:
            return

        if layout == "horizontal":
            cols = min(n, 5)
            for i, node in enumerate(visible):
                node.x = float(i % cols) * 150.0
                node.y = float(i // cols) * 100.0
        elif layout == "vertical":
            rows = min(n, 5)
            for i, node in enumerate(visible):
                node.x = float(i // rows) * 150.0
                node.y = float(i % rows) * 100.0
        elif layout == "radial":
            center_x, center_y = 200.0, 200.0
            if n == 1:
                visible[0].x = center_x
                visible[0].y = center_y
            else:
                for i, node in enumerate(visible):
                    angle = 2 * 3.14159 * i / n
                    radius = 80.0 + 30.0 * (i % 3)
                    node.x = center_x + radius * (1 if i % 2 == 0 else -1)
                    node.y = center_y + radius * (0.5 if i % 3 == 0 else -0.5)

    def _compute_stats(self, nodes: list[LineageGraphNode],
                       edges: list[LineageGraphEdge]) -> dict[str, int]:
        stats = {
            "node_count": len(nodes),
            "edge_count": len(edges),
        }
        type_counts: dict[str, int] = {}
        health_counts: dict[str, int] = {}
        for node in nodes:
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1
            health_counts[node.health_status] = health_counts.get(node.health_status, 0) + 1
        stats["types"] = type_counts
        stats["health"] = health_counts
        return stats

    def generate_graph(self, view_id: str) -> LineageGraph:
        view = self.get(view_id)
        nodes, edges = self._generate_nodes_edges(view)
        collapsed = set(view.collapsed_nodes)
        self._apply_color_scheme(nodes, view.color_by)
        self._apply_layout(nodes, view.layout, collapsed)
        highlighted = set(view.highlighted_nodes)
        visible_nodes = [n for n in nodes if n.node_id not in collapsed]
        visible_edges = [e for e in edges
                         if e.source not in collapsed and e.target not in collapsed]
        stats = self._compute_stats(visible_nodes, visible_edges)
        return LineageGraph(
            view_id=view_id,
            nodes=visible_nodes,
            edges=visible_edges,
            stats=stats,
        )

    def expand_node(self, view_id: str, node_id: str) -> LineageGraph:
        view = self.get(view_id)
        new_collapsed = [n for n in view.collapsed_nodes if n != node_id]
        updated = self.update(view_id, {"collapsed_nodes": new_collapsed})
        return self.generate_graph(updated.view_id)

    def collapse_node(self, view_id: str, node_id: str) -> LineageGraph:
        view = self.get(view_id)
        if node_id not in view.collapsed_nodes:
            new_collapsed = list(view.collapsed_nodes) + [node_id]
            self.update(view_id, {"collapsed_nodes": new_collapsed})
        return self.generate_graph(view_id)

    def color_by(self, view_id: str, color_scheme: str) -> LineageGraph:
        if color_scheme not in _VALID_COLOR_BY:
            raise LineageVisualizationError("INVALID_COLOR_BY",
                                            f"color_by must be one of {_VALID_COLOR_BY}")
        self.update(view_id, {"color_by": color_scheme})
        return self.generate_graph(view_id)

    def share_view(self, view_id: str, make_public: bool) -> LineageView:
        return self.update(view_id, {"is_public": make_public})

    def list_views_by_dataset(self, dataset_rid: str) -> list[LineageView]:
        with self._lock:
            results = [v for v in self._views.values()
                       if v.root_dataset_rid == dataset_rid]
        return sorted(results, key=lambda v: v.created_at, reverse=True)


_lineage_visualization_engine: LineageVisualizationEngine | None = None
_lineage_visualization_engine_lock = threading.Lock()


def get_lineage_visualization_engine() -> LineageVisualizationEngine:
    global _lineage_visualization_engine
    if _lineage_visualization_engine is None:
        with _lineage_visualization_engine_lock:
            if _lineage_visualization_engine is None:
                _lineage_visualization_engine = LineageVisualizationEngine.get_instance()
    return _lineage_visualization_engine


# ════════════════════ #131 Column Lineage Search ════════════════════

class ColumnIndexEntry(BaseModel):
    dataset_rid: str
    column_name: str
    data_type: str = "string"
    description: str = ""
    tags: list[str] = []
    last_updated: datetime | None = None


class ColumnTraceStep(BaseModel):
    dataset_rid: str
    column_name: str
    transform_expr: str = ""
    direction: str


class ColumnTraceResult(BaseModel):
    column: str
    dataset_rid: str
    direction: str
    depth: int
    path: list[ColumnTraceStep] = []


_VALID_TRACE_DIRECTIONS = {"upstream", "downstream"}


def _make_col_key(dataset_rid: str, column_name: str) -> str:
    return f"{dataset_rid}::{column_name}"


class ColumnLineageSearchEngine:
    """列级血缘搜索引擎（列索引 + 模糊搜索 + 列级追踪）."""

    _instance: ColumnLineageSearchEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._columns: dict[str, ColumnIndexEntry] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ColumnLineageSearchEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── CRUD ──

    def register_column(self, dataset_rid: str, column_name: str,
                        data_type: str = "string", description: str = "",
                        tags: list[str] | None = None) -> ColumnIndexEntry:
        if not dataset_rid or not dataset_rid.strip():
            raise ColumnLineageSearchError("MISSING_DATASET", "dataset_rid is required")
        if not column_name or not column_name.strip():
            raise ColumnLineageSearchError("MISSING_COLUMN", "column_name is required")

        now = _utcnow()
        entry = ColumnIndexEntry(
            dataset_rid=dataset_rid,
            column_name=column_name,
            data_type=data_type,
            description=description,
            tags=tags if tags is not None else [],
            last_updated=now,
        )
        key = _make_col_key(dataset_rid, column_name)
        with self._lock:
            if key not in self._columns and len(self._columns) >= _MAX_COLUMN_INDEX:
                oldest = min(self._columns.values(), key=lambda x: x.last_updated)
                old_key = _make_col_key(oldest.dataset_rid, oldest.column_name)
                del self._columns[old_key]
            self._columns[key] = entry
        return entry

    def get_column(self, dataset_rid: str, column_name: str) -> ColumnIndexEntry:
        key = _make_col_key(dataset_rid, column_name)
        with self._lock:
            entry = self._columns.get(key)
        if entry is None:
            raise ColumnLineageSearchError("NOT_FOUND",
                                           f"column {column_name} in dataset {dataset_rid} not found")
        return entry

    def list_columns(self, dataset_rid: str) -> list[ColumnIndexEntry]:
        with self._lock:
            results = [c for c in self._columns.values()
                       if c.dataset_rid == dataset_rid]
        return sorted(results, key=lambda c: c.column_name)

    def update_column(self, dataset_rid: str, column_name: str,
                      updates: dict) -> ColumnIndexEntry:
        key = _make_col_key(dataset_rid, column_name)
        with self._lock:
            entry = self._columns.get(key)
            if entry is None:
                raise ColumnLineageSearchError("NOT_FOUND",
                                               f"column {column_name} in dataset {dataset_rid} not found")
            data = entry.model_dump()
            data.update(updates)
            data["dataset_rid"] = dataset_rid
            data["column_name"] = column_name
            updated = ColumnIndexEntry(**{**data, "last_updated": _utcnow()})
            self._columns[key] = updated
        return updated

    def delete_column(self, dataset_rid: str, column_name: str) -> bool:
        key = _make_col_key(dataset_rid, column_name)
        with self._lock:
            if key in self._columns:
                del self._columns[key]
                return True
        return False

    # ── 搜索 ──

    def search_columns(self, keyword: str, data_type: str | None = None,
                       tag: str | None = None) -> list[ColumnIndexEntry]:
        with self._lock:
            results = list(self._columns.values())
        if keyword:
            results = [c for c in results if _fuzzy_match(keyword, c.column_name)]
        if data_type:
            results = [c for c in results if c.data_type.lower() == data_type.lower()]
        if tag:
            results = [c for c in results if tag in c.tags]
        return sorted(results, key=lambda c: c.last_updated, reverse=True)

    # ── 追踪 ──

    def trace_column(self, dataset_rid: str, column_name: str,
                     direction: str, max_depth: int = 3) -> ColumnTraceResult:
        if direction not in _VALID_TRACE_DIRECTIONS:
            raise ColumnLineageSearchError("INVALID_DIRECTION",
                                           f"direction must be one of {_VALID_TRACE_DIRECTIONS}")
        if not (1 <= max_depth <= 10):
            raise ColumnLineageSearchError("INVALID_DEPTH", "max_depth must be in [1, 10]")

        try:
            self.get_column(dataset_rid, column_name)
        except ColumnLineageSearchError:
            raise ColumnLineageSearchError("NOT_FOUND",
                                           f"column {column_name} in dataset {dataset_rid} not found")

        path: list[ColumnTraceStep] = []
        path.append(ColumnTraceStep(
            dataset_rid=dataset_rid,
            column_name=column_name,
            transform_expr="",
            direction=direction,
        ))

        for d in range(1, max_depth + 1):
            step_dataset = f"ri.foundry.main.dataset.{uuid.uuid4().hex[:12]}"
            step_column = f"{column_name}_{direction[:3]}_{d}"
            transforms = [
                f"CAST({column_name} AS string)",
                f"UPPER({column_name})",
                f"TRIM({column_name})",
                f"CONCAT({column_name}, '_suffix')",
                f"SUBSTRING({column_name}, 1, 10)",
            ]
            transform_expr = transforms[d % len(transforms)]
            path.append(ColumnTraceStep(
                dataset_rid=step_dataset,
                column_name=step_column,
                transform_expr=transform_expr,
                direction=direction,
            ))

        return ColumnTraceResult(
            column=column_name,
            dataset_rid=dataset_rid,
            direction=direction,
            depth=max_depth,
            path=path,
        )

    # ── 索引构建 ──

    def build_index(self, dataset_rid: str) -> int:
        if not dataset_rid or not dataset_rid.strip():
            raise ColumnLineageSearchError("MISSING_DATASET", "dataset_rid is required")

        sample_columns = [
            ("id", "long", "Unique identifier", ["primary_key"]),
            ("name", "string", "Display name", ["required"]),
            ("created_at", "timestamp", "Creation time", ["audit"]),
            ("updated_at", "timestamp", "Last update time", ["audit"]),
            ("status", "string", "Current status", ["status"]),
            ("description", "string", "Detailed description", []),
            ("owner", "string", "Owner identifier", ["ownership"]),
            ("tags", "string", "Comma-separated tags", ["metadata"]),
        ]

        count = 0
        for col_name, data_type, desc, tags in sample_columns:
            self.register_column(dataset_rid, col_name, data_type, desc, tags)
            count += 1
        return count


_column_lineage_search_engine: ColumnLineageSearchEngine | None = None
_column_lineage_search_engine_lock = threading.Lock()


def get_column_lineage_search_engine() -> ColumnLineageSearchEngine:
    global _column_lineage_search_engine
    if _column_lineage_search_engine is None:
        with _column_lineage_search_engine_lock:
            if _column_lineage_search_engine is None:
                _column_lineage_search_engine = ColumnLineageSearchEngine.get_instance()
    return _column_lineage_search_engine


# ════════════════════ #132 Lineage Build Timeline ════════════════════

class BuildSchedule(BaseModel):
    schedule_id: str = ""
    name: str
    pipeline_id: str
    cron_expression: str
    timezone: str = "UTC"
    status: str = "active"
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BuildRun(BaseModel):
    run_id: str = ""
    schedule_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    datasets_built: list[str] = []
    duration_ms: int = 0
    error_message: str = ""


class GanttTask(BaseModel):
    task_id: str
    name: str
    pipeline_id: str = ""
    start_time: datetime
    end_time: datetime
    status: str = "scheduled"
    dependencies: list[str] = []


class GanttChart(BaseModel):
    chart_id: str
    title: str
    start_date: date
    end_date: date
    tasks: list[GanttTask] = []


_VALID_SCHEDULE_STATUSES = {"active", "paused", "disabled"}
_VALID_RUN_STATUSES = {"pending", "running", "success", "failed", "cancelled"}


def _validate_cron(expr: str) -> bool:
    if not expr:
        return False
    parts = expr.strip().split()
    if len(parts) != 5:
        return False
    minute, hour, dom, month, dow = parts

    def _is_valid_field(field: str, min_val: int, max_val: int, allow_names: set[str] | None = None) -> bool:
        if field == "*":
            return True
        if "," in field:
            return all(_is_valid_field(p, min_val, max_val, allow_names) for p in field.split(","))
        if "/" in field:
            parts_step = field.split("/")
            if len(parts_step) != 2:
                return False
            base, step = parts_step
            if not _is_valid_field(base, min_val, max_val, allow_names):
                return False
            try:
                return int(step) > 0
            except ValueError:
                return False
        if "-" in field:
            range_parts = field.split("-")
            if len(range_parts) != 2:
                return False
            try:
                start = int(range_parts[0])
                end = int(range_parts[1])
                return min_val <= start <= end <= max_val
            except ValueError:
                return False
        try:
            val = int(field)
            return min_val <= val <= max_val
        except ValueError:
            if allow_names and field.lower() in allow_names:
                return True
            return False

    return (_is_valid_field(minute, 0, 59) and
            _is_valid_field(hour, 0, 23) and
            _is_valid_field(dom, 1, 31) and
            _is_valid_field(month, 1, 12) and
            _is_valid_field(dow, 0, 7))


def _compute_next_run_time(cron_expression: str, from_time: datetime) -> datetime:
    parts = cron_expression.strip().split()
    if len(parts) != 5:
        return from_time + timedelta(hours=1)
    minute, hour, dom, month, dow = parts

    def _field_matches(field: str, value: int) -> bool:
        if field == "*":
            return True
        if "," in field:
            return any(_field_matches(p, value) for p in field.split(","))
        if "/" in field:
            parts_step = field.split("/")
            if len(parts_step) != 2:
                return False
            base, step_str = parts_step
            try:
                step = int(step_str)
            except ValueError:
                return False
            if base == "*":
                return value % step == 0
            if "-" in base:
                range_parts = base.split("-")
                try:
                    start = int(range_parts[0])
                    end = int(range_parts[1])
                    return start <= value <= end and (value - start) % step == 0
                except ValueError:
                    return False
            try:
                base_val = int(base)
                return value >= base_val and (value - base_val) % step == 0
            except ValueError:
                return False
        if "-" in field:
            range_parts = field.split("-")
            if len(range_parts) != 2:
                return False
            try:
                start = int(range_parts[0])
                end = int(range_parts[1])
                return start <= value <= end
            except ValueError:
                return False
        try:
            return int(field) == value
        except ValueError:
            return False

    candidate = from_time + timedelta(minutes=1)
    candidate = candidate.replace(second=0, microsecond=0)

    for _ in range(365 * 24 * 60):
        if (_field_matches(minute, candidate.minute) and
                _field_matches(hour, candidate.hour) and
                _field_matches(dom, candidate.day) and
                _field_matches(month, candidate.month) and
                _field_matches(dow, candidate.weekday())):
            return candidate
        candidate += timedelta(minutes=1)

    return from_time + timedelta(days=1)


class LineageBuildTimelineEngine:
    """搭建时间线引擎（调度管理 + 运行记录 + 甘特图）."""

    _instance: LineageBuildTimelineEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._schedules: dict[str, BuildSchedule] = {}
        self._runs: dict[str, BuildRun] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> LineageBuildTimelineEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── Schedule CRUD ──

    def register_schedule(self, schedule: BuildSchedule) -> BuildSchedule:
        if not schedule.name or not schedule.name.strip():
            raise LineageBuildTimelineError("MISSING_NAME", "schedule name is required")
        if not schedule.pipeline_id or not schedule.pipeline_id.strip():
            raise LineageBuildTimelineError("MISSING_PIPELINE", "pipeline_id is required")
        if not _validate_cron(schedule.cron_expression):
            raise LineageBuildTimelineError("INVALID_CRON", "invalid cron expression")
        if not schedule.timezone or not schedule.timezone.strip():
            raise LineageBuildTimelineError("INVALID_TIMEZONE", "timezone is required")
        if schedule.status not in _VALID_SCHEDULE_STATUSES:
            raise LineageBuildTimelineError("INVALID_STATUS",
                                            f"status must be one of {_VALID_SCHEDULE_STATUSES}")

        now = _utcnow()
        sid = f"bs-{uuid.uuid4().hex[:8]}"
        next_run = None
        if schedule.status == "active":
            next_run = _compute_next_run_time(schedule.cron_expression, now)

        s = schedule.model_copy(update={
            "schedule_id": sid,
            "created_at": now,
            "updated_at": now,
            "next_run_at": next_run,
        })
        with self._lock:
            if len(self._schedules) >= _MAX_SCHEDULES:
                oldest = min(self._schedules.values(), key=lambda x: x.created_at)
                del self._schedules[oldest.schedule_id]
            self._schedules[sid] = s
        return s

    def get_schedule(self, schedule_id: str) -> BuildSchedule:
        with self._lock:
            s = self._schedules.get(schedule_id)
        if s is None:
            raise LineageBuildTimelineError("NOT_FOUND", f"schedule {schedule_id} not found")
        return s

    def list_schedules(self, pipeline_id: str | None = None,
                       status: str | None = None) -> list[BuildSchedule]:
        with self._lock:
            results = list(self._schedules.values())
        if pipeline_id:
            results = [s for s in results if s.pipeline_id == pipeline_id]
        if status:
            results = [s for s in results if s.status == status]
        return sorted(results, key=lambda s: s.created_at, reverse=True)

    def update_schedule(self, schedule_id: str, updates: dict) -> BuildSchedule:
        with self._lock:
            s = self._schedules.get(schedule_id)
            if s is None:
                raise LineageBuildTimelineError("NOT_FOUND", f"schedule {schedule_id} not found")
            if "status" in updates and updates["status"] not in _VALID_SCHEDULE_STATUSES:
                raise LineageBuildTimelineError("INVALID_STATUS",
                                                f"status must be one of {_VALID_SCHEDULE_STATUSES}")
            if "cron_expression" in updates and not _validate_cron(updates["cron_expression"]):
                raise LineageBuildTimelineError("INVALID_CRON", "invalid cron expression")
            if "timezone" in updates and (not updates["timezone"] or not updates["timezone"].strip()):
                raise LineageBuildTimelineError("INVALID_TIMEZONE", "timezone is required")
            data = s.model_dump()
            data.update(updates)
            now = _utcnow()
            new_status = data.get("status", s.status)
            new_cron = data.get("cron_expression", s.cron_expression)
            next_run = None
            if new_status == "active":
                next_run = _compute_next_run_time(new_cron, now)
            updated = BuildSchedule(**{**data, "updated_at": now, "next_run_at": next_run})
            self._schedules[schedule_id] = updated
        return updated

    def delete_schedule(self, schedule_id: str) -> bool:
        with self._lock:
            if schedule_id in self._schedules:
                del self._schedules[schedule_id]
                runs_to_delete = [rid for rid, r in self._runs.items()
                                  if r.schedule_id == schedule_id]
                for rid in runs_to_delete:
                    del self._runs[rid]
                return True
        return False

    # ── Cron 计算 ──

    def compute_next_run(self, schedule_id: str) -> datetime:
        schedule = self.get_schedule(schedule_id)
        now = _utcnow()
        next_run = _compute_next_run_time(schedule.cron_expression, now)
        self.update_schedule(schedule_id, {"next_run_at": next_run})
        return next_run

    # ── Run 管理 ──

    def trigger_run(self, schedule_id: str) -> BuildRun:
        schedule = self.get_schedule(schedule_id)
        if schedule.status == "paused":
            raise LineageBuildTimelineError("SCHEDULE_PAUSED",
                                            f"schedule {schedule_id} is paused")
        if schedule.status == "disabled":
            raise LineageBuildTimelineError("SCHEDULE_PAUSED",
                                            f"schedule {schedule_id} is disabled")

        now = _utcnow()
        run_id = f"br-{uuid.uuid4().hex[:8]}"
        run = BuildRun(
            run_id=run_id,
            schedule_id=schedule_id,
            status="running",
            started_at=now,
        )
        with self._lock:
            if len(self._runs) >= _MAX_RUNS:
                oldest = min(self._runs.values(), key=lambda x: x.started_at)
                del self._runs[oldest.run_id]
            self._runs[run_id] = run

            s = self._schedules.get(schedule_id)
            if s:
                updated = s.model_copy(update={
                    "last_run_at": now,
                    "next_run_at": _compute_next_run_time(s.cron_expression, now),
                    "updated_at": now,
                })
                self._schedules[schedule_id] = updated
        return run

    def complete_run(self, run_id: str, success: bool,
                     datasets_built: list[str] | None = None,
                     error_message: str = "") -> BuildRun:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise LineageBuildTimelineError("RUN_NOT_FOUND", f"run {run_id} not found")
            if run.status != "running":
                raise LineageBuildTimelineError("RUN_NOT_RUNNING",
                                                f"run {run_id} is not in running state")
            now = _utcnow()
            duration_ms = int((now - run.started_at).total_seconds() * 1000)
            new_status = "success" if success else "failed"
            updated = run.model_copy(update={
                "status": new_status,
                "finished_at": now,
                "datasets_built": datasets_built if datasets_built is not None else [],
                "duration_ms": duration_ms,
                "error_message": error_message,
            })
            self._runs[run_id] = updated
        return updated

    def get_run(self, run_id: str) -> BuildRun:
        with self._lock:
            run = self._runs.get(run_id)
        if run is None:
            raise LineageBuildTimelineError("RUN_NOT_FOUND", f"run {run_id} not found")
        return run

    def list_runs(self, schedule_id: str, limit: int = 50) -> list[BuildRun]:
        with self._lock:
            results = [r for r in self._runs.values() if r.schedule_id == schedule_id]
        results = sorted(results, key=lambda r: r.started_at, reverse=True)
        return results[:limit]

    # ── 暂停/恢复 ──

    def pause_schedule(self, schedule_id: str) -> BuildSchedule:
        return self.update_schedule(schedule_id, {"status": "paused"})

    def resume_schedule(self, schedule_id: str) -> BuildSchedule:
        return self.update_schedule(schedule_id, {"status": "active"})

    # ── 甘特图 ──

    def get_gantt_chart(self, start_date: date, end_date: date,
                        pipeline_id: str | None = None) -> GanttChart:
        schedules = self.list_schedules(pipeline_id=pipeline_id)
        tasks: list[GanttTask] = []

        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        for s in schedules:
            if s.status == "disabled":
                continue

            current = start_dt
            for _ in range(100):
                next_run = _compute_next_run_time(s.cron_expression, current)
                if next_run > end_dt:
                    break
                task_id = f"gt-{s.schedule_id}-{next_run.strftime('%Y%m%d%H%M')}"
                end_time = next_run + timedelta(minutes=30)
                status = "scheduled"
                if next_run < _utcnow():
                    status = "success"

                tasks.append(GanttTask(
                    task_id=task_id,
                    name=s.name,
                    pipeline_id=s.pipeline_id,
                    start_time=next_run,
                    end_time=end_time,
                    status=status,
                ))
                current = next_run + timedelta(minutes=1)

        chart_id = f"gc-{uuid.uuid4().hex[:8]}"
        return GanttChart(
            chart_id=chart_id,
            title=f"Build Timeline {start_date.isoformat()} ~ {end_date.isoformat()}",
            start_date=start_date,
            end_date=end_date,
            tasks=sorted(tasks, key=lambda t: t.start_time),
        )


_lineage_build_timeline_engine: LineageBuildTimelineEngine | None = None
_lineage_build_timeline_engine_lock = threading.Lock()


def get_lineage_build_timeline_engine() -> LineageBuildTimelineEngine:
    global _lineage_build_timeline_engine
    if _lineage_build_timeline_engine is None:
        with _lineage_build_timeline_engine_lock:
            if _lineage_build_timeline_engine is None:
                _lineage_build_timeline_engine = LineageBuildTimelineEngine.get_instance()
    return _lineage_build_timeline_engine
