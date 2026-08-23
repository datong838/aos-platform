import { useEffect, useId, useMemo, useRef, useState } from "react";
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
  MAX_LOGIC_CANVAS_COORDINATE,
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
  { kind: "input", label: "输入", title: "业务输入", description: "定义业务逻辑输入", icon: "入" },
  { kind: "create_variable", label: "创建变量", title: "创建变量", description: "创建中间变量", icon: "变" },
  { kind: "get_property", label: "获取属性", title: "获取属性", description: "读取本体属性", icon: "取" },
  { kind: "use_llm", label: "使用大模型", title: "使用大模型", description: "调用大模型能力", icon: "模" },
  { kind: "use_tool", label: "使用工具", title: "使用工具", description: "调用已注册工具", icon: "工" },
  { kind: "transform", label: "数据变换", title: "数据变换", description: "执行数据变换", icon: "换" },
  { kind: "apply_action", label: "应用动作", title: "应用动作", description: "产生可审计的动作提议", icon: "动" },
  { kind: "execute", label: "执行", title: "执行结果", description: "提交执行结果", icon: "执" },
  {
    kind: "branch",
    label: "分支",
    title: "条件分支",
    description: "按条件选择路径",
    icon: "支",
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
    title: "上下文交接",
    description: "汇聚上游上下文",
    icon: "汇",
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
type LinkPreview = LinkOrigin & {
  pointerId: number;
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
  moved: boolean;
};

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
      <span>{item.title}</span>
      <small>{item.description}</small>
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
  onPointerLinkStart,
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
  onPointerLinkStart: (
    sourcePort: string,
    branchPath: string,
    portIndex: number,
    event: React.PointerEvent<HTMLButtonElement>,
  ) => void;
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
        data-logic-input-node-id={node.id}
        disabled={disabled}
        onClick={(event) => {
          event.stopPropagation();
          onCompleteLink();
        }}
      />
      <div className="bp-logic-canvas-output-ports">
        {ports.map((port, portIndex) => (
          <button
            key={port.id}
            type="button"
            className="bp-logic-canvas-port bp-logic-canvas-port-out"
            aria-label={`从 ${node.id} 的 ${port.id} 端口建立连接`}
            title={port.label}
            disabled={disabled}
            onPointerDown={(event) => {
              event.stopPropagation();
              onPointerLinkStart(port.id, port.branchPath, portIndex, event);
            }}
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
  const [linkPreview, setLinkPreview] = useState<LinkPreview | null>(null);
  const linkDragRef = useRef<LinkPreview | null>(null);
  const suppressLinkClickRef = useRef(false);
  const [interactionMessage, setInteractionMessage] = useState("");
  const arrowMarkerId = `logic-arrow-${useId().replace(/:/g, "")}`;
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

  function pointerCanvasPosition(clientX: number, clientY: number): { x: number; y: number } | null {
    const canvas = canvasRef.current;
    if (!canvas || !Number.isFinite(clientX) || !Number.isFinite(clientY)) return null;
    const rect = canvas.getBoundingClientRect();
    return {
      x: Math.min(MAX_LOGIC_CANVAS_COORDINATE, Math.max(0, (clientX - rect.left + canvas.scrollLeft) / safeZoom)),
      y: Math.min(MAX_LOGIC_CANVAS_COORDINATE, Math.max(0, (clientY - rect.top + canvas.scrollTop) / safeZoom)),
    };
  }

  function startPointerLink(
    node: LogicGraphNode,
    sourcePort: string,
    branchPath: string,
    portIndex: number,
    event: React.PointerEvent<HTMLButtonElement>,
  ): void {
    if (disabled || event.button !== 0) return;
    const pointerId = Number.isInteger(event.pointerId) ? event.pointerId : 1;
    const pointer = pointerCanvasPosition(event.clientX, event.clientY);
    const startX = node.position_x + NODE_WIDTH;
    const startY = node.position_y + 34 + portIndex * 16;
    const preview: LinkPreview = {
      nodeId: node.id,
      sourcePort,
      branchPath,
      pointerId,
      startX,
      startY,
      currentX: pointer?.x ?? startX,
      currentY: pointer?.y ?? startY,
      moved: false,
    };
    linkDragRef.current = preview;
    setLinkPreview(preview);
    event.currentTarget.setPointerCapture?.(pointerId);
  }

  function movePointerLink(event: React.PointerEvent<HTMLElement>): void {
    const active = linkDragRef.current;
    const pointerId = Number.isInteger(event.pointerId) ? event.pointerId : 1;
    if (!active || active.pointerId !== pointerId) return;
    const pointer = pointerCanvasPosition(event.clientX, event.clientY);
    if (!pointer) return;
    const moved = active.moved || Math.hypot(pointer.x - active.startX, pointer.y - active.startY) >= 4;
    const next = { ...active, currentX: pointer.x, currentY: pointer.y, moved };
    linkDragRef.current = next;
    setLinkPreview(next);
  }

  function clearPointerLink(event: React.PointerEvent<HTMLElement>): LinkPreview | null {
    const active = linkDragRef.current;
    const pointerId = Number.isInteger(event.pointerId) ? event.pointerId : 1;
    if (!active || active.pointerId !== pointerId) return null;
    if (event.currentTarget.hasPointerCapture?.(pointerId)) {
      event.currentTarget.releasePointerCapture(pointerId);
    }
    linkDragRef.current = null;
    setLinkPreview(null);
    return active;
  }

  function endPointerLink(event: React.PointerEvent<HTMLElement>): void {
    const active = clearPointerLink(event);
    if (!active?.moved) return;
    suppressLinkClickRef.current = true;
    window.setTimeout(() => { suppressLinkClickRef.current = false; }, 0);
    const target = document.elementFromPoint(event.clientX, event.clientY)
      ?.closest<HTMLElement>("[data-logic-input-node-id]");
    const targetNodeId = target?.dataset.logicInputNodeId;
    if (!targetNodeId) {
      setInteractionMessage("连接已取消：请拖到目标输入端口");
      return;
    }
    completeLink(targetNodeId, active);
  }

  function cancelPointerLink(event: React.PointerEvent<HTMLElement>): void {
    const active = clearPointerLink(event);
    if (active?.moved) setInteractionMessage("连接已取消");
  }

  function clickSourcePort(sourcePort: string, branchPath: string, nodeId: string): void {
    if (suppressLinkClickRef.current) {
      suppressLinkClickRef.current = false;
      return;
    }
    setLinkOrigin({ nodeId, sourcePort, branchPath });
    setInteractionMessage("");
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

  function completeLink(targetNodeId: string, pointerOrigin?: LinkOrigin): void {
    const activeOrigin = pointerOrigin ?? linkOrigin;
    if (!activeOrigin || disabled) return;
    const candidate: LogicGraphEdge = {
      id: createEdgeId(),
      source_node_id: activeOrigin.nodeId,
      source_port: activeOrigin.sourcePort,
      target_node_id: targetNodeId,
      target_port: "in",
      branch_path: activeOrigin.branchPath,
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
        className={`bp-logic-canvas-shell${inspectorCollapsed ? " is-inspector-collapsed" : ""}${inspector ? "" : " without-inspector"}${linkPreview?.moved ? " is-link-dragging" : ""}`}
      >
        <div className="bp-logic-canvas-toolbar">
          <button type="button" className="btn" aria-label="缩小画布" onClick={() => onZoomChange?.(Math.max(0.5, Number((safeZoom - 0.1).toFixed(1))))}>−</button>
          <span aria-label="画布缩放比例">{Math.round(safeZoom * 100)}%</span>
          <button type="button" className="btn" aria-label="放大画布" onClick={() => onZoomChange?.(Math.min(2, Number((safeZoom + 0.1).toFixed(1))))}>+</button>
          <button type="button" className="btn" aria-label="重置画布缩放" onClick={() => onZoomChange?.(1)}>1:1</button>
          <span className="bp-logic-canvas-stats">节点 {nodes.length} · 连接 {edges.length}</span>
          {(linkOrigin || linkPreview?.moved) && (
            <span className="bp-logic-canvas-linking">
              {linkPreview?.moved ? "拖线模式 · 松开到目标输入端口" : "连接模式 · 请选择目标端口"}
            </span>
          )}
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
          <h3>Block 组件库 · 中英并列 · {palette.length} 种</h3>
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
              onPointerMove={movePointerLink}
              onPointerUp={endPointerLink}
              onPointerCancel={cancelPointerLink}
            >
              <svg className="bp-logic-canvas-edges" width={stageWidth} height={stageHeight} aria-hidden>
                <defs>
                  <marker
                    id={arrowMarkerId}
                    markerWidth="8"
                    markerHeight="8"
                    refX="7"
                    refY="4"
                    orient="auto"
                    markerUnits="strokeWidth"
                  >
                    <path d="M 0 0 L 8 4 L 0 8 z" className="bp-logic-canvas-edge-arrow" />
                  </marker>
                </defs>
                {linkPreview?.moved && (
                  <path
                    className="bp-logic-canvas-edge bp-logic-canvas-edge-preview"
                    markerEnd={`url(#${arrowMarkerId})`}
                    d={`M ${linkPreview.startX} ${linkPreview.startY} C ${linkPreview.startX + 60} ${linkPreview.startY}, ${linkPreview.currentX - 60} ${linkPreview.currentY}, ${linkPreview.currentX} ${linkPreview.currentY}`}
                  />
                )}
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
                      markerEnd={`url(#${arrowMarkerId})`}
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
                  linking={linkOrigin?.nodeId === node.id || linkPreview?.nodeId === node.id}
                  runState={nodeRunStates?.get(node.id)}
                  disabled={disabled}
                  onSelect={() => onSelectNode?.(node.id)}
                  onStartLink={(sourcePort, branchPath) => clickSourcePort(sourcePort, branchPath, node.id)}
                  onPointerLinkStart={(sourcePort, branchPath, portIndex, event) => (
                    startPointerLink(node, sourcePort, branchPath, portIndex, event)
                  )}
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
