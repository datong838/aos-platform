/**
 * 186w · Pipeline 画布页 · 对齐 foundry/html/pipeline.html（图1）
 * 层次：顶栏操作 · 中网格 DAG · 底预览 · 右输出属性
 * Phase E-02~E-06：节点拖拽 + 算子工具栏 + 管道类型 + 输出配置 + 预览增强
 * W3-C6：视图 Tab（编辑/历史）+ 变换节点配置/试运行 · 优先接 phase5 pipeline API
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet, apiPost, apiPut } from "../../api/client";
import { BpBanner, BpToolbar } from "./blueprintUi";
import { S2Chrome, useJsonGet } from "./shared";
import {
  buildStatusBadge,
  pipelineDisplayTitle,
  tableKeyFromBlob,
  TABLE_LABELS,
  type PipelineMeta,
} from "./pipelineMeta";

type PreviewResult = {
  columns?: string[];
  rows?: Record<string, unknown>[];
  total?: number;
  objectType?: string;
};

type NodeType = "input" | "transform" | "output";

export type HistoryItem = {
  id: string;
  pipeline_id?: string;
  action?: string;
  actor?: string;
  detail?: string;
  created_at?: number;
};

export type GraphNode = {
  id: string;
  name?: string;
  node_type?: string;
  position_x?: number;
  position_y?: number;
  config?: Record<string, unknown>;
};

export type GraphPayload = {
  pipeline_id?: string;
  nodes?: GraphNode[];
  edges?: { source_node_id?: string; target_node_id?: string }[];
  demo?: boolean;
};

export type XformConfig = { expression: string; filter: string };

/** W3-C6 · 合成演示历史（API 失败时） */
export function buildDemoHistory(pipe: PipelineMeta | null, pipelineId: string): HistoryItem[] {
  const now = Date.now() / 1000;
  const build = pipe?.lastBuild;
  return [
    {
      id: `demo-h1-${pipelineId}`,
      pipeline_id: pipelineId,
      action: "created",
      actor: "system",
      detail: "演示路径 · 管道创建",
      created_at: now - 86400,
    },
    {
      id: `demo-h2-${pipelineId}`,
      pipeline_id: pipelineId,
      action: build?.status ? "deployed" : "updated",
      actor: "system",
      detail: build?.id
        ? `演示路径 · Build ${build.id} · ${build.status || "—"}`
        : "演示路径 · 最近保存",
      created_at: now - 3600,
    },
    {
      id: `demo-h3-${pipelineId}`,
      pipeline_id: pipelineId,
      action: "run",
      actor: "system",
      detail: "演示路径 · 试运行",
      created_at: now - 300,
    },
  ];
}

export function formatHistoryTime(ts?: number): string {
  if (ts == null || !Number.isFinite(ts)) return "—";
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return "—";
  }
}

export function historyPathLabel(demo: boolean): string {
  return demo ? "演示路径" : "API";
}

export function pickTransformNode(graph: GraphPayload | null): GraphNode | null {
  const nodes = graph?.nodes || [];
  return (
    nodes.find((n) => (n.node_type || "").toLowerCase() === "transform") ||
    nodes.find((n) => (n.name || "").toLowerCase().includes("transform")) ||
    null
  );
}

export function xformStorageKey(pipelineId: string): string {
  return `aos.pipeline.xform.${pipelineId}`;
}

export function loadLocalXform(pipelineId: string): XformConfig | null {
  try {
    const raw = localStorage.getItem(xformStorageKey(pipelineId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as XformConfig;
    if (typeof parsed?.expression !== "string") return null;
    return { expression: parsed.expression, filter: String(parsed.filter || "") };
  } catch {
    return null;
  }
}

export function saveLocalXform(pipelineId: string, cfg: XformConfig): void {
  localStorage.setItem(xformStorageKey(pipelineId), JSON.stringify(cfg));
}

export function formatTrialMsg(ok: boolean, demo: boolean, detail?: string): string {
  const path = demo ? "演示路径" : "API";
  if (ok) return `试运行成功 · ${path}${detail ? ` · ${detail}` : ""}`;
  return `试运行失败 · ${path}${detail ? ` · ${detail}` : ""}`;
}

/** 算子工具栏定义 · 15 个算子分 3 组 */
const OPERATORS: { group: string; items: { id: string; label: string; kind: NodeType }[] }[] = [
  {
    group: "输入",
    items: [
      { id: "src-jdbc", label: "JDBC 源", kind: "input" },
      { id: "src-file", label: "文件源", kind: "input" },
      { id: "src-stream", label: "流式源", kind: "input" },
    ],
  },
  {
    group: "变换",
    items: [
      { id: "tf-filter", label: "过滤", kind: "transform" },
      { id: "tf-join", label: "关联", kind: "transform" },
      { id: "tf-aggregate", label: "聚合", kind: "transform" },
      { id: "tf-map", label: "映射", kind: "transform" },
      { id: "tf-sort", label: "排序", kind: "transform" },
      { id: "tf-union", label: "合并", kind: "transform" },
      { id: "tf-lookup", label: "查表", kind: "transform" },
      { id: "tf-udf", label: "自定义函数", kind: "transform" },
    ],
  },
  {
    group: "输出",
    items: [
      { id: "out-dataset", label: "数据集", kind: "output" },
      { id: "out-object", label: "对象实例", kind: "output" },
      { id: "out-stream", label: "流式输出", kind: "output" },
      { id: "out-webhook", label: "Webhook", kind: "output" },
    ],
  },
];

const PIPE_TYPES = [
  { id: "batch", label: "批量" },
  { id: "incremental", label: "增量" },
  { id: "streaming", label: "流式" },
] as const;

const WRITE_MODES = [
  { id: "SNAPSHOT", label: "快照" },
  { id: "APPEND", label: "追加" },
  { id: "MERGE", label: "合并" },
  { id: "UPDATE", label: "更新" },
  { id: "DELETE", label: "删除" },
  { id: "UPSERT", label: "插入或更新" },
] as const;

function cellText(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "object") {
    try {
      return JSON.stringify(v);
    } catch {
      return String(v);
    }
  }
  const s = String(v);
  return s.length > 48 ? `${s.slice(0, 45)}…` : s;
}

/** 推断列类型 */
function inferColumnType(rows: Record<string, unknown>[], col: string): string {
  for (const row of rows) {
    const v = row[col];
    if (v == null) continue;
    if (typeof v === "number") return "number";
    if (typeof v === "boolean") return "bool";
    if (typeof v === "string") {
      if (/^\d{4}-\d{2}-\d{2}[T ]/.test(v)) return "date";
      return "string";
    }
    return "json";
  }
  return "—";
}

export function PipelineCanvasPage() {
  const { pipelineId = "" } = useParams();
  const { data, err, reload } = useJsonGet<{ items: PipelineMeta[] }>("/v1/pipelines");
  const pipe = useMemo(
    () => (data?.items || []).find((p) => p.id === pipelineId) || null,
    [data?.items, pipelineId],
  );
  const title = pipe ? pipelineDisplayTitle(pipe) : pipelineId || "管道";
  const badge = buildStatusBadge(pipe?.lastBuild?.status);
  const table = tableKeyFromBlob(pipe?.id, pipe?.datasetRid);
  const outLabel = table ? TABLE_LABELS[table]?.zh || pipe?.datasetRid : pipe?.datasetRid || "输出数据集";
  const otHint = pipe?.objectTypeHint || (table ? TABLE_LABELS[table]?.ot : undefined);

  const [selected, setSelected] = useState<"input" | "transform" | "output">("output");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [previewErr, setPreviewErr] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // Phase E-02: 节点拖拽位置
  const [nodePositions, setNodePositions] = useState<Record<string, { x: number; y: number }>>({
    input: { x: 60, y: 60 },
    transform: { x: 300, y: 60 },
    output: { x: 540, y: 60 },
  });
  const [draggingNode, setDraggingNode] = useState<string | null>(null);

  // Phase E-05: 管道类型
  const [pipeType, setPipeType] = useState<string>("batch");

  // Phase E-06: 写入模式
  const [writeMode, setWriteMode] = useState<string>("SNAPSHOT");

  // Phase E-03: 算子拖入画布
  const [extraNodes, setExtraNodes] = useState<{ id: string; label: string; kind: NodeType; x: number; y: number }[]>([]);

  // Phase 7: 画布缩放 + 右键菜单 + 连接线管理
  const [zoom, setZoom] = useState(1);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; nodeId: string } | null>(null);
  const [connections, setConnections] = useState<{ from: string; to: string }[]>([]);
  const [linkingFrom, setLinkingFrom] = useState<string | null>(null);
  const [showStats, setShowStats] = useState(false);

  // W3-C6: 视图 Tab + 历史 + 变换配置
  const [viewTab, setViewTab] = useState<"edit" | "history">("edit");
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [historyDemo, setHistoryDemo] = useState(false);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [graph, setGraph] = useState<GraphPayload | null>(null);
  const [xform, setXform] = useState<XformConfig>({ expression: "row", filter: "" });
  const [xformMsg, setXformMsg] = useState<string | null>(null);
  const [xformBusy, setXformBusy] = useState(false);
  const transformNode = useMemo(() => pickTransformNode(graph), [graph]);

  function handleNodeDragStart(e: React.DragEvent, nodeKey: string) {
    setDraggingNode(nodeKey);
    e.dataTransfer.effectAllowed = "move";
  }

  function handleNodeDragEnd() {
    setDraggingNode(null);
  }

  function handleCanvasDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }

  function handleCanvasDrop(e: React.DragEvent) {
    e.preventDefault();
    const opId = e.dataTransfer.getData("text/plain");
    if (!opId) return;
    // 查找算子定义
    for (const group of OPERATORS) {
      const op = group.items.find((i) => i.id === opId);
      if (op) {
        const rect = e.currentTarget.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        setExtraNodes((prev) => [
          ...prev,
          { id: `${op.id}-${Date.now()}`, label: op.label, kind: op.kind, x, y },
        ]);
        return;
      }
    }
  }

  function handleNodeMouseMove(e: React.MouseEvent) {
    if (!draggingNode) return;
    const rect = (e.currentTarget as HTMLElement).closest(".bp-pipe-dag")?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left - 70;
    const y = e.clientY - rect.top - 30;
    setNodePositions((prev) => ({ ...prev, [draggingNode]: { x: Math.max(0, x), y: Math.max(0, y) } }));
  }

  function removeExtraNode(id: string) {
    setExtraNodes((prev) => prev.filter((n) => n.id !== id));
    setConnections((prev) => prev.filter((c) => c.from !== id && c.to !== id));
  }

  // Phase 7: 缩放控制
  function handleZoomIn() { setZoom((z) => Math.min(z + 0.1, 2)); }
  function handleZoomOut() { setZoom((z) => Math.max(z - 0.1, 0.5)); }
  function handleZoomReset() { setZoom(1); }

  // Phase 7: 右键菜单
  function handleContextMenu(e: React.MouseEvent, nodeId: string) {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, nodeId });
  }

  function closeContextMenu() { setContextMenu(null); }

  // Phase 7: 连接线管理
  function startLink(nodeId: string) {
    setLinkingFrom(nodeId);
    setContextMenu(null);
  }

  function completeLink(targetNodeId: string) {
    if (linkingFrom && linkingFrom !== targetNodeId) {
      setConnections((prev) => {
        const exists = prev.some((c) => c.from === linkingFrom && c.to === targetNodeId);
        if (exists) return prev;
        return [...prev, { from: linkingFrom, to: targetNodeId }];
      });
    }
    setLinkingFrom(null);
  }

  function removeConnection(from: string, to: string) {
    setConnections((prev) => prev.filter((c) => !(c.from === from && c.to === to)));
    setContextMenu(null);
  }

  // Phase 7: 清空画布
  function clearCanvas() {
    setExtraNodes([]);
    setConnections([]);
    setContextMenu(null);
  }

  useEffect(() => {
    setSelected("output");
    setPreview(null);
    setPreviewErr(null);
    setViewTab("edit");
    setXformMsg(null);
    const local = loadLocalXform(pipelineId);
    if (local) setXform(local);
    else setXform({ expression: "row", filter: "" });
  }, [pipelineId]);

  // W3-C6 · 拉取 graph（变换节点 id）
  useEffect(() => {
    if (!pipelineId) return;
    let cancelled = false;
    (async () => {
      try {
        const g = await apiGet<GraphPayload>(`/v1/pipelines/${encodeURIComponent(pipelineId)}/graph`);
        if (cancelled) return;
        setGraph(g);
        const xf = pickTransformNode(g);
        const cfg = xf?.config;
        if (cfg && typeof cfg.expression === "string") {
          setXform({
            expression: String(cfg.expression),
            filter: String(cfg.filter || ""),
          });
        }
      } catch {
        if (!cancelled) setGraph(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pipelineId]);

  // W3-C6 · 拉取运行历史
  useEffect(() => {
    if (!pipelineId || viewTab !== "history") return;
    let cancelled = false;
    (async () => {
      setHistoryBusy(true);
      try {
        const res = await apiGet<{ items?: HistoryItem[]; demo?: boolean }>(
          `/v1/pipelines/${encodeURIComponent(pipelineId)}/history`,
        );
        if (cancelled) return;
        const items = res.items || [];
        if (items.length === 0) {
          setHistoryItems(buildDemoHistory(pipe, pipelineId));
          setHistoryDemo(true);
        } else {
          setHistoryItems(items);
          setHistoryDemo(Boolean(res.demo));
        }
      } catch {
        if (!cancelled) {
          setHistoryItems(buildDemoHistory(pipe, pipelineId));
          setHistoryDemo(true);
        }
      } finally {
        if (!cancelled) setHistoryBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pipelineId, viewTab, pipe]);

  async function saveXformConfig() {
    setXformBusy(true);
    setXformMsg(null);
    const nodeId = transformNode?.id || `demo-xf-${pipelineId}`;
    try {
      const res = await apiPut<{ demo?: boolean }>(
        `/v1/pipelines/${encodeURIComponent(pipelineId)}/nodes/${encodeURIComponent(nodeId)}/config`,
        { config: xform },
      );
      saveLocalXform(pipelineId, xform);
      setXformMsg(`已保存配置 · ${historyPathLabel(Boolean(res.demo || graph?.demo))}`);
    } catch (e) {
      saveLocalXform(pipelineId, xform);
      setXformMsg(`已保存 · 演示路径 · localStorage${e instanceof Error ? `（${e.message}）` : ""}`);
    } finally {
      setXformBusy(false);
    }
  }

  async function runXformTrial() {
    setXformBusy(true);
    setXformMsg(null);
    const nodeId = transformNode?.id || `demo-xf-${pipelineId}`;
    try {
      const res = await apiPost<{ status?: string; latency_ms?: number; demo?: boolean; output_rows?: unknown[] }>(
        `/v1/pipelines/${encodeURIComponent(pipelineId)}/nodes/${encodeURIComponent(nodeId)}/trial-run`,
        { sample_input: { expression: xform.expression, filter: xform.filter } },
      );
      const demo = Boolean(res.demo || graph?.demo);
      setXformMsg(
        formatTrialMsg(res.status === "ok" || !res.status, demo, `${res.latency_ms ?? "—"}ms · ${res.output_rows?.length ?? 0} 行`),
      );
    } catch (e) {
      setXformMsg(formatTrialMsg(false, true, e instanceof Error ? e.message : String(e)));
    } finally {
      setXformBusy(false);
    }
  }

  useEffect(() => {
    if (!pipe?.datasetRid && !otHint) return;
    let cancelled = false;
    (async () => {
      setPreviewBusy(true);
      setPreviewErr(null);
      try {
        const body: Record<string, unknown> = { limit: 8 };
        if (otHint) body.objectType = otHint;
        if (pipe?.datasetRid) body.datasetRid = pipe.datasetRid;
        const result = await apiPost<PreviewResult>("/v1/analytics/datasets/preview", body);
        if (!cancelled) setPreview(result);
      } catch (e) {
        if (!cancelled) setPreviewErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setPreviewBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pipe?.datasetRid, otHint]);

  const cols = preview?.columns?.slice(0, 6) || [];
  const rows = preview?.rows?.slice(0, 5) || [];

  return (
    <S2Chrome title={title} lede="Pipeline Builder · 画布">
      <BpToolbar>
        <Link to="/data/pipelines" className="btn-nav">
          ← 管道列表
        </Link>
        <select className="bp-pipe-branch" aria-label="分支" defaultValue="master" disabled>
          <option value="master">master</option>
        </select>
        {/* Phase E-05: 管道类型选择器 */}
        <div className="bp-pipe-type-selector" role="radiogroup" aria-label="管道类型">
          {PIPE_TYPES.map((t) => (
            <button
              key={t.id}
              type="button"
              role="radio"
              aria-checked={pipeType === t.id}
              className={`btn${pipeType === t.id ? " is-active" : ""}`}
              onClick={() => setPipeType(t.id)}
              style={{ fontSize: "0.75rem", padding: "2px 8px" }}
            >
              {t.label}
            </button>
          ))}
        </div>
        <button type="button" className="btn">
          保存
        </button>
        <Link to="/data/pipeline-proposals" className="btn-nav">
          提议
        </Link>
        <Link to="/data/schedules" className="btn-nav">
          打开计划编辑器
        </Link>
        <Link to="/data/builds" className="btn-primary">
          部署
        </Link>
        <span className={`bp-pipe-badge bp-pipe-badge-${badge.tone}`}>
          <span className="bp-pipe-badge-dot" />
          {pipe?.lastBuild?.id ? `Build ${pipe.lastBuild.id}` : "Build"} · {badge.label}
        </span>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
      </BpToolbar>

      {/* Phase E-03: 算子工具栏 */}
      <div className="bp-pipe-operator-bar" style={{ display: "flex", gap: 12, padding: "6px 12px", overflowX: "auto", borderBottom: "1px solid var(--aos-border, #2a3540)" }}>
        {OPERATORS.map((group) => (
          <div key={group.group} style={{ display: "flex", gap: 4, alignItems: "center", flexShrink: 0 }}>
            <span className="muted" style={{ fontSize: "0.7rem", marginRight: 4 }}>{group.group}</span>
            {group.items.map((op) => (
              <button
                key={op.id}
                type="button"
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData("text/plain", op.id);
                  e.dataTransfer.effectAllowed = "copy";
                }}
                className="btn-nav"
                style={{ fontSize: "0.7rem", padding: "2px 8px", cursor: "grab" }}
                title={`拖拽到画布添加「${op.label}」`}
              >
                {op.label}
              </button>
            ))}
          </div>
        ))}
      </div>

      {err && <p className="error">{err}</p>}
      {!err && !pipe && <BpBanner tone="warn">未找到管道 {pipelineId}</BpBanner>}

      {pipe && (
        <>
          {/* W3-C6 · 视图 Tab */}
          <div className="w3-c6-view-tabs" role="tablist" aria-label="管道视图">
            <button
              type="button"
              role="tab"
              aria-selected={viewTab === "edit"}
              className={`btn${viewTab === "edit" ? " is-active" : ""}`}
              onClick={() => setViewTab("edit")}
            >
              编辑
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={viewTab === "history"}
              className={`btn${viewTab === "history" ? " is-active" : ""}`}
              onClick={() => setViewTab("history")}
            >
              历史
            </button>
            {viewTab === "history" && (
              <span className={`w3-c6c7-path-badge ${historyDemo ? "is-demo" : "is-live"}`}>
                {historyPathLabel(historyDemo)}
              </span>
            )}
          </div>

          {viewTab === "history" && (
            <div className="w3-c6-history">
              {historyBusy && <p className="muted">加载历史…</p>}
              {!historyBusy && historyItems.length === 0 && <p className="muted">暂无历史记录</p>}
              <ul className="w3-c6-history-list">
                {historyItems.map((h) => (
                  <li key={h.id} className="w3-c6-history-item">
                    <div className="w3-c6-history-head">
                      <strong>{h.action || "event"}</strong>
                      <span className="muted">{formatHistoryTime(h.created_at)}</span>
                    </div>
                    <div className="muted" style={{ fontSize: "0.75rem" }}>
                      {h.actor || "system"} · {h.detail || "—"}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {viewTab === "edit" && (
        <div className="bp-pipe-canvas-shell">
          {/* Phase 7: 画布工具栏 - 缩放 + 统计 + 清空 */}
          <div className="bp-pipe-canvas-toolbar" style={{ display: "flex", gap: 8, padding: "4px 12px", alignItems: "center", borderBottom: "1px solid var(--aos-border, #e2e8f0)", background: "var(--aos-surface, #f7fafc)" }}>
            <button type="button" className="btn" onClick={handleZoomOut} style={{ fontSize: "0.75rem", padding: "2px 8px" }} title="缩小">−</button>
            <span style={{ fontSize: "0.75rem", minWidth: 48, textAlign: "center" }}>{Math.round(zoom * 100)}%</span>
            <button type="button" className="btn" onClick={handleZoomIn} style={{ fontSize: "0.75rem", padding: "2px 8px" }} title="放大">+</button>
            <button type="button" className="btn" onClick={handleZoomReset} style={{ fontSize: "0.75rem", padding: "2px 8px" }} title="重置缩放">1:1</button>
            <div style={{ width: 1, height: 18, background: "var(--aos-border, #e2e8f0)", margin: "0 4px" }} />
            <button type="button" className="btn" onClick={() => setShowStats((v) => !v)} style={{ fontSize: "0.75rem", padding: "2px 8px" }}>
              {showStats ? "隐藏统计" : "统计"}
            </button>
            {showStats && (
              <span className="muted" style={{ fontSize: "0.7rem" }}>
                节点 {3 + extraNodes.length} · 连接 {2 + connections.length} · 算子组 {OPERATORS.length}
              </span>
            )}
            <div style={{ flex: 1 }} />
            {linkingFrom && (
              <span style={{ fontSize: "0.7rem", color: "var(--aos-accent, #3182ce)" }}>
                连接模式 · 点击目标节点完成连接
              </span>
            )}
            <button type="button" className="btn" onClick={clearCanvas} style={{ fontSize: "0.75rem", padding: "2px 8px" }} title="清空额外节点">清空</button>
          </div>

          <div className="bp-pipe-canvas-main">
            <div
              className="grid-pattern bp-pipe-dag"
              onDragOver={handleCanvasDragOver}
              onDrop={handleCanvasDrop}
              onMouseMove={handleNodeMouseMove}
              onMouseUp={handleNodeDragEnd}
              onClick={closeContextMenu}
              style={{ position: "relative", minHeight: 200, transform: `scale(${zoom})`, transformOrigin: "top left", transition: "transform 0.15s ease" }}
            >
              <svg className="bp-pipe-flow-svg" preserveAspectRatio="none" viewBox="0 0 720 200" aria-hidden>
                <path className="flow-line flow-line-active" d={`M ${nodePositions.input.x + 100} ${nodePositions.input.y + 30} C ${nodePositions.input.x + 140} ${nodePositions.input.y + 30}, ${nodePositions.transform.x - 40} ${nodePositions.transform.y + 30}, ${nodePositions.transform.x} ${nodePositions.transform.y + 30}`} />
                <path className="flow-line flow-line-active" d={`M ${nodePositions.transform.x + 100} ${nodePositions.transform.y + 30} C ${nodePositions.transform.x + 140} ${nodePositions.transform.y + 30}, ${nodePositions.output.x - 40} ${nodePositions.output.y + 30}, ${nodePositions.output.x} ${nodePositions.output.y + 30}`} />
              </svg>
              <div className="bp-pipe-nodes" style={{ position: "relative" }}>
                <button
                  type="button"
                  draggable
                  onDragStart={(e) => handleNodeDragStart(e, "input")}
                  onDragEnd={handleNodeDragEnd}
                  className={`pipeline-node bp-pipe-node bp-pipe-node-input${selected === "input" ? " is-selected" : ""}${linkingFrom === "input" ? " is-linking" : ""}`}
                  onClick={() => {
                    if (linkingFrom) { completeLink("input"); }
                    else { setSelected("input"); }
                  }}
                  onContextMenu={(e) => handleContextMenu(e, "input")}
                  style={{ position: "absolute", left: nodePositions.input.x, top: nodePositions.input.y, cursor: "grab" }}
                >
                  <div className="bp-pipe-node-head">
                    <span className="bp-pipe-node-icon bp-pipe-node-icon-amber" />
                    <span className="bp-pipe-node-kind bp-pipe-kind-amber">输入</span>
                  </div>
                  <div className="bp-pipe-node-title">{pipe.sourceId || "source"}</div>
                  <div className="bp-pipe-node-sub">Source</div>
                </button>

                <button
                  type="button"
                  draggable
                  onDragStart={(e) => handleNodeDragStart(e, "transform")}
                  onDragEnd={handleNodeDragEnd}
                  className={`pipeline-node bp-pipe-node bp-pipe-node-xform${selected === "transform" ? " is-selected" : ""}${linkingFrom === "transform" ? " is-linking" : ""}`}
                  onClick={() => {
                    if (linkingFrom) { completeLink("transform"); }
                    else { setSelected("transform"); }
                  }}
                  onContextMenu={(e) => handleContextMenu(e, "transform")}
                  style={{ position: "absolute", left: nodePositions.transform.x, top: nodePositions.transform.y, cursor: "grab" }}
                >
                  <div className="bp-pipe-node-head">
                    <span className="bp-pipe-node-icon bp-pipe-node-icon-cyan" />
                    <span className="bp-pipe-node-kind bp-pipe-kind-cyan">变换</span>
                  </div>
                  <div className="bp-pipe-node-title">Ingest</div>
                  <div className="bp-pipe-node-sub">表 → 对象实例</div>
                </button>

                <button
                  type="button"
                  draggable
                  onDragStart={(e) => handleNodeDragStart(e, "output")}
                  onDragEnd={handleNodeDragEnd}
                  className={`pipeline-node bp-pipe-node bp-pipe-node-out${selected === "output" ? " is-selected" : ""}${linkingFrom === "output" ? " is-linking" : ""}`}
                  onClick={() => {
                    if (linkingFrom) { completeLink("output"); }
                    else { setSelected("output"); }
                  }}
                  onContextMenu={(e) => handleContextMenu(e, "output")}
                  style={{ position: "absolute", left: nodePositions.output.x, top: nodePositions.output.y, cursor: "grab" }}
                >
                  <div className="bp-pipe-node-head">
                    <span className="bp-pipe-node-icon bp-pipe-node-icon-emerald" />
                    <span className="bp-pipe-node-kind bp-pipe-kind-emerald">输出</span>
                  </div>
                  <div className="bp-pipe-node-title">{outLabel}</div>
                  <div className="bp-pipe-node-sub">{pipe.datasetRid || "dataset"}</div>
                </button>

                {/* Phase E-03: 拖入的额外算子节点 */}
                {extraNodes.map((n) => (
                  <button
                    key={n.id}
                    type="button"
                    className={`pipeline-node bp-pipe-node bp-pipe-node-${n.kind === "input" ? "input" : n.kind === "transform" ? "xform" : "out"}${linkingFrom === n.id ? " is-linking" : ""}`}
                    onClick={() => {
                      if (linkingFrom) { completeLink(n.id); }
                    }}
                    onContextMenu={(e) => handleContextMenu(e, n.id)}
                    onDoubleClick={() => removeExtraNode(n.id)}
                    style={{ position: "absolute", left: n.x, top: n.y, cursor: "pointer", opacity: 0.9 }}
                    title="双击移除 · 右键菜单"
                  >
                    <div className="bp-pipe-node-head">
                      <span className={`bp-pipe-node-icon bp-pipe-node-icon-${n.kind === "input" ? "amber" : n.kind === "transform" ? "cyan" : "emerald"}`} />
                      <span className={`bp-pipe-node-kind bp-pipe-kind-${n.kind === "input" ? "amber" : n.kind === "transform" ? "cyan" : "emerald"}`}>
                        {n.kind === "input" ? "输入" : n.kind === "transform" ? "变换" : "输出"}
                      </span>
                    </div>
                    <div className="bp-pipe-node-title">{n.label}</div>
                    <div className="bp-pipe-node-sub">双击移除</div>
                  </button>
                ))}
              </div>
              {/* Phase 7: 额外连接线渲染 */}
              {connections.length > 0 && (
                <svg className="bp-pipe-flow-svg" preserveAspectRatio="none" viewBox="0 0 720 200" aria-hidden style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none", zIndex: 0 }}>
                  {connections.map((c, i) => {
                    const nodePos = (id: string) => {
                      if (id === "input") return nodePositions.input;
                      if (id === "transform") return nodePositions.transform;
                      if (id === "output") return nodePositions.output;
                      const ex = extraNodes.find((n) => n.id === id);
                      return ex ? { x: ex.x, y: ex.y } : { x: 0, y: 0 };
                    };
                    const from = nodePos(c.from);
                    const to = nodePos(c.to);
                    return (
                      <path key={i} className="flow-line flow-line-dashed" d={`M ${from.x + 100} ${from.y + 30} C ${from.x + 140} ${from.y + 30}, ${to.x - 40} ${to.y + 30}, ${to.x} ${to.y + 30}`} strokeDasharray="4 3" opacity={0.5} />
                    );
                  })}
                </svg>
              )}
            </div>

            {/* Phase 7: 右键菜单 */}
            {contextMenu && (
              <div
                className="bp-context-menu"
                style={{
                  position: "fixed",
                  left: contextMenu.x,
                  top: contextMenu.y,
                  zIndex: 1000,
                  background: "var(--aos-surface, #fff)",
                  border: "1px solid var(--aos-border, #e2e8f0)",
                  borderRadius: 4,
                  boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                  padding: "4px 0",
                  minWidth: 140,
                }}
              >
                <button
                  type="button"
                  className="bp-context-item"
                  style={{ display: "block", width: "100%", padding: "6px 12px", textAlign: "left", background: "none", border: "none", cursor: "pointer", fontSize: "0.8rem" }}
                  onClick={() => startLink(contextMenu.nodeId)}
                >
                  从此节点建立连接…
                </button>
                {linkingFrom && linkingFrom !== contextMenu.nodeId && (
                  <button
                    type="button"
                    className="bp-context-item"
                    style={{ display: "block", width: "100%", padding: "6px 12px", textAlign: "left", background: "none", border: "none", cursor: "pointer", fontSize: "0.8rem" }}
                    onClick={() => completeLink(contextMenu.nodeId)}
                  >
                    连接到此节点
                  </button>
                )}
                {connections.filter((c) => c.from === contextMenu.nodeId || c.to === contextMenu.nodeId).map((c, i) => (
                  <button
                    key={i}
                    type="button"
                    className="bp-context-item"
                    style={{ display: "block", width: "100%", padding: "6px 12px", textAlign: "left", background: "none", border: "none", cursor: "pointer", fontSize: "0.8rem", color: "#e53e3e" }}
                    onClick={() => removeConnection(c.from, c.to)}
                  >
                    移除连接 {c.from} → {c.to}
                  </button>
                ))}
                <div style={{ height: 1, background: "var(--aos-border, #e2e8f0)", margin: "4px 0" }} />
                <button
                  type="button"
                  className="bp-context-item"
                  style={{ display: "block", width: "100%", padding: "6px 12px", textAlign: "left", background: "none", border: "none", cursor: "pointer", fontSize: "0.8rem" }}
                  onClick={() => { closeContextMenu(); }}
                >
                  关闭菜单
                </button>
              </div>
            )}

            <div className="bp-pipe-preview">
              <div className="bp-pipe-preview-bar">
                <span>输出预览 · {outLabel}</span>
                <span className="muted">
                  {previewBusy ? "加载中…" : preview?.total != null ? `${preview.total} 行` : "采样"}
                </span>
              </div>
              <div className="bp-pipe-preview-body">
                {previewErr && <p className="error">{previewErr}</p>}
                {!previewErr && cols.length > 0 && (
                  <table className="bp-pipe-preview-table">
                    <thead>
                      <tr>
                        {cols.map((c) => (
                          <th key={c}>
                            {c}
                            <span className="bp-pipe-col-type" style={{ marginLeft: 4, fontSize: "0.65rem", opacity: 0.6 }}>
                              {inferColumnType(rows, c)}
                            </span>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, i) => (
                        <tr key={i}>
                          {cols.map((c) => (
                            <td key={c}>{cellText(row[c])}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                {!previewErr && !previewBusy && cols.length === 0 && (
                  <p className="muted">暂无预览行 · 可到数据集页核对对象实例</p>
                )}
              </div>
            </div>
          </div>

          <aside className="bp-pipe-inspector">
            <div className="bp-pipe-inspector-block">
              <h3 className="bp-pipe-inspector-title">
                {selected === "input" && "输入源"}
                {selected === "transform" && "变换"}
                {selected === "output" && "输出数据集"}
              </h3>
              <p className="muted bp-pipe-inspector-lede">
                {selected === "input" && (pipe.sourceId || "—")}
                {selected === "transform" && (
                  transformNode
                    ? `${transformNode.name || "transform"} · ${transformNode.id}`
                    : "Ingest · 变换配置（演示节点）"
                )}
                {selected === "output" && `${outLabel}${otHint ? ` · ${otHint}` : ""}`}
              </p>
            </div>

            {selected === "transform" && (
              <div className="w3-c6-xform">
                {graph?.demo && (
                  <span className="w3-c6c7-path-badge is-demo">演示路径 · graph</span>
                )}
                <label className="bp-pipe-field">
                  <span>表达式</span>
                  <textarea
                    className="w3-c6-xform-input"
                    rows={3}
                    value={xform.expression}
                    onChange={(e) => setXform((c) => ({ ...c, expression: e.target.value }))}
                    aria-label="变换表达式"
                  />
                </label>
                <label className="bp-pipe-field">
                  <span>过滤条件</span>
                  <input
                    className="w3-c6-xform-input"
                    value={xform.filter}
                    onChange={(e) => setXform((c) => ({ ...c, filter: e.target.value }))}
                    placeholder="可选 · 如 status = 'ok'"
                    aria-label="过滤条件"
                  />
                </label>
                <div className="w3-c6-xform-actions">
                  <button type="button" className="btn" disabled={xformBusy} onClick={() => void saveXformConfig()}>
                    保存配置
                  </button>
                  <button type="button" className="btn-primary" disabled={xformBusy} onClick={() => void runXformTrial()}>
                    试运行
                  </button>
                </div>
                {xformMsg && <p className="w3-c6-xform-msg muted">{xformMsg}</p>}
              </div>
            )}

            {selected === "output" && (
              <>
                <label className="bp-pipe-field">
                  <span>格式</span>
                  <select disabled defaultValue="parquet">
                    <option value="parquet">Parquet</option>
                  </select>
                </label>
                <label className="bp-pipe-field">
                  <span>表格式</span>
                  <select disabled defaultValue="objects">
                    <option value="objects">对象实例（PG）</option>
                  </select>
                </label>
                {/* Phase E-06: 6 种 Write Mode 可选 */}
                <label className="bp-pipe-field">
                  <span>写入模式</span>
                  <select
                    value={writeMode}
                    onChange={(e) => setWriteMode(e.target.value)}
                  >
                    {WRITE_MODES.map((m) => (
                      <option key={m.id} value={m.id}>{m.id} · {m.label}</option>
                    ))}
                  </select>
                </label>
                <p className="muted" style={{ fontSize: "0.7rem", marginTop: 4 }}>
                  管道类型：{PIPE_TYPES.find((t) => t.id === pipeType)?.label} · 当前写入模式：{writeMode}
                </p>
                <div className="bp-pipe-schema">
                  <div className="bp-section-label">Schema</div>
                  {cols.length === 0 ? (
                    <p className="muted">预览后显示列</p>
                  ) : (
                    <table className="bp-pipe-schema-table">
                      <thead>
                        <tr>
                          <th>列</th>
                          <th>类型</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cols.map((c) => (
                          <tr key={c}>
                            <td className="mono">{c}</td>
                            <td className="muted">{inferColumnType(rows, c)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </>
            )}

            <Link to="/data/builds" className="btn-primary bp-pipe-deploy">
              部署并搭建
            </Link>
            {pipe.datasetRid && (
              <Link to={`/data/datasets?rid=${encodeURIComponent(pipe.datasetRid)}`} className="btn-nav bp-pipe-deploy">
                打开数据集 →
              </Link>
            )}

            <button
              type="button"
              className="btn bp-pipe-advanced-toggle"
              onClick={() => setAdvancedOpen((v) => !v)}
            >
              {advancedOpen ? "收起高级" : "高级 · 向量索引"}
            </button>
            {advancedOpen && (
              <p className="muted" style={{ fontSize: "0.75rem" }}>
                向量索引接线见列表旧入口已迁出主舞台；请用 AIP / embed API 或后续专页，避免污染画布层次。
              </p>
            )}
          </aside>
        </div>
          )}
        </>
      )}
    </S2Chrome>
  );
}
