import { describe, expect, it } from "vitest";

import {
  LOGIC_BLOCK_KINDS,
  assertSavedLogicGraphMatches,
  logicCanvasDropPosition,
  moveLogicCanvasPosition,
  normalizeLogicGraph,
  tryAddLogicEdge,
  type LogicGraphEdge,
  type LogicGraphNode,
  type LogicGraphSnapshot,
} from "./logicCanvasGraph";

const nodes: LogicGraphNode[] = [
  { id: "input-1", kind: "input", label: "Input", position_x: 20, position_y: 30, config: {} },
  { id: "llm-1", kind: "use_llm", label: "LLM", position_x: 240, position_y: 30, config: { prompt: "hello" } },
  { id: "execute-1", kind: "execute", label: "Execute", position_x: 460, position_y: 30, config: {} },
];

const edges: LogicGraphEdge[] = [
  {
    id: "edge-1",
    source_node_id: "input-1",
    source_port: "out",
    target_node_id: "llm-1",
    target_port: "in",
    branch_path: "",
    order: 0,
  },
];

function graph(overrides: Partial<LogicGraphSnapshot> = {}): LogicGraphSnapshot {
  return {
    id: "logic-1",
    name: "Risk flow",
    description: "",
    status: "draft",
    schema_version: 1,
    revision: 4,
    published_version: null,
    graph_hash: "hash-1",
    persisted: true,
    demo: false,
    nodes,
    edges,
    entry_node_ids: ["input-1"],
    ...overrides,
  };
}

describe("logicCanvasGraph · canonical contract", () => {
  it("locks all 10 supported block kinds", () => {
    expect(LOGIC_BLOCK_KINDS).toEqual([
      "input",
      "create_variable",
      "get_property",
      "use_llm",
      "use_tool",
      "transform",
      "apply_action",
      "execute",
      "branch",
      "handoff",
    ]);
  });

  it("normalizes object keys plus node, edge and entry order", () => {
    const normalized = normalizeLogicGraph(graph({
      nodes: [
        { ...nodes[1], config: { z: 1, nested: { z: 2, a: 1 }, a: 2 } },
        nodes[2],
        nodes[0],
      ],
      edges: [
        { ...edges[0], id: "edge-z", target_node_id: "execute-1" },
        { ...edges[0], id: "edge-a" },
      ],
      entry_node_ids: ["llm-1", "input-1"],
    }));

    expect(normalized.nodes.map((node) => node.id)).toEqual(["execute-1", "input-1", "llm-1"]);
    const llm = normalized.nodes.find((node) => node.id === "llm-1")!;
    expect(Object.keys(llm.config)).toEqual(["a", "nested", "z"]);
    expect(Object.keys(llm.config.nested as object)).toEqual(["a", "z"]);
    expect(normalized.edges.map((edge) => edge.id)).toEqual(["edge-a", "edge-z"]);
    expect(normalized.entry_node_ids).toEqual(["input-1", "llm-1"]);
  });

  it("rejects unknown kinds, invalid coordinates and dangling endpoints", () => {
    expect(() => normalizeLogicGraph(graph({
      nodes: [{ ...nodes[0], kind: "unknown" as LogicGraphNode["kind"] }],
      edges: [],
    }))).toThrow("未知 Block kind");
    expect(() => normalizeLogicGraph(graph({
      nodes: [{ ...nodes[0], position_x: Number.NaN }],
      edges: [],
    }))).toThrow("坐标必须是有限非负数");
    expect(() => normalizeLogicGraph(graph({
      edges: [{ ...edges[0], target_node_id: "missing" }],
    }))).toThrow("连接端点不存在");
    expect(() => normalizeLogicGraph(graph({
      edges: [{ ...edges[0], source_port: "wrong" }],
    }))).toThrow("端口语义无效");
  });

  it("accepts an exact committed save response independent of ordering", () => {
    expect(() => assertSavedLogicGraphMatches(
      graph({ revision: 5, nodes: [...nodes].reverse(), edges: [...edges].reverse() }),
      {
        graphId: "logic-1",
        expectedRevision: 4,
        name: "Risk flow",
        description: "",
        status: "draft",
        schemaVersion: 1,
        nodes,
        edges,
        entryNodeIds: ["input-1"],
      },
    )).not.toThrow();
  });

  it("fails closed for uncommitted, wrong revision or changed snapshots", () => {
    const expected = {
      graphId: "logic-1",
      expectedRevision: 4,
      name: "Risk flow",
      description: "",
      status: "draft" as const,
      schemaVersion: 1,
      nodes,
      edges,
      entryNodeIds: ["input-1"],
    };
    expect(() => assertSavedLogicGraphMatches(graph({ revision: 5, persisted: false }), expected)).toThrow("未确认持久化");
    expect(() => assertSavedLogicGraphMatches(graph({ revision: 6 }), expected)).toThrow("revision");
    expect(() => assertSavedLogicGraphMatches(graph({ revision: 5, nodes: [{ ...nodes[0], label: "changed" }, ...nodes.slice(1)] }), expected)).toThrow("节点");
    expect(() => assertSavedLogicGraphMatches(graph({ revision: 5, edges: [] }), expected)).toThrow("连接");
  });
});

describe("logicCanvasGraph · edge safety and coordinates", () => {
  it("normalizes movement and palette drop by zoom, scroll and bounds", () => {
    expect(moveLogicCanvasPosition({ x: 10, y: 20 }, { x: 80, y: 40 }, 2)).toEqual({ x: 50, y: 40 });
    expect(moveLogicCanvasPosition({ x: 10, y: 10 }, { x: -100, y: -100 }, 1)).toEqual({ x: 0, y: 0 });
    expect(logicCanvasDropPosition({
      translatedRect: { left: 310, top: 220, width: 40, height: 20 },
      canvasRect: { left: 100, top: 80 },
      scroll: { left: 20, top: 10 },
      zoom: 2,
      nodeSize: { width: 160, height: 60 },
    })).toEqual({ x: 45, y: 50 });
  });

  it("rejects self loops, duplicate edges and cycles before mutation", () => {
    const self = tryAddLogicEdge(nodes, edges, {
      id: "self",
      source_node_id: "input-1",
      source_port: "out",
      target_node_id: "input-1",
      target_port: "in",
      branch_path: "",
      order: 1,
    });
    expect(self).toMatchObject({ ok: false, code: "self_loop" });

    const duplicate = tryAddLogicEdge(nodes, edges, { ...edges[0], id: "duplicate" });
    expect(duplicate).toMatchObject({ ok: false, code: "duplicate" });

    const chain = tryAddLogicEdge(nodes, edges, {
      id: "edge-2",
      source_node_id: "llm-1",
      source_port: "out",
      target_node_id: "execute-1",
      target_port: "in",
      branch_path: "",
      order: 1,
    });
    expect(chain.ok).toBe(true);
    if (!chain.ok) throw new Error("expected chain edge");
    const cycle = tryAddLogicEdge(nodes, chain.edges, {
      id: "edge-3",
      source_node_id: "execute-1",
      source_port: "out",
      target_node_id: "input-1",
      target_port: "in",
      branch_path: "",
      order: 2,
    });
    expect(cycle).toMatchObject({ ok: false, code: "cycle" });
  });
});
