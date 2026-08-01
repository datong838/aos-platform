/**
 * 186w · Pipeline 画布页 · 对齐 foundry/html/pipeline.html（图1）
 * 层次：顶栏操作 · 中网格 DAG · 底预览 · 右输出属性
 * Phase E-02~E-06：节点拖拽 + 算子工具栏 + 管道类型 + 输出配置 + 预览增强
 * W3-C6：视图 Tab（编辑/历史）+ 变换节点配置/试运行 · 优先接 phase5 pipeline API
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
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
  status?: string;
};

export type GraphPayload = {
  pipeline_id?: string;
  nodes?: GraphNode[];
  edges?: { id?: string; source_node_id?: string; target_node_id?: string; label?: string }[];
  demo?: boolean;
  persisted?: boolean;
  pipeline_type?: string;
  write_mode?: string;
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
export const OPERATORS: { group: string; items: { id: string; label: string; kind: NodeType }[] }[] = [
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

export const PIPE_TYPES = [
  { id: "batch", label: "批量" },
  { id: "incremental", label: "增量" },
  { id: "streaming", label: "流式" },
] as const;

export const WRITE_MODES = [
  { id: "SNAPSHOT", label: "快照" },
  { id: "APPEND", label: "追加" },
  { id: "MERGE", label: "合并" },
  { id: "UPDATE", label: "更新" },
  { id: "DELETE", label: "删除" },
  { id: "UPSERT", label: "插入或更新" },
] as const;

export function cellText(v: unknown): string {
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
export function inferColumnType(rows: Record<string, unknown>[], col: string): string {
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

type Operator = (typeof OPERATORS)[number]["items"][number];
type CanvasConnection = { id: string; from: string; to: string; label?: string };

function DraggableOperator({ op, onAdd }: { op: Operator; onAdd: (op: Operator) => void }) {
  const didDrag = useRef(false);
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `operator:${op.id}`,
    data: { source: "palette", op },
  });
  useEffect(() => {
    if (isDragging) {
      didDrag.current = true;
      return;
    }
    if (didDrag.current) {
      const timer = window.setTimeout(() => { didDrag.current = false; }, 0);
      return () => window.clearTimeout(timer);
    }
  }, [isDragging]);
  return (
    <button
      ref={setNodeRef}
      type="button"
      className="btn-nav"
      style={{ fontSize: "0.7rem", padding: "2px 8px", cursor: "grab", opacity: isDragging ? 0.5 : 1 }}
      title={`拖拽到画布添加「${op.label}」`}
      onClick={() => {
        if (didDrag.current) {
          didDrag.current = false;
          return;
        }
        onAdd(op);
      }}
      {...listeners}
      {...attributes}
    >
      {op.label}
    </button>
  );
}

function DraggableCanvasNode({
  nodeId,
  x,
  y,
  zoom,
  className,
  title,
  onClick,
  onContextMenu,
  onDoubleClick,
  children,
}: {
  nodeId: string;
  x: number;
  y: number;
  zoom: number;
  className: string;
  title?: string;
  onClick: () => void;
  onContextMenu: (event: React.MouseEvent) => void;
  onDoubleClick?: () => void;
  children: React.ReactNode;
}) {
  const didDrag = useRef(false);
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `node:${nodeId}`,
    data: { source: "canvas", nodeId },
  });
  useEffect(() => {
    if (isDragging) {
      didDrag.current = true;
      return;
    }
    if (didDrag.current) {
      const timer = window.setTimeout(() => { didDrag.current = false; }, 0);
      return () => window.clearTimeout(timer);
    }
  }, [isDragging]);
  return (
    <button
      ref={setNodeRef}
      type="button"
      className={className}
      onClick={() => {
        if (didDrag.current) {
          didDrag.current = false;
          return;
        }
        onClick();
      }}
      onContextMenu={onContextMenu}
      onDoubleClick={onDoubleClick}
      title={title}
      style={{
        position: "absolute",
        left: x,
        top: y,
        cursor: isDragging ? "grabbing" : "grab",
        opacity: isDragging ? 0.75 : 1,
        zIndex: isDragging ? 3 : 1,
        transform: transform ? `translate3d(${transform.x / zoom}px, ${transform.y / zoom}px, 0)` : undefined,
      }}
      {...listeners}
      {...attributes}
    >
      {children}
    </button>
  );
}

function CanvasDropArea({
  canvasRef,
  className,
  style,
  onClick,
  children,
}: {
  canvasRef: React.MutableRefObject<HTMLDivElement | null>;
  className: string;
  style: React.CSSProperties;
  onClick: () => void;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: "pipeline-canvas" });
  return (
    <div
      ref={(node) => {
        setNodeRef(node);
        canvasRef.current = node;
      }}
      className={`${className}${isOver ? " is-drop-target" : ""}`}
      style={style}
      onClick={onClick}
    >
      {children}
    </div>
  );
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
  const [inspectorCollapsed, setInspectorCollapsed] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor),
  );

  // Phase E-02: 节点拖拽位置
  const [nodePositions, setNodePositions] = useState<Record<string, { x: number; y: number }>>({
    input: { x: 60, y: 60 },
    transform: { x: 300, y: 60 },
    output: { x: 540, y: 60 },
  });
  const [baseNodeIds, setBaseNodeIds] = useState<Record<NodeType, string>>({
    input: "input",
    transform: "transform",
    output: "output",
  });

  // Phase E-05: 管道类型
  const [pipeType, setPipeType] = useState<string>("batch");

  // Phase E-06: 写入模式
  const [writeMode, setWriteMode] = useState<string>("SNAPSHOT");

  // Phase E-03: 算子拖入画布
  const [extraNodes, setExtraNodes] = useState<{ id: string; label: string; kind: NodeType; x: number; y: number }[]>([]);

  // Phase 7: 画布缩放 + 右键菜单 + 连接线管理
  const [zoom, setZoom] = useState(1);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; nodeId: string } | null>(null);
  const [connections, setConnections] = useState<CanvasConnection[]>([]);
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

  function markDirty() {
    setDirty(true);
    setSaveMsg(null);
  }

  function addOperator(op: Operator, position?: { x: number; y: number }) {
    const suffix = `${Date.now()}-${Math.random().toString(16).slice(2, 7)}`;
    setExtraNodes((prev) => [
      ...prev,
      {
        id: `${op.id}-${suffix}`,
        label: op.label,
        kind: op.kind,
        x: position?.x ?? 120 + (prev.length % 3) * 190,
        y: position?.y ?? 170 + Math.floor(prev.length / 3) * 90,
      },
    ]);
    markDirty();
  }

  function handleDragEnd(event: DragEndEvent) {
    const data = event.active.data.current as
      | { source?: "palette"; op?: Operator }
      | { source?: "canvas"; nodeId?: string }
      | undefined;
    if (data?.source === "canvas" && data.nodeId) {
      const dx = event.delta.x / zoom;
      const dy = event.delta.y / zoom;
      if (!dx && !dy) return;
      if (data.nodeId === "input" || data.nodeId === "transform" || data.nodeId === "output") {
        setNodePositions((prev) => ({
          ...prev,
          [data.nodeId!]: {
            x: Math.max(0, prev[data.nodeId!].x + dx),
            y: Math.max(0, prev[data.nodeId!].y + dy),
          },
        }));
      } else {
        setExtraNodes((prev) => prev.map((node) => (
          node.id === data.nodeId
            ? { ...node, x: Math.max(0, node.x + dx), y: Math.max(0, node.y + dy) }
            : node
        )));
      }
      markDirty();
      return;
    }

    if (data?.source !== "palette" || !data.op || event.over?.id !== "pipeline-canvas") return;
    const canvas = canvasRef.current;
    const translated = event.active.rect.current.translated;
    if (!canvas || !translated) return;
    const canvasRect = canvas.getBoundingClientRect();
    const x = Math.max(0, (translated.left + translated.width / 2 - canvasRect.left + canvas.scrollLeft) / zoom - 80);
    const y = Math.max(0, (translated.top + translated.height / 2 - canvasRect.top + canvas.scrollTop) / zoom - 30);
    addOperator(data.op, { x, y });
  }

  function removeExtraNode(id: string) {
    setExtraNodes((prev) => prev.filter((n) => n.id !== id));
    setConnections((prev) => prev.filter((c) => c.from !== id && c.to !== id));
    markDirty();
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
        markDirty();
        return [...prev, { id: `edge-${Date.now()}-${prev.length}`, from: linkingFrom, to: targetNodeId }];
      });
    }
    setLinkingFrom(null);
  }

  function removeConnection(from: string, to: string) {
    setConnections((prev) => prev.filter((c) => !(c.from === from && c.to === to)));
    setContextMenu(null);
    markDirty();
  }

  // Phase 7: 清空画布
  function clearCanvas() {
    setExtraNodes([]);
    setConnections([]);
    setContextMenu(null);
    markDirty();
  }

  useEffect(() => {
    setSelected("output");
    setPreview(null);
    setPreviewErr(null);
    setViewTab("edit");
    setXformMsg(null);
    setSaveMsg(null);
    setDirty(false);
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
        const graphNodes = g.nodes || [];
        const sourceNode = graphNodes.find((node) => ["source", "input"].includes((node.node_type || "").toLowerCase()));
        const transformGraphNode = pickTransformNode(g);
        const outputNode = graphNodes.find((node) => ["sink", "output"].includes((node.node_type || "").toLowerCase()));
        const ids: Record<NodeType, string> = {
          input: sourceNode?.id || `canvas-input-${pipelineId}`,
          transform: transformGraphNode?.id || `canvas-transform-${pipelineId}`,
          output: outputNode?.id || `canvas-output-${pipelineId}`,
        };
        setBaseNodeIds(ids);
        setNodePositions({
          input: { x: sourceNode?.position_x ?? 60, y: sourceNode?.position_y ?? 60 },
          transform: { x: transformGraphNode?.position_x ?? 300, y: transformGraphNode?.position_y ?? 60 },
          output: { x: outputNode?.position_x ?? 540, y: outputNode?.position_y ?? 60 },
        });
        const baseIds = new Set(Object.values(ids));
        setExtraNodes(graphNodes.filter((node) => !baseIds.has(node.id)).map((node) => {
          const nodeType = (node.node_type || "transform").toLowerCase();
          const kind: NodeType = ["source", "input"].includes(nodeType)
            ? "input"
            : ["sink", "output"].includes(nodeType) ? "output" : "transform";
          return {
            id: node.id,
            label: node.name || node.id,
            kind,
            x: node.position_x ?? 120,
            y: node.position_y ?? 160,
          };
        }));
        const keyByNodeId = new Map<string, string>([
          [ids.input, "input"],
          [ids.transform, "transform"],
          [ids.output, "output"],
        ]);
        setConnections((g.edges || []).flatMap((edge, index) => {
          if (!edge.source_node_id || !edge.target_node_id) return [];
          return [{
            id: edge.id || `edge-loaded-${index}`,
            from: keyByNodeId.get(edge.source_node_id) || edge.source_node_id,
            to: keyByNodeId.get(edge.target_node_id) || edge.target_node_id,
            label: edge.label,
          }];
        }));
        const type = (g.pipeline_type || "").toLowerCase();
        setPipeType(type === "streaming" ? "streaming" : type === "etl" || type === "elt" ? "incremental" : "batch");
        setWriteMode(g.write_mode || "SNAPSHOT");
        setDirty(false);
        const xf = pickTransformNode(g);
        const cfg = xf?.config;
        if (cfg && typeof cfg.expression === "string") {
          setXform({
            expression: String(cfg.expression),
            filter: String(cfg.filter || ""),
          });
        }
      } catch {
        if (!cancelled) {
          setGraph(null);
          setSaveMsg("画布加载失败，当前内容不可保存；请刷新后重试");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pipelineId]);

  async function saveCanvas() {
    const idForKey = (key: string) => baseNodeIds[key as NodeType] || key;
    const originalById = new Map((graph?.nodes || []).map((node) => [node.id, node]));
    const baseNodes: { key: NodeType; name: string; nodeType: string }[] = [
      { key: "input", name: pipe?.sourceId || "source", nodeType: "source" },
      { key: "transform", name: "Ingest", nodeType: "transform" },
      { key: "output", name: String(outLabel || "output"), nodeType: "sink" },
    ];
    const nodes = [
      ...baseNodes.map(({ key, name, nodeType }) => {
        const id = baseNodeIds[key];
        const original = originalById.get(id);
        return {
          id,
          name: original?.name || name,
          node_type: original?.node_type || nodeType,
          position_x: nodePositions[key].x,
          position_y: nodePositions[key].y,
          config: original?.config || (key === "transform" ? xform : {}),
          status: original?.status || "idle",
        };
      }),
      ...extraNodes.map((node) => {
        const original = originalById.get(node.id);
        return {
          id: node.id,
          name: node.label,
          node_type: original?.node_type || (node.kind === "input" ? "source" : node.kind === "output" ? "sink" : "transform"),
          position_x: node.x,
          position_y: node.y,
          config: original?.config || {},
          status: original?.status || "idle",
        };
      }),
    ];
    const edges = connections.map((connection) => ({
      id: connection.id,
      source_node_id: idForKey(connection.from),
      target_node_id: idForKey(connection.to),
      label: connection.label || "",
    }));

    setSaveBusy(true);
    setSaveMsg(null);
    try {
      const saved = await apiPut<GraphPayload>(`/v1/pipelines/${encodeURIComponent(pipelineId)}/graph`, {
        nodes,
        edges,
        pipeline_type: pipeType === "streaming" ? "Streaming" : pipeType === "incremental" ? "ETL" : "Batch",
        write_mode: writeMode,
        name: title,
      });
      if (!saved.persisted || saved.demo) throw new Error("服务端未确认持久化");
      setGraph(saved);
      setDirty(false);
      setSaveMsg(`已保存 · ${saved.nodes?.length || 0} 个节点 · ${saved.edges?.length || 0} 条连接`);
    } catch (e) {
      setSaveMsg(`保存失败 · ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSaveBusy(false);
    }
  }

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
      if (res.demo) throw new Error("演示节点不支持持久化，请先保存画布");
      saveLocalXform(pipelineId, xform);
      setGraph((current) => current ? {
        ...current,
        nodes: (current.nodes || []).map((node) => node.id === nodeId ? { ...node, config: xform } : node),
      } : current);
      setXformMsg("已保存配置 · API");
    } catch (e) {
      setXformMsg(`保存失败 · ${e instanceof Error ? e.message : String(e)}`);
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
              onClick={() => { setPipeType(t.id); markDirty(); }}
              style={{ fontSize: "0.75rem", padding: "2px 8px" }}
            >
              {t.label}
            </button>
          ))}
        </div>
        <button type="button" className="btn" disabled={saveBusy || !pipe || !graph} onClick={() => void saveCanvas()}>
          {saveBusy ? "保存中…" : dirty ? "保存 *" : "保存"}
        </button>
        {saveMsg && <span className={saveMsg.startsWith("保存失败") ? "error" : "muted"}>{saveMsg}</span>}
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

      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      {/* Phase E-03: 算子工具栏 */}
      <div className="bp-pipe-operator-bar" style={{ display: "flex", gap: 12, padding: "6px 12px", overflowX: "auto", borderBottom: "1px solid var(--aos-border, #2a3540)" }}>
        {OPERATORS.map((group) => (
          <div key={group.group} style={{ display: "flex", gap: 4, alignItems: "center", flexShrink: 0 }}>
            <span className="muted" style={{ fontSize: "0.7rem", marginRight: 4 }}>{group.group}</span>
            {group.items.map((op) => (
              <DraggableOperator key={op.id} op={op} onAdd={addOperator} />
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
        <div className={`bp-pipe-canvas-shell${inspectorCollapsed ? " is-inspector-collapsed" : ""}`}>
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
                节点 {3 + extraNodes.length} · 连接 {connections.length} · 算子组 {OPERATORS.length}
              </span>
            )}
            <div style={{ flex: 1 }} />
            {linkingFrom && (
              <span style={{ fontSize: "0.7rem", color: "var(--aos-accent, #3182ce)" }}>
                连接模式 · 点击目标节点完成连接
              </span>
            )}
            <button
              type="button"
              className="btn"
              onClick={() => setInspectorCollapsed((value) => !value)}
              style={{ fontSize: "0.75rem", padding: "2px 8px" }}
            >
              {inspectorCollapsed ? "展开属性" : "收起属性"}
            </button>
            <button type="button" className="btn" onClick={clearCanvas} style={{ fontSize: "0.75rem", padding: "2px 8px" }} title="清空额外节点">清空</button>
          </div>

          <div className="bp-pipe-canvas-main">
            <CanvasDropArea
              canvasRef={canvasRef}
              className="grid-pattern bp-pipe-dag"
              onClick={closeContextMenu}
              style={{ position: "relative", minHeight: 200, transform: `scale(${zoom})`, transformOrigin: "top left", transition: "transform 0.15s ease" }}
            >
              <div className="bp-pipe-nodes" style={{ position: "relative" }}>
                <DraggableCanvasNode
                  nodeId="input"
                  x={nodePositions.input.x}
                  y={nodePositions.input.y}
                  zoom={zoom}
                  className={`pipeline-node bp-pipe-node bp-pipe-node-input${selected === "input" ? " is-selected" : ""}${linkingFrom === "input" ? " is-linking" : ""}`}
                  onClick={() => {
                    if (linkingFrom) { completeLink("input"); }
                    else { setSelected("input"); }
                  }}
                  onContextMenu={(e) => handleContextMenu(e, "input")}
                >
                  <div className="bp-pipe-node-head">
                    <span className="bp-pipe-node-icon bp-pipe-node-icon-amber" />
                    <span className="bp-pipe-node-kind bp-pipe-kind-amber">输入</span>
                  </div>
                  <div className="bp-pipe-node-title">{pipe.sourceId || "source"}</div>
                  <div className="bp-pipe-node-sub">Source</div>
                </DraggableCanvasNode>

                <DraggableCanvasNode
                  nodeId="transform"
                  x={nodePositions.transform.x}
                  y={nodePositions.transform.y}
                  zoom={zoom}
                  className={`pipeline-node bp-pipe-node bp-pipe-node-xform${selected === "transform" ? " is-selected" : ""}${linkingFrom === "transform" ? " is-linking" : ""}`}
                  onClick={() => {
                    if (linkingFrom) { completeLink("transform"); }
                    else { setSelected("transform"); }
                  }}
                  onContextMenu={(e) => handleContextMenu(e, "transform")}
                >
                  <div className="bp-pipe-node-head">
                    <span className="bp-pipe-node-icon bp-pipe-node-icon-cyan" />
                    <span className="bp-pipe-node-kind bp-pipe-kind-cyan">变换</span>
                  </div>
                  <div className="bp-pipe-node-title">Ingest</div>
                  <div className="bp-pipe-node-sub">表 → 对象实例</div>
                </DraggableCanvasNode>

                <DraggableCanvasNode
                  nodeId="output"
                  x={nodePositions.output.x}
                  y={nodePositions.output.y}
                  zoom={zoom}
                  className={`pipeline-node bp-pipe-node bp-pipe-node-out${selected === "output" ? " is-selected" : ""}${linkingFrom === "output" ? " is-linking" : ""}`}
                  onClick={() => {
                    if (linkingFrom) { completeLink("output"); }
                    else { setSelected("output"); }
                  }}
                  onContextMenu={(e) => handleContextMenu(e, "output")}
                >
                  <div className="bp-pipe-node-head">
                    <span className="bp-pipe-node-icon bp-pipe-node-icon-emerald" />
                    <span className="bp-pipe-node-kind bp-pipe-kind-emerald">输出</span>
                  </div>
                  <div className="bp-pipe-node-title">{outLabel}</div>
                  <div className="bp-pipe-node-sub">{pipe.datasetRid || "dataset"}</div>
                </DraggableCanvasNode>

                {/* Phase E-03: 拖入的额外算子节点 */}
                {extraNodes.map((n) => (
                  <DraggableCanvasNode
                    key={n.id}
                    nodeId={n.id}
                    x={n.x}
                    y={n.y}
                    zoom={zoom}
                    className={`pipeline-node bp-pipe-node bp-pipe-node-${n.kind === "input" ? "input" : n.kind === "transform" ? "xform" : "out"}${linkingFrom === n.id ? " is-linking" : ""}`}
                    onClick={() => {
                      if (linkingFrom) { completeLink(n.id); }
                    }}
                    onContextMenu={(e) => handleContextMenu(e, n.id)}
                    onDoubleClick={() => removeExtraNode(n.id)}
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
                  </DraggableCanvasNode>
                ))}
              </div>
              {/* Phase 7: 额外连接线渲染 */}
              {connections.length > 0 && (
                <svg className="bp-pipe-flow-svg" width="100%" height="100%" aria-hidden style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none", zIndex: 0 }}>
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
                      <path key={c.id || i} className="flow-line flow-line-active" d={`M ${from.x + 100} ${from.y + 30} C ${from.x + 140} ${from.y + 30}, ${to.x - 40} ${to.y + 30}, ${to.x} ${to.y + 30}`} />
                    );
                  })}
                </svg>
              )}
            </CanvasDropArea>

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
            <button
              type="button"
              className="btn bp-pipe-inspector-collapse"
              onClick={() => setInspectorCollapsed((value) => !value)}
              aria-label={inspectorCollapsed ? "展开属性面板" : "折叠属性面板"}
              title={inspectorCollapsed ? "展开属性面板" : "折叠属性面板"}
            >
              {inspectorCollapsed ? "‹" : "›"}
            </button>
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
                    onChange={(e) => { setWriteMode(e.target.value); markDirty(); }}
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
      </DndContext>
    </S2Chrome>
  );
}
