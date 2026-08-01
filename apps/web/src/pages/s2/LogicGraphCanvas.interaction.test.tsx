import React, { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LogicGraphEdge, LogicGraphNode } from "./logicCanvasGraph";

const dnd = vi.hoisted(() => ({
  onDragEnd: null as null | ((event: Record<string, unknown>) => void),
}));

vi.mock("@dnd-kit/core", () => ({
  DndContext: ({ children, onDragEnd }: { children: React.ReactNode; onDragEnd: (event: Record<string, unknown>) => void }) => {
    dnd.onDragEnd = onDragEnd;
    return children;
  },
  KeyboardSensor: class KeyboardSensor {},
  PointerSensor: class PointerSensor {},
  useDraggable: () => ({
    attributes: { "aria-describedby": "dnd-description" },
    listeners: {},
    setNodeRef: () => undefined,
    transform: null,
    isDragging: false,
  }),
  useDroppable: () => ({ setNodeRef: () => undefined, isOver: false }),
  useSensor: (...args: unknown[]) => args,
  useSensors: (...args: unknown[]) => args,
}));

import {
  DEFAULT_LOGIC_PALETTE,
  LogicGraphCanvas,
  type LogicCanvasDirtyReason,
  type LogicCanvasNodeRunState,
} from "./LogicGraphCanvas";

const initialNodes: LogicGraphNode[] = [
  { id: "input-1", kind: "input", label: "Input", position_x: 20, position_y: 20, config: {} },
  { id: "llm-1", kind: "use_llm", label: "LLM", position_x: 260, position_y: 20, config: {} },
  { id: "execute-1", kind: "execute", label: "Execute", position_x: 500, position_y: 20, config: {} },
  {
    id: "branch-1",
    kind: "branch",
    label: "Branch",
    position_x: 260,
    position_y: 180,
    config: { paths: [{ id: "high", label: "High" }, { id: "default", label: "Default", default: true }] },
  },
];

const initialEdges: LogicGraphEdge[] = [
  { id: "edge-a", source_node_id: "input-1", source_port: "out", target_node_id: "llm-1", target_port: "in", branch_path: "", order: 0 },
  { id: "edge-b", source_node_id: "llm-1", source_port: "out", target_node_id: "execute-1", target_port: "in", branch_path: "", order: 1 },
];

type HarnessState = {
  nodes: LogicGraphNode[];
  edges: LogicGraphEdge[];
  reasons: LogicCanvasDirtyReason[];
  rejected: string[];
  zoom: number;
  collapsed: boolean;
  selectedNodeId: string;
  nodeRunStates: ReadonlyMap<string, LogicCanvasNodeRunState>;
  setZoom: (value: number) => void;
  setNodeRunStates: React.Dispatch<React.SetStateAction<ReadonlyMap<string, LogicCanvasNodeRunState>>>;
};

let latest: HarnessState;

function Harness() {
  const [nodes, setNodes] = useState(initialNodes);
  const [edges, setEdges] = useState(initialEdges);
  const [reasons, setReasons] = useState<LogicCanvasDirtyReason[]>([]);
  const [rejected, setRejected] = useState<string[]>([]);
  const [zoom, setZoom] = useState(1);
  const [collapsed, setCollapsed] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [nodeRunStates, setNodeRunStates] = useState<ReadonlyMap<string, LogicCanvasNodeRunState>>(() => new Map([
    ["input-1", "executed"],
    ["llm-1", "skipped"],
    ["execute-1", "failed"],
    ["branch-1", "canceled"],
    ["ghost-node", "failed"],
  ]));
  latest = {
    nodes,
    edges,
    reasons,
    rejected,
    zoom,
    collapsed,
    selectedNodeId,
    nodeRunStates,
    setZoom,
    setNodeRunStates,
  };
  return (
    <LogicGraphCanvas
      nodes={nodes}
      edges={edges}
      palette={DEFAULT_LOGIC_PALETTE}
      zoom={zoom}
      selectedNodeId={selectedNodeId}
      nodeRunStates={nodeRunStates}
      inspectorCollapsed={collapsed}
      onNodesChange={setNodes}
      onEdgesChange={setEdges}
      onSelectNode={setSelectedNodeId}
      onDirty={(reason) => setReasons((previous) => [...previous, reason])}
      onEdgeRejected={(message) => setRejected((previous) => [...previous, message])}
      onZoomChange={setZoom}
      onInspectorCollapsedChange={setCollapsed}
      createNodeId={(kind) => `${kind}-added`}
      createEdgeId={() => `edge-${latest.edges.length + 1}`}
    />
  );
}

function button(host: HTMLElement, label: string): HTMLButtonElement {
  const found = host.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`);
  if (!found) throw new Error(`missing button: ${label}`);
  return found;
}

function pointerEvent(type: string, clientX: number, clientY: number): Event {
  const event = new MouseEvent(type, { bubbles: true, button: 0, clientX, clientY });
  Object.defineProperty(event, "pointerId", { configurable: true, value: 1 });
  return event;
}

describe("LogicGraphCanvas interactions", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    await act(async () => root.render(<Harness />));
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    dnd.onDragEnd = null;
  });

  it("drops a palette item at the zoom-aware canvas coordinate and moves an existing node", async () => {
    const canvas = host.querySelector<HTMLElement>('[data-testid="logic-graph-drop-area"]')!;
    Object.defineProperty(canvas, "scrollLeft", { configurable: true, value: 20 });
    Object.defineProperty(canvas, "scrollTop", { configurable: true, value: 10 });
    canvas.getBoundingClientRect = () => ({ left: 100, top: 80, right: 900, bottom: 680, width: 800, height: 600, x: 100, y: 80, toJSON: () => ({}) });
    await act(async () => latest.setZoom(2));

    await act(async () => dnd.onDragEnd?.({
      active: {
        data: { current: { source: "palette", item: DEFAULT_LOGIC_PALETTE.find((item) => item.kind === "handoff") } },
        rect: { current: { translated: { left: 310, top: 220, width: 40, height: 20 } } },
      },
      over: { id: "logic-graph-canvas" },
      delta: { x: 0, y: 0 },
    }));
    const added = latest.nodes.find((node) => node.id === "handoff-added")!;
    expect(added).toMatchObject({ kind: "handoff", position_x: 35, position_y: 38 });
    expect(latest.reasons).toContain("node_add");

    await act(async () => dnd.onDragEnd?.({
      active: { data: { current: { source: "canvas", nodeId: "input-1" } }, rect: { current: { translated: null } } },
      over: { id: "logic-graph-canvas" },
      delta: { x: 160, y: 80 },
    }));
    expect(latest.nodes.find((node) => node.id === "input-1")).toMatchObject({ position_x: 100, position_y: 60 });
    expect(latest.reasons).toContain("node_move");
    expect(host.querySelector('[data-node-id="input-1"]')?.getAttribute("data-run-state")).toBe("executed");
  });

  it("renders all four read-only run states with clear badges and aria without masking selection", async () => {
    const expectations: Array<[string, LogicCanvasNodeRunState, string]> = [
      ["input-1", "executed", "已执行"],
      ["llm-1", "skipped", "已跳过"],
      ["execute-1", "failed", "失败"],
      ["branch-1", "canceled", "已取消"],
    ];
    expectations.forEach(([nodeId, state, label]) => {
      const node = host.querySelector<HTMLElement>(`[data-node-id="${nodeId}"]`)!;
      expect(node.dataset.runState).toBe(state);
      expect(node.classList.contains(`is-run-${state}`)).toBe(true);
      expect(node.getAttribute("aria-label")).toContain(`运行状态：${label}`);
      expect(node.querySelector(`[aria-label="运行状态：${label}"]`)?.textContent).toBe(label);
    });
    expect(host.querySelector('[data-node-id="ghost-node"]')).toBeNull();

    await act(async () => button(host, "拖动 execute-1").click());
    const selectedFailed = host.querySelector<HTMLElement>('[data-node-id="execute-1"]')!;
    expect(selectedFailed.classList.contains("is-selected")).toBe(true);
    expect(selectedFailed.classList.contains("is-run-failed")).toBe(true);
    expect(latest.reasons).toHaveLength(0);
  });

  it("clears read-only run states without mutating graph or dirty reasons", async () => {
    const nodesBefore = structuredClone(latest.nodes);
    const edgesBefore = structuredClone(latest.edges);
    await act(async () => latest.setNodeRunStates(new Map()));
    expect(host.querySelectorAll("[data-run-state]")).toHaveLength(0);
    expect(latest.nodes).toEqual(nodesBefore);
    expect(latest.edges).toEqual(edgesBefore);
    expect(latest.reasons).toHaveLength(0);
  });

  it("connects ports, exposes branch path ports and deletes an edge", async () => {
    expect(button(host, "从 branch-1 的 high 端口建立连接")).toBeTruthy();
    await act(async () => button(host, "从 branch-1 的 high 端口建立连接").click());
    await act(async () => button(host, "连接到 execute-1 的 in 端口").click());
    expect(latest.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({ source_node_id: "branch-1", source_port: "high", target_node_id: "execute-1", branch_path: "high" }),
    ]));
    expect(latest.reasons).toContain("edge_add");

    const created = latest.edges.find((edge) => edge.source_node_id === "branch-1")!;
    await act(async () => button(host, `删除连接 ${created.id}`).click());
    expect(latest.edges.some((edge) => edge.id === created.id)).toBe(false);
    expect(latest.reasons).toContain("edge_delete");
  });

  it("drags an output port onto an input port with a live preview and directional arrows", async () => {
    const source = button(host, "从 branch-1 的 high 端口建立连接");
    const target = button(host, "连接到 execute-1 的 in 端口");
    const stage = host.querySelector<HTMLElement>(".bp-logic-canvas-stage")!;
    const originalElementFromPoint = document.elementFromPoint;
    Object.defineProperty(document, "elementFromPoint", {
      configurable: true,
      value: vi.fn(() => target),
    });
    const edgeCount = latest.edges.length;

    await act(async () => {
      source.dispatchEvent(pointerEvent("pointerdown", 440, 214));
      stage.dispatchEvent(pointerEvent("pointermove", 500, 120));
    });
    const preview = host.querySelector<SVGPathElement>(".bp-logic-canvas-edge-preview");
    expect(preview).not.toBeNull();
    expect(preview?.getAttribute("marker-end")).toMatch(/^url\(#logic-arrow-/);
    expect(host.textContent).toContain("拖线模式");

    await act(async () => {
      target.dispatchEvent(pointerEvent("pointerup", 500, 62));
      source.click();
    });
    expect(latest.edges).toHaveLength(edgeCount + 1);
    expect(latest.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        source_node_id: "branch-1",
        source_port: "high",
        target_node_id: "execute-1",
        branch_path: "high",
      }),
    ]));
    expect(latest.reasons.at(-1)).toBe("edge_add");
    expect(host.querySelector(".bp-logic-canvas-edge-preview")).toBeNull();
    expect(host.textContent).not.toContain("连接模式 · 请选择目标端口");
    host.querySelectorAll<SVGPathElement>(".bp-logic-canvas-edge:not(.bp-logic-canvas-edge-preview)")
      .forEach((path) => expect(path.getAttribute("marker-end")).toMatch(/^url\(#logic-arrow-/));

    Object.defineProperty(document, "elementFromPoint", {
      configurable: true,
      value: originalElementFromPoint,
    });
  });

  it("cancels empty pointer drops and reuses duplicate-edge validation without mutating the graph", async () => {
    const source = button(host, "从 input-1 的 out 端口建立连接");
    const duplicateTarget = button(host, "连接到 llm-1 的 in 端口");
    const originalElementFromPoint = document.elementFromPoint;
    const edgeCount = latest.edges.length;

    Object.defineProperty(document, "elementFromPoint", {
      configurable: true,
      value: vi.fn(() => null),
    });
    await act(async () => {
      source.dispatchEvent(pointerEvent("pointerdown", 200, 54));
      source.dispatchEvent(pointerEvent("pointermove", 360, 160));
      source.dispatchEvent(pointerEvent("pointerup", 360, 160));
    });
    expect(latest.edges).toHaveLength(edgeCount);
    expect(host.textContent).toContain("连接已取消");
    expect(host.querySelector(".bp-logic-canvas-edge-preview")).toBeNull();

    Object.defineProperty(document, "elementFromPoint", {
      configurable: true,
      value: vi.fn(() => duplicateTarget),
    });
    await act(async () => {
      source.dispatchEvent(pointerEvent("pointerdown", 200, 54));
      source.dispatchEvent(pointerEvent("pointermove", 260, 62));
      source.dispatchEvent(pointerEvent("pointerup", 260, 62));
    });
    expect(latest.edges).toHaveLength(edgeCount);
    expect(latest.rejected.at(-1)).toContain("重复");

    Object.defineProperty(document, "elementFromPoint", {
      configurable: true,
      value: originalElementFromPoint,
    });
  });

  it("keeps click-to-add accessibility and removes a node with its incident edges", async () => {
    await act(async () => button(host, "添加 输入").click());
    expect(latest.nodes.some((node) => node.id === "input-added")).toBe(true);
    expect(latest.reasons).toContain("node_add");

    await act(async () => button(host, "删除节点 llm-1").click());
    expect(latest.nodes.some((node) => node.id === "llm-1")).toBe(false);
    expect(latest.edges.some((edge) => edge.source_node_id === "llm-1" || edge.target_node_id === "llm-1")).toBe(false);
    expect(latest.reasons).toContain("node_delete");
  });

  it("rejects duplicate, self-loop and cyclic connections before changing edges", async () => {
    const edgeCount = latest.edges.length;
    await act(async () => button(host, "从 input-1 的 out 端口建立连接").click());
    await act(async () => button(host, "连接到 llm-1 的 in 端口").click());
    expect(latest.edges).toHaveLength(edgeCount);
    expect(latest.rejected.at(-1)).toContain("重复");

    await act(async () => button(host, "从 input-1 的 out 端口建立连接").click());
    await act(async () => button(host, "连接到 input-1 的 in 端口").click());
    expect(latest.edges).toHaveLength(edgeCount);
    expect(latest.rejected.at(-1)).toContain("自身");

    await act(async () => button(host, "从 execute-1 的 out 端口建立连接").click());
    await act(async () => button(host, "连接到 input-1 的 in 端口").click());
    expect(latest.edges).toHaveLength(edgeCount);
    expect(latest.rejected.at(-1)).toContain("环");
  });

  it("offers controlled zoom and inspector-collapse interfaces without marking the graph dirty", async () => {
    const dirtyCount = latest.reasons.length;
    await act(async () => button(host, "放大画布").click());
    expect(latest.zoom).toBe(1.1);
    await act(async () => button(host, "重置画布缩放").click());
    expect(latest.zoom).toBe(1);
    await act(async () => button(host, "折叠属性面板").click());
    expect(latest.collapsed).toBe(true);
    expect(latest.reasons).toHaveLength(dirtyCount);
  });
});
