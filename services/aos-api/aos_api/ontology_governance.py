"""W2-I · Ontology 治理引擎：Usage Metrics + Graph Query."""
from __future__ import annotations

import threading
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ─────────────── #38 Usage Metrics ───────────────

class UsageMetric(BaseModel):
    reads: int = 0
    writes: int = 0
    interactions: int = 0
    active_users: int = 0
    sources: dict[str, int] = Field(default_factory=dict)
    daily_series: list[dict[str, Any]] = Field(default_factory=list)
    window_days: int = 30


class UsageMetricsEngine:
    """内存滑动窗口使用指标（30 天）· #38."""

    def __init__(self, window_days: int = 30) -> None:
        self._lock = threading.Lock()
        self._window_days = window_days

        # 全局每日计数器: date_str -> {reads, writes, interactions, users: set, sources: {}}
        self._global_daily: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"reads": 0, "writes": 0, "interactions": 0, "users": set(), "sources": defaultdict(int)}
        )
        # 按 Object Type: otype -> date_str -> {同上}
        self._otype_daily: dict[str, dict[str, dict[str, Any]]] = defaultdict(
            lambda: defaultdict(
                lambda: {"reads": 0, "writes": 0, "interactions": 0, "users": set(), "sources": defaultdict(int)}
            )
        )
        # 按 Link Type
        self._ltype_daily: dict[str, dict[str, dict[str, Any]]] = defaultdict(
            lambda: defaultdict(
                lambda: {"reads": 0, "writes": 0, "interactions": 0, "users": set(), "sources": defaultdict(int)}
            )
        )

    def _prune(self, bucket: dict[str, dict[str, Any]]) -> None:
        today = date.today()
        cutoff = (today - timedelta(days=self._window_days)).strftime("%Y-%m-%d")
        stale = [d for d in bucket if d < cutoff]
        for d in stale:
            del bucket[d]

    def record(
        self,
        event_type: str,
        *,
        user_id: str | None = None,
        source: str = "api",
        object_type: str | None = None,
        link_type: str | None = None,
        day: str | None = None,
    ) -> None:
        """记录一个使用事件。event_type: read/write/interaction."""
        day = day or _utc_today()
        with self._lock:
            self._prune(self._global_daily)
            g = self._global_daily[day]
            g[event_type + "s"] += 1
            if user_id:
                g["users"].add(user_id)
            g["sources"][source] += 1

            if object_type:
                self._prune(self._otype_daily[object_type])
                o = self._otype_daily[object_type][day]
                o[event_type + "s"] += 1
                if user_id:
                    o["users"].add(user_id)
                o["sources"][source] += 1

            if link_type:
                self._prune(self._ltype_daily[link_type])
                l = self._ltype_daily[link_type][day]
                l[event_type + "s"] += 1
                if user_id:
                    l["users"].add(user_id)
                l["sources"][source] += 1

    def _aggregate(self, bucket: dict[str, dict[str, Any]]) -> UsageMetric:
        today = date.today()
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(self._window_days - 1, -1, -1)]
        series: list[dict[str, Any]] = []
        total_reads = 0
        total_writes = 0
        total_interactions = 0
        all_users: set[str] = set()
        all_sources: dict[str, int] = defaultdict(int)

        for d in dates:
            entry = bucket.get(d)
            if entry:
                series.append({
                    "date": d,
                    "reads": entry["reads"],
                    "writes": entry["writes"],
                    "interactions": entry["interactions"],
                    "activeUsers": len(entry["users"]),
                })
                total_reads += entry["reads"]
                total_writes += entry["writes"]
                total_interactions += entry["interactions"]
                all_users.update(entry["users"])
                for s, c in entry["sources"].items():
                    all_sources[s] += c
            else:
                series.append({
                    "date": d,
                    "reads": 0,
                    "writes": 0,
                    "interactions": 0,
                    "activeUsers": 0,
                })

        return UsageMetric(
            reads=total_reads,
            writes=total_writes,
            interactions=total_interactions,
            active_users=len(all_users),
            sources=dict(all_sources),
            daily_series=series,
            window_days=self._window_days,
        )

    def get_global(self) -> UsageMetric:
        with self._lock:
            self._prune(self._global_daily)
            return self._aggregate(self._global_daily)

    def get_object_type(self, object_type: str) -> UsageMetric:
        with self._lock:
            if object_type in self._otype_daily:
                self._prune(self._otype_daily[object_type])
                return self._aggregate(self._otype_daily[object_type])
            return UsageMetric(window_days=self._window_days)

    def get_link_type(self, link_type: str) -> UsageMetric:
        with self._lock:
            if link_type in self._ltype_daily:
                self._prune(self._ltype_daily[link_type])
                return self._aggregate(self._ltype_daily[link_type])
            return UsageMetric(window_days=self._window_days)

    def reset(self) -> None:
        with self._lock:
            self._global_daily.clear()
            self._otype_daily.clear()
            self._ltype_daily.clear()


# ─────────────── #69 Graph Query ───────────────

class GraphNode(BaseModel):
    type: str
    id: str
    depth: int = 0


class GraphEdge(BaseModel):
    rel: str
    src_type: str
    src_id: str
    dst_type: str
    dst_id: str
    depth: int = 0


class PathStep(BaseModel):
    type: str
    id: str
    rel: str | None = None


class GraphQueryEngine:
    """内存图查询引擎：多跳 BFS + 最短路径 · #69.

    使用邻接表存储，支持从外部批量导入边（测试用）。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # 出边: (src_type, src_id) -> [(rel, dst_type, dst_id)]
        self._out_edges: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
        # 入边: (dst_type, dst_id) -> [(rel, src_type, src_id)]
        self._in_edges: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
        # 所有关系类型集合（用于验证）
        self._all_rels: set[str] = set()

    def add_edge(self, rel: str, src_type: str, src_id: str, dst_type: str, dst_id: str) -> None:
        with self._lock:
            key_out = (src_type, src_id)
            if (rel, dst_type, dst_id) not in self._out_edges[key_out]:
                self._out_edges[key_out].append((rel, dst_type, dst_id))
            key_in = (dst_type, dst_id)
            if (rel, src_type, src_id) not in self._in_edges[key_in]:
                self._in_edges[key_in].append((rel, src_type, src_id))
            self._all_rels.add(rel)

    def add_edges_batch(self, edges: list[tuple[str, str, str, str, str]]) -> None:
        """edges: list of (rel, src_type, src_id, dst_type, dst_id)."""
        for rel, st, si, dt, di in edges:
            self.add_edge(rel, st, si, dt, di)

    def multi_hop(
        self,
        src_type: str,
        src_id: str,
        hops: int,
        *,
        rel: str | None = None,
        direction: str = "out",
        max_nodes: int = 500,
    ) -> dict[str, Any]:
        """BFS 多跳邻居查询。direction: out / in / both."""
        if hops < 1 or hops > 5:
            raise ValueError("hops must be between 1 and 5")

        nodes: dict[tuple[str, str], int] = {}  # (type, id) -> depth
        edges_list: list[GraphEdge] = []
        visited: set[tuple[str, str]] = set()
        queue: deque[tuple[str, str, int]] = deque()

        start = (src_type, src_id)
        visited.add(start)
        nodes[start] = 0
        queue.append((src_type, src_id, 0))

        with self._lock:
            while queue:
                ctype, cid, depth = queue.popleft()
                if depth >= hops or len(nodes) >= max_nodes:
                    continue

                neighbors: list[tuple[str, str, str, str]] = []  # (rel, ntype, nid, direction)

                if direction in ("out", "both"):
                    for r, nt, ni in self._out_edges.get((ctype, cid), []):
                        if rel and r != rel:
                            continue
                        neighbors.append((r, nt, ni, "out"))

                if direction in ("in", "both"):
                    for r, st, si in self._in_edges.get((ctype, cid), []):
                        if rel and r != rel:
                            continue
                        neighbors.append((r, st, si, "in"))

                for r, ntype, nid, _dir in neighbors:
                    nkey = (ntype, nid)
                    if nkey not in visited:
                        visited.add(nkey)
                        nodes[nkey] = depth + 1
                        if _dir == "out":
                            edges_list.append(GraphEdge(
                                rel=r, src_type=ctype, src_id=cid,
                                dst_type=ntype, dst_id=nid, depth=depth + 1,
                            ))
                        else:
                            edges_list.append(GraphEdge(
                                rel=r, src_type=ntype, src_id=nid,
                                dst_type=ctype, dst_id=cid, depth=depth + 1,
                            ))
                        if len(nodes) < max_nodes:
                            queue.append((ntype, nid, depth + 1))

        node_list = [GraphNode(type=t, id=i, depth=d) for (t, i), d in nodes.items() if d > 0]
        return {
            "srcType": src_type,
            "srcId": src_id,
            "hops": hops,
            "direction": direction,
            "totalNodes": len(node_list),
            "totalEdges": len(edges_list),
            "nodes": [n.model_dump() for n in node_list],
            "edges": [e.model_dump() for e in edges_list],
        }

    def shortest_path(
        self,
        src_type: str,
        src_id: str,
        dst_type: str,
        dst_id: str,
        *,
        max_hops: int = 6,
        rels: list[str] | None = None,
        undirected: bool = True,
    ) -> dict[str, Any]:
        """双向 BFS 最短路径查询。默认无向遍历（边可双向走）。"""
        if max_hops < 1 or max_hops > 8:
            raise ValueError("max_hops must be between 1 and 8")

        start = (src_type, src_id)
        goal = (dst_type, dst_id)
        if start == goal:
            return {
                "found": True,
                "distance": 0,
                "path": [PathStep(type=src_type, id=src_id).model_dump()],
                "explored": 1,
            }

        fwd_visited: dict[tuple[str, str], tuple[str, str, str] | None] = {start: None}
        fwd_queue: deque[tuple[str, str, int]] = deque([(src_type, src_id, 0)])
        bwd_visited: dict[tuple[str, str], tuple[str, str, str] | None] = {goal: None}
        bwd_queue: deque[tuple[str, str, int]] = deque([(dst_type, dst_id, 0)])

        explored = 0
        meeting_node: tuple[str, str] | None = None

        with self._lock:
            while fwd_queue and bwd_queue:
                if len(fwd_queue) <= len(bwd_queue):
                    meeting_node = self._bfs_step(
                        fwd_queue, fwd_visited, bwd_visited,
                        direction="forward", max_hops=max_hops,
                        rels=rels, undirected=undirected,
                    )
                else:
                    meeting_node = self._bfs_step(
                        bwd_queue, bwd_visited, fwd_visited,
                        direction="backward", max_hops=max_hops,
                        rels=rels, undirected=undirected,
                    )
                explored = len(fwd_visited) + len(bwd_visited)
                if meeting_node:
                    break
                if explored > 2000:
                    break

        if not meeting_node:
            return {"found": False, "distance": -1, "path": [], "explored": explored}

        fwd_path = self._rebuild_path(fwd_visited, start, meeting_node, forward=True)
        bwd_path = self._rebuild_path(bwd_visited, goal, meeting_node, forward=False)

        full = fwd_path + bwd_path[1:]

        return {
            "found": True,
            "distance": len(full) - 1,
            "path": [p.model_dump() for p in full],
            "explored": explored,
        }

    def _bfs_step(
        self,
        queue: deque[tuple[str, str, int]],
        this_visited: dict[tuple[str, str], tuple[str, str, str] | None],
        other_visited: dict[tuple[str, str], tuple[str, str, str] | None],
        *,
        direction: str,
        max_hops: int,
        rels: list[str] | None,
        undirected: bool = False,
    ) -> tuple[str, str] | None:
        """扩展一层。返回相遇节点，若无返回 None。"""
        if not queue:
            return None
        level_size = len(queue)
        for _ in range(level_size):
            ctype, cid, depth = queue.popleft()
            if depth >= max_hops:
                continue

            neighbors: list[tuple[str, str, str]] = []
            if undirected:
                for r, nt, ni in self._out_edges.get((ctype, cid), []):
                    if rels and r not in rels:
                        continue
                    neighbors.append((r, nt, ni))
                for r, st, si in self._in_edges.get((ctype, cid), []):
                    if rels and r not in rels:
                        continue
                    neighbors.append((r, st, si))
            elif direction == "forward":
                for r, nt, ni in self._out_edges.get((ctype, cid), []):
                    if rels and r not in rels:
                        continue
                    neighbors.append((r, nt, ni))
            else:
                for r, st, si in self._in_edges.get((ctype, cid), []):
                    if rels and r not in rels:
                        continue
                    neighbors.append((r, st, si))

            for r, ntype, nid in neighbors:
                nkey = (ntype, nid)
                if nkey in other_visited:
                    this_visited[nkey] = (r, ctype, cid)
                    return nkey
                if nkey not in this_visited:
                    this_visited[nkey] = (r, ctype, cid)
                    queue.append((ntype, nid, depth + 1))
        return None

    def _rebuild_path(
        self,
        visited: dict[tuple[str, str], tuple[str, str, str] | None],
        endpoint: tuple[str, str],
        meeting: tuple[str, str],
        *,
        forward: bool,
    ) -> list[PathStep]:
        """从 meeting 反向追溯到 endpoint，然后反转。"""
        path: list[PathStep] = []
        current = meeting
        while current is not None:
            prev_info = visited.get(current)
            if prev_info is None:
                # 起点
                path.append(PathStep(type=current[0], id=current[1]))
                break
            rel, ptype, pid = prev_info
            path.append(PathStep(type=current[0], id=current[1], rel=rel))
            current = (ptype, pid)

        if forward:
            path.reverse()
        return path

    def expand(
        self,
        seeds: list[tuple[str, str]],
        hops: int,
        *,
        max_nodes: int = 500,
        rels: list[str] | None = None,
    ) -> dict[str, Any]:
        """子图扩展：从多个种子节点向外展开 N 跳。"""
        if hops < 1 or hops > 5:
            raise ValueError("hops must be between 1 and 5")

        nodes: dict[tuple[str, str], int] = {}
        edges_list: list[GraphEdge] = []
        queue: deque[tuple[str, str, int]] = deque()

        for st, si in seeds:
            key = (st, si)
            if key not in nodes:
                nodes[key] = 0
                queue.append((st, si, 0))

        with self._lock:
            while queue and len(nodes) < max_nodes:
                ctype, cid, depth = queue.popleft()
                if depth >= hops:
                    continue

                for r, ntype, ni in self._out_edges.get((ctype, cid), []):
                    if rels and r not in rels:
                        continue
                    nkey = (ntype, ni)
                    if nkey not in nodes:
                        nodes[nkey] = depth + 1
                        edges_list.append(GraphEdge(
                            rel=r, src_type=ctype, src_id=cid,
                            dst_type=ntype, dst_id=ni, depth=depth + 1,
                        ))
                        if len(nodes) < max_nodes:
                            queue.append((ntype, ni, depth + 1))

        node_list = [GraphNode(type=t, id=i, depth=d) for (t, i), d in nodes.items()]
        return {
            "seedCount": len(seeds),
            "hops": hops,
            "totalNodes": len(node_list),
            "totalEdges": len(edges_list),
            "nodes": [n.model_dump() for n in node_list],
            "edges": [e.model_dump() for e in edges_list],
        }

    def reset(self) -> None:
        with self._lock:
            self._out_edges.clear()
            self._in_edges.clear()
            self._all_rels.clear()


# ─────────────── 单例 ───────────────

_usage_engine: UsageMetricsEngine | None = None
_graph_engine: GraphQueryEngine | None = None
_singleton_lock = threading.Lock()


def get_usage_engine() -> UsageMetricsEngine:
    global _usage_engine
    if _usage_engine is None:
        with _singleton_lock:
            if _usage_engine is None:
                _usage_engine = UsageMetricsEngine()
    return _usage_engine


def get_graph_engine() -> GraphQueryEngine:
    global _graph_engine
    if _graph_engine is None:
        with _singleton_lock:
            if _graph_engine is None:
                _graph_engine = GraphQueryEngine()
    return _graph_engine
