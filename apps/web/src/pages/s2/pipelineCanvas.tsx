/**
 * 186w · Pipeline 画布页 · 对齐 foundry/html/pipeline.html（图1）
 * 层次：顶栏操作 · 中网格 DAG · 底预览 · 右输出属性
 * Phase E-02~E-06：节点拖拽 + 算子工具栏 + 管道类型 + 输出配置 + 预览增强
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiPost } from "../../api/client";
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
  }, [pipelineId]);

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
                {selected === "transform" && "Ingest · 当前管道为源表直写入对象（无自定义 Join 图）"}
                {selected === "output" && `${outLabel}${otHint ? ` · ${otHint}` : ""}`}
              </p>
            </div>

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
    </S2Chrome>
  );
}
