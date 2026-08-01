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
  setZoom: (value: number) => void;
};

let latest: HarnessState;

function Harness() {
  const [nodes, setNodes] = useState(initialNodes);
  const [edges, setEdges] = useState(initialEdges);
  const [reasons, setReasons] = useState<LogicCanvasDirtyReason[]>([]);
  const [rejected, setRejected] = useState<string[]>([]);
  const [zoom, setZoom] = useState(1);
  const [collapsed, setCollapsed] = useState(false);
  latest = { nodes, edges, reasons, rejected, zoom, collapsed, setZoom };
  return (
    <LogicGraphCanvas
      nodes={nodes}
      edges={edges}
      palette={DEFAULT_LOGIC_PALETTE}
      zoom={zoom}
      inspectorCollapsed={collapsed}
      onNodesChange={setNodes}
      onEdgesChange={setEdges}
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
