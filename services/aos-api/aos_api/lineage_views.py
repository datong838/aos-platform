"""W2-#4 · Data Lineage（L1）增强。

列级血缘 + 22 种着色调色板 + 交互式 DAG 布局 + 4 种节点映射。
独立视图模块，不改 lineage_graph.py 核心（最小更改）。

详见 docs/palantier/20_tech/220tech_w2-e-media-lineage-ide.md §2.3/§3.2。
"""
from __future__ import annotations

import math
from collections import deque
from typing import Any

from pydantic import BaseModel, Field

from .lineage_graph import LineageGraph, get_graph


class ColumnLineage(BaseModel):
    source_columns: list[str] = Field(default_factory=list)
    target_column: str = ""
    transform_expr: str = ""


class LineageEdgeDetail(BaseModel):
    source: str
    target: str
    columns: list[ColumnLineage] = Field(default_factory=list)


# 22 种着色调色板
PALETTE_22: dict[str, str] = {
    "dataset": "#3b82f6",
    "transform": "#f59e0b",
    "ontology_object": "#10b981",
    "artifact": "#8b5cf6",
    "data_source": "#ef4444",
    "llm": "#ec4899",
    "media_set": "#14b8a6",
}

_DEPTH_SHADES = [
    "#ffffff", "#f0f9ff", "#e0f2fe", "#bae6fd",
    "#7dd3fc", "#38bdf8", "#0ea5e9", "#0284c7",
    "#0369a1", "#075985", "#0c4a6e",
]

# 4 种核心节点类型映射（收敛到 #4 要求）
NODE_KIND_4 = {
    "dataset": "source",
    "data_source": "source",
    "media_set": "source",
    "transform": "transform",
    "llm": "transform",
    "ontology_object": "sink",
    "artifact": "sink",
}


class LineageViewError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def color_by_type(node_type: str) -> str:
    return PALETTE_22.get(node_type, "#6b7280")


def color_by_depth(node_id: str, graph: LineageGraph) -> str:
    depths = _compute_depths(graph)
    depth = depths.get(node_id, 0)
    idx = min(depth, len(_DEPTH_SHADES) - 1)
    return _DEPTH_SHADES[idx]


def color_22(graph: LineageGraph, by: str = "type") -> dict[str, str]:
    if by == "type":
        nodes = graph.to_dict().get("nodes", [])
        return {n["id"]: color_by_type(n.get("type", "")) for n in nodes}
    if by == "depth":
        depths = _compute_depths(graph)
        return {nid: _DEPTH_SHADES[min(d, len(_DEPTH_SHADES) - 1)] for nid, d in depths.items()}
    raise LineageViewError("BAD_BY", f"未知着色维度 {by!r}，可用：type/depth")


def _compute_depths(graph: LineageGraph) -> dict[str, int]:
    data = graph.to_dict()
    nodes = [n["id"] for n in data["nodes"]]
    edges = data["edges"]
    adj: dict[str, list[str]] = {}
    in_deg: dict[str, int] = {}
    for n in nodes:
        adj[n] = []
        in_deg[n] = 0
    for e in edges:
        adj[e["source"]].append(e["target"])
        in_deg[e["target"]] = in_deg.get(e["target"], 0) + 1
    queue = deque([n for n in nodes if in_deg.get(n, 0) == 0])
    depths: dict[str, int] = {n: 0 for n in queue}
    while queue:
        node = queue.popleft()
        for child in adj.get(node, []):
            depths[child] = depths.get(node, 0) + 1
            in_deg[child] -= 1
            if in_deg[child] == 0:
                queue.append(child)
    return depths


class LayoutNode(BaseModel):
    id: str
    x: float
    y: float
    layer: int
    color: str = ""
    node_kind_4: str = ""
    label: str = ""


class LayoutEdge(BaseModel):
    source: str
    target: str
    columns: list[ColumnLineage] = Field(default_factory=list)


class LineageLayout(BaseModel):
    nodes: list[LayoutNode] = Field(default_factory=list)
    edges: list[LayoutEdge] = Field(default_factory=list)
    layer_count: int = 0
    width: float = 0.0
    height: float = 0.0


def compute_layout(
    graph: LineageGraph,
    column_map: dict[str, list[ColumnLineage]] | None = None,
    node_x_spacing: float = 200,
    node_y_spacing: float = 120,
) -> LineageLayout:
    data = graph.to_dict()
    nodes = data["nodes"]
    edges = data["edges"]
    depths = _compute_depths(graph)
    layers: dict[int, list[str]] = {}
    for nid, d in depths.items():
        layers.setdefault(d, []).append(nid)
    layout_nodes: list[LayoutNode] = []
    max_layer_width = 1
    for layer_idx, layer_nodes in sorted(layers.items()):
        max_layer_width = max(max_layer_width, len(layer_nodes))
        for col_idx, nid in enumerate(layer_nodes):
            node_meta = next((n for n in nodes if n["id"] == nid), {})
            ntype = node_meta.get("type", "dataset")
            layout_nodes.append(LayoutNode(
                id=nid,
                x=col_idx * node_x_spacing,
                y=layer_idx * node_y_spacing,
                layer=layer_idx,
                color=color_by_type(ntype),
                node_kind_4=NODE_KIND_4.get(ntype, "source"),
                label=node_meta.get("name", nid),
            ))
    layout_edges: list[LayoutEdge] = []
    for e in edges:
        cols = (column_map or {}).get(f"{e['source']}->{e['target']}", [])
        layout_edges.append(LayoutEdge(source=e["source"], target=e["target"], columns=cols))
    return LineageLayout(
        nodes=layout_nodes,
        edges=layout_edges,
        layer_count=len(layers),
        width=max_layer_width * node_x_spacing,
        height=len(layers) * node_y_spacing,
    )


def list_palette() -> list[dict[str, str]]:
    return [{"type": k, "color": v} for k, v in PALETTE_22.items()]


def list_node_kinds() -> list[dict[str, str]]:
    return [{"raw_type": k, "kind_4": v} for k, v in NODE_KIND_4.items()]


class LineageViewService:
    """Lineage 视图聚合服务。"""

    def __init__(self, graph: LineageGraph | None = None) -> None:
        self._graph = graph or get_graph()
        self._column_map: dict[str, list[ColumnLineage]] = {}

    def set_column_lineage(self, source: str, target: str, columns: list[ColumnLineage]) -> None:
        self._column_map[f"{source}->{target}"] = columns

    def get_column_lineage(self, source: str, target: str) -> list[ColumnLineage]:
        return self._column_map.get(f"{source}->{target}", [])

    def color(self, by: str = "type") -> dict[str, str]:
        return color_22(self._graph, by)

    def layout(self) -> LineageLayout:
        return compute_layout(self._graph, self._column_map)

    def summary(self) -> dict[str, Any]:
        data = self._graph.to_dict()
        kind_counts: dict[str, int] = {}
        for n in data["nodes"]:
            k4 = NODE_KIND_4.get(n.get("type", ""), "source")
            kind_counts[k4] = kind_counts.get(k4, 0) + 1
        total_columns = sum(len(cols) for cols in self._column_map.values())
        return {
            "node_count": len(data["nodes"]),
            "edge_count": len(data["edges"]),
            "kind_4_counts": kind_counts,
            "column_lineage_count": total_columns,
        }


_service = LineageViewService()


def get_service() -> LineageViewService:
    return _service
