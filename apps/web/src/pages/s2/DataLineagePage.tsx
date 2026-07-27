import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  BpBanner,
  BpMetricGrid,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./blueprintUi";
import { S2Chrome, useJsonGet } from "./shared";

// ── Types ──────────────────────────────────────────────────────

export type NodeType = "source" | "dataset" | "pipeline" | "object_type" | "funnel";

export type NodeStatus = "healthy" | "stale" | "error" | "unknown";

export type LineageNode = {
  id: string;
  name: string;
  type: NodeType;
  status: NodeStatus;
  level: number; // depth in the graph
  x: number;
  y: number;
  meta?: {
    rowCount?: number;
    lastUpdated?: string;
    description?: string;
  };
};

export type LineageEdge = {
  id: string;
  source: string;
  target: string;
  label?: string;
};

export type LineageGraph = {
  nodes: LineageNode[];
  edges: LineageEdge[];
};

// ── Pure functions ─────────────────────────────────────────────

export const NODE_TYPE_LABEL: Record<NodeType, string> = {
  source: "数据源",
  dataset: "数据集",
  pipeline: "管道",
  object_type: "Object Type",
  funnel: "Funnel",
};

export const NODE_TYPE_TONE: Record<NodeType, "ok" | "warn" | "bad" | "muted"> = {
  source: "ok",
  dataset: "warn",
  pipeline: "ok",
  object_type: "muted",
  funnel: "bad",
};

export const NODE_STATUS_LABEL: Record<NodeStatus, string> = {
  healthy: "健康",
  stale: "过期",
  error: "错误",
  unknown: "未知",
};

export const NODE_STATUS_TONE: Record<NodeStatus, "ok" | "warn" | "bad" | "muted"> = {
  healthy: "ok",
  stale: "warn",
  error: "bad",
  unknown: "muted",
};

export function formatTimestamp(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

export function filterNodes(
  nodes: LineageNode[],
  typeFilter: NodeType | "all",
  query: string,
): LineageNode[] {
  const q = query.trim().toLowerCase();
  return nodes.filter((n) => {
    if (typeFilter !== "all" && n.type !== typeFilter) return false;
    if (!q) return true;
    return n.name.toLowerCase().includes(q) || n.id.toLowerCase().includes(q);
  });
}

export function upstreamNodes(graph: LineageGraph, nodeId: string): LineageNode[] {
  const visited = new Set<string>();
  const result: LineageNode[] = [];
  function walk(id: string) {
    for (const edge of graph.edges) {
      if (edge.target === id && !visited.has(edge.source)) {
        visited.add(edge.source);
        const node = graph.nodes.find((n) => n.id === edge.source);
        if (node) result.push(node);
        walk(edge.source);
      }
    }
  }
  walk(nodeId);
  return result;
}

export function downstreamNodes(graph: LineageGraph, nodeId: string): LineageNode[] {
  const visited = new Set<string>();
  const result: LineageNode[] = [];
  function walk(id: string) {
    for (const edge of graph.edges) {
      if (edge.source === id && !visited.has(edge.target)) {
        visited.add(edge.target);
        const node = graph.nodes.find((n) => n.id === edge.target);
        if (node) result.push(node);
        walk(edge.target);
      }
    }
  }
  walk(nodeId);
  return result;
}

export function computeImpact(
  graph: LineageGraph,
  nodeId: string,
): { upstream: number; downstream: number; affected: number } {
  const up = upstreamNodes(graph, nodeId);
  const down = downstreamNodes(graph, nodeId);
  return { upstream: up.length, downstream: down.length, affected: up.length + down.length };
}

export function filterByLevel(
  nodes: LineageNode[],
  maxLevel: number,
): LineageNode[] {
  return nodes.filter((n) => n.level <= maxLevel);
}

export function countByType(nodes: LineageNode[]): Record<NodeType, number> {
  const acc: Record<NodeType, number> = {
    source: 0,
    dataset: 0,
    pipeline: 0,
    object_type: 0,
    funnel: 0,
  };
  for (const n of nodes) acc[n.type]++;
  return acc;
}

export function countByStatus(nodes: LineageNode[]): Record<NodeStatus, number> {
  const acc: Record<NodeStatus, number> = {
    healthy: 0,
    stale: 0,
    error: 0,
    unknown: 0,
  };
  for (const n of nodes) acc[n.status]++;
  return acc;
}

export function edgePath(edge: LineageEdge, nodes: LineageNode[]): string {
  const source = nodes.find((n) => n.id === edge.source);
  const target = nodes.find((n) => n.id === edge.target);
  if (!source || !target) return "";
  const x1 = source.x + 120;
  const y1 = source.y + 24;
  const x2 = target.x;
  const y2 = target.y + 24;
  const midX = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;
}

// ── Mock data ──────────────────────────────────────────────────

const DEMO_NODES: LineageNode[] = [
  { id: "src-taobao", name: "淘宝开放平台", type: "source", status: "healthy", level: 0, x: 40, y: 40, meta: { description: "订单/商品/会员数据", lastUpdated: new Date(Date.now() - 5 * 60000).toISOString() } },
  { id: "src-jd", name: "京东开放平台", type: "source", status: "healthy", level: 0, x: 40, y: 120, meta: { description: "京东电商数据", lastUpdated: new Date(Date.now() - 10 * 60000).toISOString() } },
  { id: "ds-raw-orders", name: "raw_orders", type: "dataset", status: "healthy", level: 1, x: 280, y: 40, meta: { rowCount: 1200000, lastUpdated: new Date(Date.now() - 8 * 60000).toISOString() } },
  { id: "ds-raw-products", name: "raw_products", type: "dataset", status: "healthy", level: 1, x: 280, y: 120, meta: { rowCount: 45000, lastUpdated: new Date(Date.now() - 15 * 60000).toISOString() } },
  { id: "pl-clean", name: "clean_pipeline", type: "pipeline", status: "healthy", level: 2, x: 520, y: 80, meta: { description: "清洗 + 去重 + 格式化" } },
  { id: "ds-curated", name: "curated_orders", type: "dataset", status: "stale", level: 3, x: 760, y: 40, meta: { rowCount: 892104, lastUpdated: new Date(Date.now() - 180 * 60000).toISOString() } },
  { id: "ds-dim", name: "dim_products", type: "dataset", status: "healthy", level: 3, x: 760, y: 120, meta: { rowCount: 44890, lastUpdated: new Date(Date.now() - 30 * 60000).toISOString() } },
  { id: "ot-order", name: "OrderType", type: "object_type", status: "healthy", level: 4, x: 1000, y: 40, meta: { description: "订单本体类型" } },
  { id: "fn-sales", name: "SalesFunnel", type: "funnel", status: "error", level: 4, x: 1000, y: 120, meta: { description: "销售漏斗分析" } },
];

const DEMO_EDGES: LineageEdge[] = [
  { id: "e1", source: "src-taobao", target: "ds-raw-orders" },
  { id: "e2", source: "src-jd", target: "ds-raw-products" },
  { id: "e3", source: "src-taobao", target: "ds-raw-products" },
  { id: "e4", source: "ds-raw-orders", target: "pl-clean" },
  { id: "e5", source: "ds-raw-products", target: "pl-clean" },
  { id: "e6", source: "pl-clean", target: "ds-curated" },
  { id: "e7", source: "pl-clean", target: "ds-dim" },
  { id: "e8", source: "ds-curated", target: "ot-order" },
  { id: "e9", source: "ds-curated", target: "fn-sales" },
  { id: "e10", source: "ds-dim", target: "fn-sales" },
];

const DEMO_GRAPH: LineageGraph = {
  nodes: DEMO_NODES,
  edges: DEMO_EDGES,
};

// ── Page Component ─────────────────────────────────────────────

const MAX_LEVEL = 4;

export function DataLineagePage() {
  const { data, err, loading } = useJsonGet<LineageGraph>("/v1/data-lineage/graph");
  const graph = data ?? DEMO_GRAPH;

  const [selectedId, setSelectedId] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<NodeType | "all">("all");
  const [query, setQuery] = useState("");
  const [maxLevel, setMaxLevel] = useState(MAX_LEVEL);
  const [tab, setTab] = useState("graph");

  const filteredNodes = useMemo(
    () => filterByLevel(filterNodes(graph.nodes, typeFilter, query), maxLevel),
    [graph.nodes, typeFilter, query, maxLevel],
  );

  const selected = useMemo(
    () => graph.nodes.find((n) => n.id === selectedId) ?? null,
    [graph.nodes, selectedId],
  );

  const impact = useMemo(
    () => (selected ? computeImpact(graph, selected.id) : null),
    [graph, selected],
  );

  const statusCounts = useMemo(() => countByStatus(graph.nodes), [graph.nodes]);

  return (
    <S2Chrome title="数据沿袭" lede="可视化数据流经的路径 · 从源到消费的完整链路">
      <BpToolbar>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as NodeType | "all")}>
          <option value="all">全部类型</option>
          {Object.entries(NODE_TYPE_LABEL).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <input
          type="search"
          placeholder="搜索节点…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ minWidth: 180 }}
        />
        <label className="muted" style={{ fontSize: "0.75rem" }}>
          最大层级:&nbsp;
          <input
            type="range"
            min={0}
            max={MAX_LEVEL}
            value={maxLevel}
            onChange={(e) => setMaxLevel(Number(e.target.value))}
            style={{ width: 80 }}
          />
          &nbsp;{maxLevel}
        </label>
      </BpToolbar>

      {loading && <p className="muted">加载中…</p>}
      {err && <p className="error">{err}</p>}

      <BpMetricGrid
        items={[
          { label: "节点总数", value: graph.nodes.length, tone: "muted" },
          { label: "连线总数", value: graph.edges.length, tone: "muted" },
          { label: "健康节点", value: statusCounts.healthy, tone: "ok" },
          { label: "异常节点", value: statusCounts.error + statusCounts.stale, tone: statusCounts.error + statusCounts.stale > 0 ? "warn" : "ok" },
        ]}
      />

      <BpTabs
        tabs={[
          { id: "graph", label: "图谱" },
          { id: "list", label: "列表" },
          { id: "impact", label: "影响分析" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "graph" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: "0.75rem" }}>
          <div className="bp-object-panel" style={{ overflow: "auto", minHeight: 320 }}>
            <svg width="1140" height="200" style={{ display: "block" }}>
              {graph.edges.map((edge) => {
                const d = edgePath(edge, graph.nodes);
                if (!d) return null;
                return (
                  <path
                    key={edge.id}
                    d={d}
                    fill="none"
                    stroke="var(--aos-border-strong)"
                    strokeWidth={1.5}
                    markerEnd="url(#arrow)"
                  />
                );
              })}
              <defs>
                <marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
                  <path d="M0,0 L7,3 L0,6 Z" fill="var(--aos-border-strong)" />
                </marker>
              </defs>
              {filteredNodes.map((n) => {
                const w = 120;
                const h = 48;
                const isSelected = selected?.id === n.id;
                return (
                  <g
                    key={n.id}
                    onClick={() => setSelectedId(n.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <rect
                      x={n.x}
                      y={n.y}
                      width={w}
                      height={h}
                      rx={4}
                      fill={isSelected ? "var(--aos-accent-light)" : "var(--aos-surface)"}
                      stroke={isSelected ? "var(--aos-accent)" : "var(--aos-border)"}
                      strokeWidth={isSelected ? 2 : 1}
                    />
                    <text x={n.x + 6} y={n.y + 16} fontSize="11" fontWeight="600" fill="var(--aos-text)">
                      {n.name.length > 14 ? n.name.slice(0, 12) + "…" : n.name}
                    </text>
                    <text x={n.x + 6} y={n.y + 32} fontSize="9" fill="var(--aos-text-secondary)">
                      {NODE_TYPE_LABEL[n.type]}
                    </text>
                    <circle
                      cx={n.x + w - 12}
                      cy={n.y + 12}
                      r={4}
                      fill={
                        n.status === "healthy"
                          ? "var(--aos-green)"
                          : n.status === "stale"
                            ? "var(--aos-amber)"
                            : n.status === "error"
                              ? "var(--aos-red)"
                              : "var(--aos-text-secondary)"
                      }
                    />
                  </g>
                );
              })}
            </svg>
            <p className="muted" style={{ fontSize: "0.7rem", marginTop: 4 }}>
              点击节点查看详情 · 共 {filteredNodes.length} 个节点显示
            </p>
          </div>
          <div className="bp-object-panel">
            {selected ? (
              <div>
                <h3 className="aos-text" style={{ fontSize: "0.85rem" }}>{selected.name}</h3>
                <div style={{ marginTop: "0.5rem" }}>
                  <span className={`bp-discover-badge bp-discover-badge-${NODE_TYPE_TONE[selected.type]}`}>
                    {NODE_TYPE_LABEL[selected.type]}
                  </span>
                  &nbsp;
                  <span className={`bp-discover-badge bp-discover-badge-${NODE_STATUS_TONE[selected.status]}`}>
                    {NODE_STATUS_LABEL[selected.status]}
                  </span>
                </div>
                {selected.meta?.description && (
                  <p className="muted" style={{ fontSize: "0.75rem", marginTop: "0.5rem" }}>
                    {selected.meta.description}
                  </p>
                )}
                <div style={{ marginTop: "0.5rem", fontSize: "0.75rem" }}>
                  {selected.meta?.rowCount != null && (
                    <div>行数: <strong>{selected.meta.rowCount.toLocaleString()}</strong></div>
                  )}
                  {selected.meta?.lastUpdated && (
                    <div>上次更新: {formatTimestamp(selected.meta.lastUpdated)}</div>
                  )}
                </div>
                {impact && (
                  <div style={{ marginTop: "0.75rem", fontSize: "0.75rem" }}>
                    <h4 className="aos-text">影响范围</h4>
                    <div>上游节点: {impact.upstream}</div>
                    <div>下游节点: {impact.downstream}</div>
                    <div>受影响总数: <strong>{impact.affected}</strong></div>
                  </div>
                )}
              </div>
            ) : (
              <p className="muted" style={{ fontSize: "0.75rem" }}>点击图谱节点查看详情</p>
            )}
          </div>
        </div>
      )}

      {tab === "list" && (
        <BpTable
          columns={["节点名", "类型", "状态", "层级", "行数", "上次更新"]}
          rows={filteredNodes.map((n) => [
            <span className="mono">{n.name}</span>,
            <span className={`bp-discover-badge bp-discover-badge-${NODE_TYPE_TONE[n.type]}`}>
              {NODE_TYPE_LABEL[n.type]}
            </span>,
            <span className={`bp-discover-badge bp-discover-badge-${NODE_STATUS_TONE[n.status]}`}>
              {NODE_STATUS_LABEL[n.status]}
            </span>,
            n.level,
            n.meta?.rowCount != null ? n.meta.rowCount.toLocaleString() : "—",
            n.meta?.lastUpdated ? formatTimestamp(n.meta.lastUpdated) : "—",
          ])}
        />
      )}

      {tab === "impact" && (
        <div>
          <BpToolbar>
            <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
              <option value="">选择节点…</option>
              {graph.nodes.map((n) => (
                <option key={n.id} value={n.id}>{n.name} ({NODE_TYPE_LABEL[n.type]})</option>
              ))}
            </select>
          </BpToolbar>
          {selected && impact ? (
            <div>
              <BpMetricGrid
                items={[
                  { label: "上游节点数", value: impact.upstream, tone: "muted" },
                  { label: "下游节点数", value: impact.downstream, tone: "muted" },
                  { label: "受影响总数", value: impact.affected, tone: impact.affected > 5 ? "warn" : "ok" },
                ]}
              />
              <h4 className="aos-text" style={{ fontSize: "0.8rem", marginTop: "0.75rem" }}>上游链路</h4>
              <BpTable
                columns={["节点名", "类型", "状态"]}
                rows={upstreamNodes(graph, selected.id).map((n) => [
                  <span className="mono">{n.name}</span>,
                  NODE_TYPE_LABEL[n.type],
                  NODE_STATUS_LABEL[n.status],
                ])}
              />
              <h4 className="aos-text" style={{ fontSize: "0.8rem", marginTop: "0.75rem" }}>下游链路</h4>
              <BpTable
                columns={["节点名", "类型", "状态"]}
                rows={downstreamNodes(graph, selected.id).map((n) => [
                  <span className="mono">{n.name}</span>,
                  NODE_TYPE_LABEL[n.type],
                  NODE_STATUS_LABEL[n.status],
                ])}
              />
            </div>
          ) : (
            <BpBanner tone="warn">请选择一个节点查看影响分析</BpBanner>
          )}
        </div>
      )}

      <BpBanner tone="info">
        对齐 <code>lineage.html</code> · 图谱/列表/影响分析三 Tab ·{" "}
        <Link to="/data/datasets">数据集</Link> ·{" "}
        <Link to="/data/health">数据健康</Link>
      </BpBanner>
    </S2Chrome>
  );
}
