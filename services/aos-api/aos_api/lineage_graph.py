"""W1-13 · Data Lineage DAG 引擎。

数据沿袭有向无环图：节点（dataset/transform/ontology_object/artifact/data_source）
+ 有向边 + 上游/下游查询 + 拓扑排序 + 节点着色 + 环检测。

详见 docs/palantier/20_tech/220tech_lineage-graph.md。
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from pydantic import BaseModel, Field


NODE_TYPES = {"dataset", "transform", "ontology_object", "artifact", "data_source"}


class LineageNode(BaseModel):
    id: str
    type: str
    name: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class LineageEdge(BaseModel):
    source: str
    target: str


class LineageError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class LineageGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, LineageNode] = {}
        self._adj: dict[str, list[str]] = defaultdict(list)       # downstream
        self._radj: dict[str, list[str]] = defaultdict(list)      # upstream

    def add_node(self, node: LineageNode) -> LineageNode:
        if node.type not in NODE_TYPES:
            raise LineageError("INVALID_NODE_TYPE", f"未知节点类型 {node.type!r}，可用：{NODE_TYPES}")
        self._nodes[node.id] = node
        return node

    def add_edge(self, source: str, target: str) -> None:
        self._require_node(source)
        self._require_node(target)
        if source == target:
            raise LineageError("SELF_LOOP", "不允许自环")
        edge = (source, target)
        if edge not in [(s, t) for s, t in zip(self._adj[source], [target] * len(self._adj[source]))]:
            self._adj[source].append(target)
            self._radj[target].append(source)

    def _require_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise LineageError("NOT_FOUND", f"节点 {node_id} 不存在")

    def get_node(self, node_id: str) -> LineageNode | None:
        return self._nodes.get(node_id)

    def get_upstream(self, node_id: str, depth: int = -1) -> list[str]:
        self._require_node(node_id)
        return self._bfs(node_id, self._radj, depth)

    def get_downstream(self, node_id: str, depth: int = -1) -> list[str]:
        self._require_node(node_id)
        return self._bfs(node_id, self._adj, depth)

    def _bfs(self, start: str, adj: dict[str, list[str]], depth: int) -> list[str]:
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        result: list[str] = []
        while queue:
            node, d = queue.popleft()
            if node in visited:
                continue
            if node != start:
                visited.add(node)
                result.append(node)
            if depth < 0 or d < depth:
                for nxt in adj.get(node, []):
                    if nxt not in visited:
                        queue.append((nxt, d + 1))
        return result

    def topological_sort(self) -> list[str]:
        in_degree: dict[str, int] = {nid: 0 for nid in self._nodes}
        for source, targets in self._adj.items():
            for t in targets:
                in_degree[t] = in_degree.get(t, 0) + 1
        queue: deque[str] = deque([n for n, d in in_degree.items() if d == 0])
        result: list[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for nxt in self._adj.get(node, []):
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)
        if len(result) != len(self._nodes):
            raise LineageError("CYCLE_DETECTED", "图中存在环，无法拓扑排序")
        return result

    def has_cycle(self) -> bool:
        try:
            self.topological_sort()
            return False
        except LineageError:
            return True

    def color_nodes(self, by: str = "type") -> dict[str, str]:
        color_map: dict[str, str] = {}
        for nid, node in self._nodes.items():
            if by == "type":
                color_map[nid] = node.type
            elif by == "name":
                color_map[nid] = node.name
            else:
                color_map[nid] = str(node.metadata.get(by, "unknown"))
        return color_map

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.model_dump() for n in self._nodes.values()],
            "edges": [{"source": s, "target": t} for s in self._adj for t in self._adj[s]],
        }

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(v) for v in self._adj.values())


_graph = LineageGraph()


def get_graph() -> LineageGraph:
    return _graph
