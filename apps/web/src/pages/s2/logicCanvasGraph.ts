/** Canonical data and safety helpers for the AIP Logic free-form graph canvas. */

export const LOGIC_BLOCK_KINDS = [
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
] as const;

export type LogicBlockKind = (typeof LOGIC_BLOCK_KINDS)[number];
export type LogicGraphStatus = "draft" | "published" | "archived";

export interface LogicGraphNode {
  id: string;
  kind: LogicBlockKind;
  label: string;
  position_x: number;
  position_y: number;
  config: Record<string, unknown>;
}

export interface LogicGraphEdge {
  id: string;
  source_node_id: string;
  source_port: string;
  target_node_id: string;
  target_port: string;
  branch_path: string;
  order: number;
}

export interface LogicGraphSnapshot {
  id: string;
  name: string;
  description: string;
  status: LogicGraphStatus;
  schema_version: number;
  revision: number;
  published_version: number | null;
  graph_hash: string;
  persisted: boolean;
  demo?: boolean;
  nodes: LogicGraphNode[];
  edges: LogicGraphEdge[];
  entry_node_ids: string[];
  created_at?: string;
  updated_at?: string;
}

export interface LogicGraphSaveExpectation {
  graphId: string;
  expectedRevision: number;
  name: string;
  description: string;
  status: LogicGraphStatus;
  schemaVersion: number;
  nodes: LogicGraphNode[];
  edges: LogicGraphEdge[];
  entryNodeIds: string[];
}

export type LogicEdgeRejectionCode =
  | "missing_endpoint"
  | "invalid_port"
  | "self_loop"
  | "duplicate"
  | "cycle";

export type LogicEdgeMutationResult =
  | { ok: true; edges: LogicGraphEdge[] }
  | { ok: false; code: LogicEdgeRejectionCode; reason: string };

const BLOCK_KIND_SET = new Set<string>(LOGIC_BLOCK_KINDS);
const GRAPH_STATUS_SET = new Set<string>(["draft", "published", "archived"]);
export const MAX_LOGIC_CANVAS_COORDINATE = 5_000;

function boundedCanvasCoordinate(value: number, fallback = 0): number {
  const safeValue = Number.isFinite(value) ? value : fallback;
  return Math.min(MAX_LOGIC_CANVAS_COORDINATE, Math.max(0, safeValue));
}

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, child]) => [key, stableValue(child)]),
    );
  }
  return value;
}

function assertId(id: string, subject: string): void {
  if (!id.trim()) throw new Error(`${subject} ID 不能为空`);
}

function assertCoordinate(value: number, nodeId: string, axis: "x" | "y"): void {
  if (!Number.isFinite(value) || value < 0) {
    throw new Error(`节点 ${nodeId} 的 ${axis} 坐标必须是有限非负数`);
  }
}

function normalizedNodes(nodes: LogicGraphNode[]): LogicGraphNode[] {
  const ids = new Set<string>();
  return nodes.map((node) => {
    assertId(node.id, "节点");
    if (ids.has(node.id)) throw new Error(`节点 ID 重复：${node.id}`);
    ids.add(node.id);
    if (!BLOCK_KIND_SET.has(node.kind)) throw new Error(`未知 Block kind：${String(node.kind)}`);
    assertCoordinate(node.position_x, node.id, "x");
    assertCoordinate(node.position_y, node.id, "y");
    if (!node.label.trim()) throw new Error(`节点 ${node.id} 标签不能为空`);
    if (!node.config || typeof node.config !== "object" || Array.isArray(node.config)) {
      throw new Error(`节点 ${node.id} config 必须是对象`);
    }
    if (node.kind === "branch") {
      const paths = Array.isArray(node.config.paths) ? node.config.paths : [];
      const defaults = paths.filter((path) => (
        Boolean(path)
        && typeof path === "object"
        && (path as Record<string, unknown>).default === true
      ));
      if (defaults.length > 1) throw new Error(`Branch 节点 ${node.id} 最多允许一个 default 路径`);
    }
    return {
      id: node.id,
      kind: node.kind,
      label: node.label,
      position_x: node.position_x,
      position_y: node.position_y,
      config: stableValue(node.config) as Record<string, unknown>,
    };
  }).sort((left, right) => left.id.localeCompare(right.id));
}

export function getLogicSourcePorts(node: LogicGraphNode): { id: string; label: string; branchPath: string }[] {
  if (node.kind !== "branch") return [{ id: "out", label: "out", branchPath: "" }];
  const paths = Array.isArray(node.config.paths) ? node.config.paths : [];
  const normalized = paths.flatMap((value) => {
    if (!value || typeof value !== "object") return [];
    const path = value as Record<string, unknown>;
    const id = String(path.id || "").trim();
    if (!id) return [];
    return [{ id, label: String(path.label || id), branchPath: id }];
  });
  return normalized.length > 0 ? normalized : [{ id: "default", label: "default", branchPath: "default" }];
}

function edgePortsAreValid(edge: LogicGraphEdge, source: LogicGraphNode): boolean {
  const port = getLogicSourcePorts(source).find((candidate) => candidate.id === edge.source_port);
  return Boolean(port && edge.target_port === "in" && port.branchPath === (edge.branch_path || ""));
}

function normalizedEdges(edges: LogicGraphEdge[], nodeById: Map<string, LogicGraphNode>): LogicGraphEdge[] {
  const ids = new Set<string>();
  return edges.map((edge) => {
    assertId(edge.id, "连接");
    if (ids.has(edge.id)) throw new Error(`连接 ID 重复：${edge.id}`);
    ids.add(edge.id);
    const source = nodeById.get(edge.source_node_id);
    if (!source || !nodeById.has(edge.target_node_id)) {
      throw new Error(`连接端点不存在：${edge.source_node_id} → ${edge.target_node_id}`);
    }
    if (edge.source_node_id === edge.target_node_id) {
      throw new Error(`连接不能指向节点自身：${edge.source_node_id}`);
    }
    if (!edge.source_port.trim() || !edge.target_port.trim()) {
      throw new Error(`连接 ${edge.id} 的端口不能为空`);
    }
    if (!edgePortsAreValid(edge, source)) throw new Error(`连接 ${edge.id} 的端口语义无效`);
    if (!Number.isInteger(edge.order) || edge.order < 0) {
      throw new Error(`连接 ${edge.id} 的 order 必须是非负整数`);
    }
    return {
      id: edge.id,
      source_node_id: edge.source_node_id,
      source_port: edge.source_port,
      target_node_id: edge.target_node_id,
      target_port: edge.target_port,
      branch_path: edge.branch_path || "",
      order: edge.order,
    };
  }).sort((left, right) => left.id.localeCompare(right.id));
}

function hasDirectedCycle(nodes: LogicGraphNode[], edges: LogicGraphEdge[]): boolean {
  const outgoing = new Map<string, string[]>();
  nodes.forEach((node) => outgoing.set(node.id, []));
  edges.forEach((edge) => outgoing.get(edge.source_node_id)?.push(edge.target_node_id));
  const visiting = new Set<string>();
  const visited = new Set<string>();

  const visit = (nodeId: string): boolean => {
    if (visiting.has(nodeId)) return true;
    if (visited.has(nodeId)) return false;
    visiting.add(nodeId);
    for (const target of outgoing.get(nodeId) || []) {
      if (visit(target)) return true;
    }
    visiting.delete(nodeId);
    visited.add(nodeId);
    return false;
  };

  return nodes.some((node) => visit(node.id));
}

function assertNoDuplicateEdges(edges: LogicGraphEdge[]): void {
  const keys = new Set<string>();
  edges.forEach((edge) => {
    const key = [
      edge.source_node_id,
      edge.source_port,
      edge.target_node_id,
      edge.target_port,
      edge.branch_path || "",
    ].join("\u0000");
    if (keys.has(key)) throw new Error(`连接重复：${edge.source_node_id} → ${edge.target_node_id}`);
    keys.add(key);
  });
}

export function normalizeLogicGraph(graph: LogicGraphSnapshot): LogicGraphSnapshot {
  assertId(graph.id, "Logic Graph");
  if (!GRAPH_STATUS_SET.has(graph.status)) throw new Error(`未知 Logic Graph 状态：${String(graph.status)}`);
  if (!Number.isInteger(graph.schema_version) || graph.schema_version < 1) {
    throw new Error("schema_version 必须是正整数");
  }
  if (!Number.isInteger(graph.revision) || graph.revision < 0) {
    throw new Error("revision 必须是非负整数");
  }
  const nodes = normalizedNodes(graph.nodes || []);
  const nodeIds = new Set(nodes.map((node) => node.id));
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const edges = normalizedEdges(graph.edges || [], nodeById);
  assertNoDuplicateEdges(edges);
  if (hasDirectedCycle(nodes, edges)) throw new Error("Logic Graph 存在有向环");
  const entryNodeIds = [...(graph.entry_node_ids || [])].sort((left, right) => left.localeCompare(right));
  if (new Set(entryNodeIds).size !== entryNodeIds.length) throw new Error("入口节点 ID 重复");
  entryNodeIds.forEach((entryId) => {
    if (!nodeIds.has(entryId)) throw new Error(`入口节点不存在：${entryId}`);
  });
  return {
    ...graph,
    nodes,
    edges,
    entry_node_ids: entryNodeIds,
  };
}

function comparableGraph(graph: LogicGraphSnapshot) {
  const normalized = normalizeLogicGraph(graph);
  return {
    id: normalized.id,
    name: normalized.name,
    description: normalized.description,
    status: normalized.status,
    schema_version: normalized.schema_version,
    nodes: normalized.nodes,
    edges: normalized.edges,
    entry_node_ids: normalized.entry_node_ids,
  };
}

export function assertSavedLogicGraphMatches(
  saved: LogicGraphSnapshot,
  expected: LogicGraphSaveExpectation,
): void {
  if (!saved.persisted || saved.demo) throw new Error("服务端未确认持久化");
  if (saved.id !== expected.graphId) {
    throw new Error(`保存响应 Logic Graph 不匹配：期望 ${expected.graphId}，实际 ${saved.id || "—"}`);
  }
  const committedRevision = expected.expectedRevision + 1;
  if (saved.revision !== committedRevision) {
    throw new Error(`保存响应 revision 不匹配：期望 ${committedRevision}，实际 ${saved.revision}`);
  }
  const expectedGraph: LogicGraphSnapshot = {
    id: expected.graphId,
    name: expected.name,
    description: expected.description,
    status: expected.status,
    schema_version: expected.schemaVersion,
    revision: committedRevision,
    published_version: null,
    graph_hash: "",
    persisted: true,
    demo: false,
    nodes: expected.nodes,
    edges: expected.edges,
    entry_node_ids: expected.entryNodeIds,
  };
  const actual = comparableGraph(saved);
  const wanted = comparableGraph(expectedGraph);
  if (JSON.stringify(actual.nodes) !== JSON.stringify(wanted.nodes)) {
    throw new Error("保存响应节点与请求快照不一致");
  }
  if (JSON.stringify(actual.edges) !== JSON.stringify(wanted.edges)) {
    throw new Error("保存响应连接与请求快照不一致");
  }
  const metadataMatches = actual.id === wanted.id
    && actual.name === wanted.name
    && actual.description === wanted.description
    && actual.status === wanted.status
    && actual.schema_version === wanted.schema_version
    && JSON.stringify(actual.entry_node_ids) === JSON.stringify(wanted.entry_node_ids);
  if (!metadataMatches) throw new Error("保存响应元数据与请求快照不一致");
}

export function moveLogicCanvasPosition(
  current: { x: number; y: number },
  delta: { x: number; y: number },
  zoom: number,
): { x: number; y: number } {
  const safeZoom = Number.isFinite(zoom) && zoom > 0 ? zoom : 1;
  const currentX = boundedCanvasCoordinate(current.x);
  const currentY = boundedCanvasCoordinate(current.y);
  const deltaX = Number.isFinite(delta.x) ? delta.x : 0;
  const deltaY = Number.isFinite(delta.y) ? delta.y : 0;
  return {
    x: boundedCanvasCoordinate(currentX + deltaX / safeZoom, currentX),
    y: boundedCanvasCoordinate(currentY + deltaY / safeZoom, currentY),
  };
}

export interface LogicCanvasDropArguments {
  translatedRect: { left: number; top: number; width: number; height: number };
  canvasRect: { left: number; top: number };
  scroll: { left: number; top: number };
  zoom: number;
  nodeSize: { width: number; height: number };
}

export function logicCanvasDropPosition(args: LogicCanvasDropArguments): { x: number; y: number } {
  const safeZoom = Number.isFinite(args.zoom) && args.zoom > 0 ? args.zoom : 1;
  const rawX = (
    args.translatedRect.left
    + args.translatedRect.width / 2
    - args.canvasRect.left
    + args.scroll.left
  ) / safeZoom - args.nodeSize.width / 2;
  const rawY = (
    args.translatedRect.top
    + args.translatedRect.height / 2
    - args.canvasRect.top
    + args.scroll.top
  ) / safeZoom - args.nodeSize.height / 2;
  return {
    x: boundedCanvasCoordinate(rawX),
    y: boundedCanvasCoordinate(rawY),
  };
}

export function tryAddLogicEdge(
  nodes: LogicGraphNode[],
  edges: LogicGraphEdge[],
  candidate: LogicGraphEdge,
): LogicEdgeMutationResult {
  const nodeIds = new Set(nodes.map((node) => node.id));
  if (!nodeIds.has(candidate.source_node_id) || !nodeIds.has(candidate.target_node_id)) {
    return { ok: false, code: "missing_endpoint", reason: "连接端点不存在" };
  }
  const source = nodes.find((node) => node.id === candidate.source_node_id)!;
  if (!edgePortsAreValid(candidate, source)) {
    return { ok: false, code: "invalid_port", reason: "连接端口无效" };
  }
  if (candidate.source_node_id === candidate.target_node_id) {
    return { ok: false, code: "self_loop", reason: "节点不能连接到自身" };
  }
  const duplicate = edges.some((edge) => edge.id === candidate.id || (
    edge.source_node_id === candidate.source_node_id
    && edge.source_port === candidate.source_port
    && edge.target_node_id === candidate.target_node_id
    && edge.target_port === candidate.target_port
    && (edge.branch_path || "") === (candidate.branch_path || "")
  ));
  if (duplicate) return { ok: false, code: "duplicate", reason: "重复连接已被拒绝" };
  const nextEdges = [...edges, candidate];
  if (hasDirectedCycle(nodes, nextEdges)) {
    return { ok: false, code: "cycle", reason: "该连接会形成有向环" };
  }
  return { ok: true, edges: nextEdges };
}
