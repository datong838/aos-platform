import { useEffect, useMemo, useRef, useState } from "react";
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

import {
  getLogicSourcePorts,
  logicCanvasDropPosition,
  moveLogicCanvasPosition,
  tryAddLogicEdge,
  type LogicBlockKind,
  type LogicGraphEdge,
  type LogicGraphNode,
} from "./logicCanvasGraph";
import type { LogicNodeRunStatus } from "./logicRunContracts";

const DROP_AREA_ID = "logic-graph-canvas";
const NODE_WIDTH = 180;
const NODE_HEIGHT = 84;
const MIN_STAGE_WIDTH = 1600;
const MIN_STAGE_HEIGHT = 900;

export interface LogicPaletteItem {
  kind: LogicBlockKind;
  label: string;
  title: string;
  description: string;
  icon: string;
  defaultConfig?: Record<string, unknown>;
}

export const DEFAULT_LOGIC_PALETTE: LogicPaletteItem[] = [
  { kind: "input", label: "输入", title: "Input", description: "定义 Logic 输入", icon: "IN" },
  { kind: "create_variable", label: "创建变量", title: "Create Variable", description: "创建中间变量", icon: "VAR" },
  { kind: "get_property", label: "获取属性", title: "Get Property", description: "读取 Ontology 属性", icon: "GET" },
  { kind: "use_llm", label: "使用 LLM", title: "Use LLM", description: "调用大模型能力", icon: "LLM" },
  { kind: "use_tool", label: "使用工具", title: "Use Tool", description: "调用已注册工具", icon: "TOOL" },
  { kind: "transform", label: "数据变换", title: "Transform", description: "执行数据变换", icon: "FX" },
  { kind: "apply_action", label: "应用动作", title: "Apply Action", description: "产生可审计 Action 提议", icon: "ACT" },
  { kind: "execute", label: "执行", title: "Execute", description: "提交执行结果", icon: "RUN" },
  {
    kind: "branch",
    label: "分支",
    title: "Branch",
    description: "按条件选择路径",
    icon: "IF",
    defaultConfig: {
      paths: [
        { id: "path-a", label: "路径 A", condition: "true", default: false },
        { id: "default", label: "默认", condition: "default", default: true },
      ],
    },
  },
  {
    kind: "handoff",
    label: "汇聚",
    title: "Handoff",
    description: "汇聚上游上下文",
    icon: "JOIN",
    defaultConfig: { decision: "", artifacts: [], open_qs: [], handoff_to: "draft_inbox" },
  },
];

export type LogicCanvasDirtyReason =
  | "node_add"
  | "node_move"
  | "node_delete"
  | "edge_add"
  | "edge_delete";

export type LogicCanvasNodeRunState = LogicNodeRunStatus;

const NODE_RUN_STATE_LABELS: Record<LogicCanvasNodeRunState, string> = {
  executed: "已执行",
  skipped: "已跳过",
  failed: "失败",
  canceled: "已取消",
};

export interface LogicGraphCanvasProps {
  nodes: LogicGraphNode[];
  edges: LogicGraphEdge[];
  palette?: LogicPaletteItem[];
  selectedNodeId?: string;
  zoom?: number;
  inspectorCollapsed?: boolean;
  inspector?: React.ReactNode;
  disabled?: boolean;
  nodeRunStates?: ReadonlyMap<string, LogicCanvasNodeRunState>;
  onNodesChange: (nodes: LogicGraphNode[]) => void;
  onEdgesChange: (edges: LogicGraphEdge[]) => void;
  onSelectNode?: (nodeId: string) => void;
  onDirty?: (reason: LogicCanvasDirtyReason) => void;
  onEdgeRejected?: (message: string) => void;
  onZoomChange?: (zoom: number) => void;
  onInspectorCollapsedChange?: (collapsed: boolean) => void;
  createNodeId?: (kind: LogicBlockKind) => string;
  createEdgeId?: () => string;
}

type LinkOrigin = { nodeId: string; sourcePort: string; branchPath: string };

function defaultNodeId(kind: LogicBlockKind): string {
  return `${kind}-${Date.now()}-${Math.random().toString(16).slice(2, 7)}`;
}

function defaultEdgeId(): string {
  return `edge-${Date.now()}-${Math.random().toString(16).slice(2, 7)}`;
}

function PaletteButton({
  item,
  disabled,
  onAdd,
}: {
  item: LogicPaletteItem;
  disabled: boolean;
  onAdd: (item: LogicPaletteItem) => void;
}) {
  const didDrag = useRef(false);
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `logic-palette:${item.kind}`,
    data: { source: "palette", item },
    disabled,
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
      className="bp-logic-canvas-palette-item"
      disabled={disabled}
      title={`${item.title} · ${item.description}`}
      aria-label={`添加 ${item.label}`}
      onClick={() => {
        if (didDrag.current) {
          didDrag.current = false;
          return;
        }
        onAdd(item);
      }}
      {...listeners}
      {...attributes}
    >
      <span className="bp-logic-canvas-palette-icon" aria-hidden>{item.icon}</span>
      <span>{item.label}</span>
      <small>{item.title}</small>
    </button>
  );
}

function DraggableLogicNode({
  node,
  zoom,
  selected,
  linking,
  runState,
  disabled,
  onSelect,
  onStartLink,
  onCompleteLink,
  onDelete,
}: {
  node: LogicGraphNode;
  zoom: number;
  selected: boolean;
  linking: boolean;
  runState?: LogicCanvasNodeRunState;
  disabled: boolean;
  onSelect: () => void;
  onStartLink: (sourcePort: string, branchPath: string) => void;
  onCompleteLink: () => void;
  onDelete: () => void;
}) {
  const ports = useMemo(() => getLogicSourcePorts(node), [node]);
  const runStateLabel = runState ? NODE_RUN_STATE_LABELS[runState] : "";
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `logic-node:${node.id}`,
    data: { source: "canvas", nodeId: node.id },
    disabled,
  });
  return (
    <div
      ref={setNodeRef}
      className={`bp-logic-canvas-node${selected ? " is-selected" : ""}${linking ? " is-linking" : ""}${runState ? ` has-run-state is-run-${runState}` : ""}`}
      style={{
        left: node.position_x,
        top: node.position_y,
        transform: transform ? `translate3d(${transform.x / zoom}px, ${transform.y / zoom}px, 0)` : undefined,
        zIndex: isDragging ? 3 : 1,
        opacity: isDragging ? 0.72 : 1,
      }}
      data-node-id={node.id}
      data-run-state={runState}
      role="group"
      aria-label={runState ? `节点 ${node.id}，运行状态：${runStateLabel}` : `节点 ${node.id}`}
      onClick={onSelect}
    >
      <button
        type="button"
        className="bp-logic-canvas-node-drag"
        aria-label={`拖动 ${node.id}`}
        disabled={disabled}
        {...listeners}
        {...attributes}
      >
        <span className="bp-logic-canvas-node-kind">{node.kind}</span>
        <strong>{node.label}</strong>
      </button>
      {runState && (
        <span
          className={`bp-logic-canvas-run-state is-${runState}`}
          aria-label={`运行状态：${runStateLabel}`}
        >
          {runStateLabel}
        </span>
      )}
      <button
        type="button"
        className="bp-logic-canvas-port bp-logic-canvas-port-in"
        aria-label={`连接到 ${node.id} 的 in 端口`}
        disabled={disabled}
        onClick={(event) => {
          event.stopPropagation();
          onCompleteLink();
        }}
      />
      <div className="bp-logic-canvas-output-ports">
        {ports.map((port) => (
          <button
            key={port.id}
            type="button"
            className="bp-logic-canvas-port bp-logic-canvas-port-out"
            aria-label={`从 ${node.id} 的 ${port.id} 端口建立连接`}
            title={port.label}
            disabled={disabled}
            onClick={(event) => {
              event.stopPropagation();
              onStartLink(port.id, port.branchPath);
            }}
          />
        ))}
      </div>
      <button
        type="button"
        className="bp-logic-canvas-node-delete"
        aria-label={`删除节点 ${node.id}`}
        disabled={disabled}
        onClick={(event) => {
          event.stopPropagation();
          onDelete();
        }}
      >
        ×
      </button>
    </div>
  );
}

function CanvasDropArea({
  canvasRef,
  children,
}: {
  canvasRef: React.MutableRefObject<HTMLDivElement | null>;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: DROP_AREA_ID });
  return (
    <div
      ref={(node) => {
        setNodeRef(node);
        canvasRef.current = node;
      }}
      className={`bp-logic-canvas-drop-area grid-pattern${isOver ? " is-drop-target" : ""}`}
      data-testid="logic-graph-drop-area"
    >
      {children}
    </div>
  );
}

export function LogicGraphCanvas({
  nodes,
  edges,
  palette = DEFAULT_LOGIC_PALETTE,
  selectedNodeId = "",
  zoom = 1,
  inspectorCollapsed = false,
  inspector,
  disabled = false,
  nodeRunStates,
  onNodesChange,
  onEdgesChange,
  onSelectNode,
  onDirty,
  onEdgeRejected,
  onZoomChange,
  onInspectorCollapsedChange,
  createNodeId = defaultNodeId,
  createEdgeId = defaultEdgeId,
}: LogicGraphCanvasProps) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const [linkOrigin, setLinkOrigin] = useState<LinkOrigin | null>(null);
  const [interactionMessage, setInteractionMessage] = useState("");
  const safeZoom = Number.isFinite(zoom) && zoom > 0 ? zoom : 1;
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor),
  );

  const stageWidth = Math.max(MIN_STAGE_WIDTH, ...nodes.map((node) => node.position_x + NODE_WIDTH + 160));
  const stageHeight = Math.max(MIN_STAGE_HEIGHT, ...nodes.map((node) => node.position_y + NODE_HEIGHT + 160));

  function markDirty(reason: LogicCanvasDirtyReason): void {
    setInteractionMessage("");
    onDirty?.(reason);
  }

  function addNode(item: LogicPaletteItem, position?: { x: number; y: number }): void {
    if (disabled) return;
    const canvas = canvasRef.current;
    const fallbackIndex = nodes.length;
    const fallback = {
      x: Math.max(0, ((canvas?.scrollLeft || 0) + 80) / safeZoom + (fallbackIndex % 3) * 200),
      y: Math.max(0, ((canvas?.scrollTop || 0) + 80) / safeZoom + Math.floor(fallbackIndex / 3) * 120),
    };
    let id = createNodeId(item.kind);
    if (nodes.some((node) => node.id === id)) id = `${id}-${nodes.length + 1}`;
    onNodesChange([
      ...nodes,
      {
        id,
        kind: item.kind,
        label: item.label,
        position_x: position?.x ?? fallback.x,
        position_y: position?.y ?? fallback.y,
        config: structuredClone(item.defaultConfig || {}),
      },
    ]);
    onSelectNode?.(id);
    markDirty("node_add");
  }

  function handleDragEnd(event: DragEndEvent): void {
    if (disabled) return;
    const data = event.active.data.current as
      | { source?: "palette"; item?: LogicPaletteItem }
      | { source?: "canvas"; nodeId?: string }
      | undefined;
    if (data?.source === "canvas" && data.nodeId) {
      if (!event.delta.x && !event.delta.y) return;
      onNodesChange(nodes.map((node) => {
        if (node.id !== data.nodeId) return node;
        const position = moveLogicCanvasPosition(
          { x: node.position_x, y: node.position_y },
          event.delta,
          safeZoom,
        );
        return { ...node, position_x: position.x, position_y: position.y };
      }));
      markDirty("node_move");
      return;
    }
    if (data?.source !== "palette" || !data.item || event.over?.id !== DROP_AREA_ID) return;
    const canvas = canvasRef.current;
    const translated = event.active.rect.current.translated;
    if (!canvas || !translated) return;
    const canvasRect = canvas.getBoundingClientRect();
    addNode(data.item, logicCanvasDropPosition({
      translatedRect: translated,
      canvasRect,
      scroll: { left: canvas.scrollLeft, top: canvas.scrollTop },
      zoom: safeZoom,
      nodeSize: { width: NODE_WIDTH, height: NODE_HEIGHT },
    }));
  }

  function rejectEdge(message: string): void {
    setInteractionMessage(message);
    onEdgeRejected?.(message);
  }

  function completeLink(targetNodeId: string): void {
    if (!linkOrigin || disabled) return;
    const candidate: LogicGraphEdge = {
      id: createEdgeId(),
      source_node_id: linkOrigin.nodeId,
      source_port: linkOrigin.sourcePort,
      target_node_id: targetNodeId,
      target_port: "in",
      branch_path: linkOrigin.branchPath,
      order: edges.length,
    };
    const result = tryAddLogicEdge(nodes, edges, candidate);
    setLinkOrigin(null);
    if (!result.ok) {
      rejectEdge(result.reason);
      return;
    }
    onEdgesChange(result.edges);
    markDirty("edge_add");
  }

  function deleteNode(nodeId: string): void {
    if (disabled) return;
    const nextEdges = edges.filter((edge) => edge.source_node_id !== nodeId && edge.target_node_id !== nodeId);
    onNodesChange(nodes.filter((node) => node.id !== nodeId));
    if (nextEdges.length !== edges.length) onEdgesChange(nextEdges);
    if (linkOrigin?.nodeId === nodeId) setLinkOrigin(null);
    markDirty("node_delete");
  }

  function deleteEdge(edgeId: string): void {
    if (disabled) return;
    onEdgesChange(edges.filter((edge) => edge.id !== edgeId));
    markDirty("edge_delete");
  }

  const nodeById = new Map(nodes.map((node) => [node.id, node]));

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <section
        className={`bp-logic-canvas-shell${inspectorCollapsed ? " is-inspector-collapsed" : ""}${inspector ? "" : " without-inspector"}`}
      >
        <div className="bp-logic-canvas-toolbar">
          <button type="button" className="btn" aria-label="缩小画布" onClick={() => onZoomChange?.(Math.max(0.5, Number((safeZoom - 0.1).toFixed(1))))}>−</button>
          <span aria-label="画布缩放比例">{Math.round(safeZoom * 100)}%</span>
          <button type="button" className="btn" aria-label="放大画布" onClick={() => onZoomChange?.(Math.min(2, Number((safeZoom + 0.1).toFixed(1))))}>+</button>
          <button type="button" className="btn" aria-label="重置画布缩放" onClick={() => onZoomChange?.(1)}>1:1</button>
          <span className="bp-logic-canvas-stats">节点 {nodes.length} · 连接 {edges.length}</span>
          {linkOrigin && <span className="bp-logic-canvas-linking">连接模式 · 请选择目标端口</span>}
          {interactionMessage && <span className="bp-logic-canvas-error" role="alert">{interactionMessage}</span>}
          <span className="bp-logic-canvas-toolbar-spacer" />
          <button
            type="button"
            className="btn"
            aria-label={inspectorCollapsed ? "展开属性面板" : "折叠属性面板"}
            onClick={() => onInspectorCollapsedChange?.(!inspectorCollapsed)}
          >
            {inspectorCollapsed ? "展开属性" : "收起属性"}
          </button>
        </div>

        <aside className="bp-logic-canvas-palette" aria-label="Logic Block 组件库">
          <h3>Block 组件库</h3>
          {palette.map((item) => (
            <PaletteButton key={item.kind} item={item} disabled={disabled} onAdd={addNode} />
          ))}
        </aside>

        <CanvasDropArea canvasRef={canvasRef}>
          <div
            className="bp-logic-canvas-stage-viewport"
            style={{ width: stageWidth * safeZoom, height: stageHeight * safeZoom }}
          >
            <div
              className="bp-logic-canvas-stage"
              style={{ width: stageWidth, height: stageHeight, transform: `scale(${safeZoom})` }}
            >
              <svg className="bp-logic-canvas-edges" width={stageWidth} height={stageHeight} aria-hidden>
                {edges.map((edge) => {
                  const source = nodeById.get(edge.source_node_id);
                  const target = nodeById.get(edge.target_node_id);
                  if (!source || !target) return null;
                  const ports = getLogicSourcePorts(source);
                  const portIndex = Math.max(0, ports.findIndex((port) => port.id === edge.source_port));
                  const startX = source.position_x + NODE_WIDTH;
                  const startY = source.position_y + 34 + portIndex * 16;
                  const endX = target.position_x;
                  const endY = target.position_y + NODE_HEIGHT / 2;
                  const bend = Math.max(40, Math.abs(endX - startX) / 2);
                  return (
                    <path
                      key={edge.id}
                      className="bp-logic-canvas-edge"
                      d={`M ${startX} ${startY} C ${startX + bend} ${startY}, ${endX - bend} ${endY}, ${endX} ${endY}`}
                    />
                  );
                })}
              </svg>

              {edges.map((edge) => {
                const source = nodeById.get(edge.source_node_id);
                const target = nodeById.get(edge.target_node_id);
                if (!source || !target) return null;
                return (
                  <button
                    key={`delete-${edge.id}`}
                    type="button"
                    className="bp-logic-canvas-edge-delete"
                    aria-label={`删除连接 ${edge.id}`}
                    title={`${edge.source_node_id} → ${edge.target_node_id}`}
                    disabled={disabled}
                    style={{
                      left: (source.position_x + NODE_WIDTH + target.position_x) / 2,
                      top: (source.position_y + target.position_y + NODE_HEIGHT) / 2,
                    }}
                    onClick={() => deleteEdge(edge.id)}
                  >
                    ×
                  </button>
                );
              })}

              {nodes.map((node) => (
                <DraggableLogicNode
                  key={node.id}
                  node={node}
                  zoom={safeZoom}
                  selected={selectedNodeId === node.id}
                  linking={linkOrigin?.nodeId === node.id}
                  runState={nodeRunStates?.get(node.id)}
                  disabled={disabled}
                  onSelect={() => onSelectNode?.(node.id)}
                  onStartLink={(sourcePort, branchPath) => {
                    setLinkOrigin({ nodeId: node.id, sourcePort, branchPath });
                    setInteractionMessage("");
                  }}
                  onCompleteLink={() => completeLink(node.id)}
                  onDelete={() => deleteNode(node.id)}
                />
              ))}
            </div>
          </div>
        </CanvasDropArea>

        {inspector && <aside className="bp-logic-canvas-inspector">{inspector}</aside>}
      </section>
    </DndContext>
  );
}
