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
  level: number;
  x: number;
  y: number;
  meta?: {
    rowCount?: number;
    lastUpdated?: string;
    description?: string;
    sourceTable?: string;
    targetOt?: string;
    rid?: string;
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

// ── Constants ──────────────────────────────────────────────────

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

const NODE_W = 140;
const NODE_H = 44;

// ── Pure functions ─────────────────────────────────────────────

export function formatTimestamp(iso: string | number | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(typeof iso === "number" ? iso * 1000 : iso);
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

function statusColor(status: NodeStatus): string {
  switch (status) {
    case "healthy": return "var(--aos-green, #22c55e)";
    case "stale": return "var(--aos-amber, #f59e0b)";
    case "error": return "var(--aos-red, #ef4444)";
    default: return "var(--aos-text-secondary, #888)";
  }
}

// ── Page Component ─────────────────────────────────────────────

export function DataLineagePage() {
  const { data, err, loading } = useJsonGet<LineageGraph>("/v1/data-lineage/graph");
  const graph = data ?? { nodes: [], edges: [] };

  const [selectedId, setSelectedId] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<NodeType | "all">("all");
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("graph");

  const typeCounts = useMemo(() => countByType(graph.nodes), [graph.nodes]);
  const statusCounts = useMemo(() => countByStatus(graph.nodes), [graph.nodes]);

  const visibleNodeIds = useMemo(() => {
    const filtered = filterNodes(graph.nodes, typeFilter, query);
    return new Set(filtered.map((n) => n.id));
  }, [graph.nodes, typeFilter, query]);

  const filteredNodes = useMemo(
    () => graph.nodes.filter((n) => visibleNodeIds.has(n.id)),
    [graph.nodes, visibleNodeIds],
  );

  const selected = useMemo(
    () => graph.nodes.find((n) => n.id === selectedId) ?? null,
    [graph.nodes, selectedId],
  );

  const impact = useMemo(
    () => (selected ? computeImpact(graph, selected.id) : null),
    [graph, selected],
  );

  const graphHeight = useMemo(() => {
    const max = Math.max(...graph.nodes.map((n) => n.y), 0) + NODE_H + 20;
    return Math.max(max, 400);
  }, [graph.nodes]);

  return (
    <S2Chrome title="数据沿袭" lede="数据从源到消费的完整链路 · 栖月汇微商城">
      <BpToolbar>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as NodeType | "all")}>
          <option value="all">全部类型</option>
          {Object.entries(NODE_TYPE_LABEL).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <input
          type="search"
          placeholder="搜索节点名/ID…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ minWidth: 200 }}
        />
        {selected && (
          <button
            type="button"
            className="btn-nav"
            onClick={() => setSelectedId("")}
          >
            清除选中
          </button>
        )}
      </BpToolbar>

      {loading && <p className="muted">加载中…</p>}
      {err && <p className="error">{err}</p>}
      {!loading && !err && graph.nodes.length === 0 && (
        <p className="muted">暂无沿袭数据，请先执行管道。</p>
      )}

      {graph.nodes.length > 0 && (
        <>
          <BpMetricGrid
            items={[
              { label: "数据源", value: typeCounts.source, tone: "ok" },
              { label: "管道", value: typeCounts.pipeline, tone: "ok" },
              { label: "数据集", value: typeCounts.dataset, tone: "warn" },
              { label: "对象类型", value: typeCounts.object_type, tone: "muted" },
            ]}
          />

          <BpMetricGrid
            items={[
              { label: "总节点", value: graph.nodes.length, tone: "muted" },
              { label: "总连线", value: graph.edges.length, tone: "muted" },
              { label: "健康", value: statusCounts.healthy, tone: "ok" },
              { label: "异常", value: statusCounts.error + statusCounts.stale, tone: statusCounts.error + statusCounts.stale > 0 ? "warn" : "ok" },
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
              <div className="bp-object-panel" style={{ overflow: "auto", minHeight: 400 }}>
                <svg
                  width={1000}
                  height={graphHeight}
                  style={{ display: "block" }}
                >
                  {/* Edges */}
                  {graph.edges.map((edge) => {
                    const sNode = graph.nodes.find((n) => n.id === edge.source);
                    const tNode = graph.nodes.find((n) => n.id === edge.target);
                    if (!sNode || !tNode) return null;
                    if (!visibleNodeIds.has(sNode.id) || !visibleNodeIds.has(tNode.id)) return null;
                    const x1 = sNode.x + NODE_W;
                    const y1 = sNode.y + NODE_H / 2;
                    const x2 = tNode.x;
                    const y2 = tNode.y + NODE_H / 2;
                    const midX = (x1 + x2) / 2;
                    const isHighlight = selectedId && (edge.source === selectedId || edge.target === selectedId);
                    return (
                      <path
                        key={edge.id}
                        d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                        fill="none"
                        stroke={isHighlight ? "var(--aos-accent, #3b82f6)" : "var(--aos-border-strong, #ccc)"}
                        strokeWidth={isHighlight ? 2 : 1}
                        opacity={selectedId && !isHighlight ? 0.3 : 1}
                      />
                    );
                  })}
                  {/* Nodes */}
                  {filteredNodes.map((n) => {
                    const isSelected = selected?.id === n.id;
                    return (
                      <g
                        key={n.id}
                        onClick={() => setSelectedId(isSelected ? "" : n.id)}
                        style={{ cursor: "pointer" }}
                      >
                        <rect
                          x={n.x}
                          y={n.y}
                          width={NODE_W}
                          height={NODE_H}
                          rx={4}
                          fill={isSelected ? "var(--aos-accent-light, #dbeafe)" : "var(--aos-surface, #fff)"}
                          stroke={isSelected ? "var(--aos-accent, #3b82f6)" : "var(--aos-border, #ddd)"}
                          strokeWidth={isSelected ? 2 : 1}
                        />
                        <text x={n.x + 6} y={n.y + 16} fontSize="11" fontWeight="600" fill="var(--aos-text, #1a1a1a)">
                          {n.name.length > 16 ? n.name.slice(0, 14) + "…" : n.name}
                        </text>
                        <text x={n.x + 6} y={n.y + 30} fontSize="9" fill="var(--aos-text-secondary, #888)">
                          {NODE_TYPE_LABEL[n.type]}
                          {n.meta?.rowCount != null && n.meta.rowCount > 0 ? ` · ${n.meta.rowCount.toLocaleString()} 行` : ""}
                        </text>
                        <circle
                          cx={n.x + NODE_W - 12}
                          cy={n.y + 12}
                          r={4}
                          fill={statusColor(n.status)}
                        />
                      </g>
                    );
                  })}
                </svg>
                <p className="muted" style={{ fontSize: "0.7rem", marginTop: 4 }}>
                  点击节点查看详情 · 共 {filteredNodes.length} / {graph.nodes.length} 个节点显示
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
                      {selected.meta?.sourceTable && (
                        <div>源表: <code>{selected.meta.sourceTable}</code></div>
                      )}
                      {selected.meta?.targetOt && (
                        <div>目标 OT: <strong>{selected.meta.targetOt}</strong></div>
                      )}
                      {selected.meta?.rid && (
                        <div>RID: <code style={{ fontSize: "0.7rem" }}>{selected.meta.rid}</code></div>
                      )}
                      {selected.meta?.lastUpdated && (
                        <div>更新时间: {formatTimestamp(selected.meta.lastUpdated)}</div>
                      )}
                    </div>
                    {impact && (
                      <div style={{ marginTop: "0.75rem", fontSize: "0.75rem" }}>
                        <h4 className="aos-text">影响范围</h4>
                        <div>上游: {impact.upstream} 个节点</div>
                        <div>下游: {impact.downstream} 个节点</div>
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
              columns={["节点名", "类型", "状态", "层级", "行数", "源表/描述"]}
              rows={filteredNodes.map((n) => [
                <span className="mono">{n.name}</span>,
                <span className={`bp-discover-badge bp-discover-badge-${NODE_TYPE_TONE[n.type]}`}>
                  {NODE_TYPE_LABEL[n.type]}
                </span>,
                <span className={`bp-discover-badge bp-discover-badge-${NODE_STATUS_TONE[n.status]}`}>
                  {NODE_STATUS_LABEL[n.status]}
                </span>,
                n.level,
                n.meta?.rowCount != null && n.meta.rowCount > 0 ? n.meta.rowCount.toLocaleString() : "—",
                <span className="muted" style={{ fontSize: "0.75rem" }}>
                  {n.meta?.sourceTable || n.meta?.description || "—"}
                </span>,
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
                      { label: "受影响总数", value: impact.affected, tone: impact.affected > 10 ? "warn" : "ok" },
                    ]}
                  />
                  <h4 className="aos-text" style={{ fontSize: "0.8rem", marginTop: "0.75rem" }}>上游链路</h4>
                  <BpTable
                    columns={["节点名", "类型", "状态"]}
                    rows={upstreamNodes(graph, selected.id).map((n) => [
                      <span className="mono">{n.name}</span>,
                      NODE_TYPE_LABEL[n.type],
                      <span className={`bp-discover-badge bp-discover-badge-${NODE_STATUS_TONE[n.status]}`}>
                        {NODE_STATUS_LABEL[n.status]}
                      </span>,
                    ])}
                  />
                  <h4 className="aos-text" style={{ fontSize: "0.8rem", marginTop: "0.75rem" }}>下游链路</h4>
                  <BpTable
                    columns={["节点名", "类型", "状态"]}
                    rows={downstreamNodes(graph, selected.id).map((n) => [
                      <span className="mono">{n.name}</span>,
                      NODE_TYPE_LABEL[n.type],
                      <span className={`bp-discover-badge bp-discover-badge-${NODE_STATUS_TONE[n.status]}`}>
                        {NODE_STATUS_LABEL[n.status]}
                      </span>,
                    ])}
                  />
                </div>
              ) : (
                <BpBanner tone="warn">请选择一个节点查看影响分析</BpBanner>
              )}
            </div>
          )}
        </>
      )}

      <BpBanner tone="info">
        数据沿袭 · 栖月汇微商城 ·{" "}
        <Link to="/data/datasets">数据集</Link> ·{" "}
        <Link to="/data/health">数据健康</Link>
      </BpBanner>
    </S2Chrome>
  );
}
