import type { GraphSnapshot } from "../../api/ontologyExplorerContracts";

export type OntologyGraphLayoutMode = "radial" | "layered";

export type PositionedGraphNode = GraphSnapshot["nodes"][number] & {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type PositionedGraphEdge = GraphSnapshot["edges"][number] & {
  path: string;
  labelX: number;
  labelY: number;
};

export type OntologyGraphLayout = {
  width: number;
  height: number;
  nodes: PositionedGraphNode[];
  edges: PositionedGraphEdge[];
};

const NODE_WIDTH = 176;
const NODE_HEIGHT = 54;
const STAGE_PADDING = 96;

function stableNodes(snapshot: GraphSnapshot) {
  return [...snapshot.nodes].sort((left, right) =>
    left.depth - right.depth || left.key.localeCompare(right.key),
  );
}

function radialNodes(snapshot: GraphSnapshot): PositionedGraphNode[] {
  const byDepth = new Map<number, GraphSnapshot["nodes"]>();
  for (const node of stableNodes(snapshot)) {
    const nodes = byDepth.get(node.depth) || [];
    nodes.push(node);
    byDepth.set(node.depth, nodes);
  }
  const positioned: PositionedGraphNode[] = [];
  for (const [depth, nodes] of [...byDepth.entries()].sort(([a], [b]) => a - b)) {
    if (depth === 0) {
      nodes.forEach((node, index) => positioned.push({
        ...node,
        x: index * (NODE_WIDTH + 28),
        y: 0,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
      }));
      continue;
    }
    const perRing = 28;
    nodes.forEach((node, index) => {
      const ring = Math.floor(index / perRing);
      const ringNodes = Math.min(perRing, nodes.length - ring * perRing);
      const ringIndex = index % perRing;
      const radius = 225 * depth + ring * 92;
      const angle = -Math.PI / 2 + (Math.PI * 2 * ringIndex) / Math.max(1, ringNodes);
      positioned.push({
        ...node,
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
      });
    });
  }
  return positioned;
}

function layeredNodes(snapshot: GraphSnapshot): PositionedGraphNode[] {
  const byDepth = new Map<number, GraphSnapshot["nodes"]>();
  for (const node of stableNodes(snapshot)) {
    const nodes = byDepth.get(node.depth) || [];
    nodes.push(node);
    byDepth.set(node.depth, nodes);
  }
  const columns = [...byDepth.entries()].sort(([a], [b]) => a - b);
  const largest = Math.max(1, ...columns.map(([, nodes]) => nodes.length));
  return columns.flatMap(([depth, nodes]) => {
    const offset = (largest - nodes.length) * 42;
    return nodes.map((node, index) => ({
      ...node,
      x: depth * 260,
      y: offset + index * 84,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
    }));
  });
}

function normalize(nodes: PositionedGraphNode[]) {
  if (nodes.length === 0) return { width: 960, height: 560, nodes };
  const minX = Math.min(...nodes.map((node) => node.x - node.width / 2));
  const maxX = Math.max(...nodes.map((node) => node.x + node.width / 2));
  const minY = Math.min(...nodes.map((node) => node.y - node.height / 2));
  const maxY = Math.max(...nodes.map((node) => node.y + node.height / 2));
  return {
    width: Math.max(960, maxX - minX + STAGE_PADDING * 2),
    height: Math.max(560, maxY - minY + STAGE_PADDING * 2),
    nodes: nodes.map((node) => ({
      ...node,
      x: node.x - minX + STAGE_PADDING,
      y: node.y - minY + STAGE_PADDING,
    })),
  };
}

export function layoutOntologyGraph(
  snapshot: GraphSnapshot,
  mode: OntologyGraphLayoutMode,
): OntologyGraphLayout {
  const normalized = normalize(mode === "radial" ? radialNodes(snapshot) : layeredNodes(snapshot));
  const nodeByKey = new Map(normalized.nodes.map((node) => [node.key, node]));
  const edges = snapshot.edges.flatMap<PositionedGraphEdge>((edge) => {
    const source = nodeByKey.get(edge.source);
    const target = nodeByKey.get(edge.target);
    if (!source || !target) return [];
    const deltaX = target.x - source.x;
    const curve = mode === "layered" ? Math.max(54, Math.abs(deltaX) * 0.42) : 0;
    const path = mode === "layered"
      ? `M ${source.x} ${source.y} C ${source.x + curve} ${source.y}, ${target.x - curve} ${target.y}, ${target.x} ${target.y}`
      : `M ${source.x} ${source.y} Q ${(source.x + target.x) / 2} ${(source.y + target.y) / 2 - 18} ${target.x} ${target.y}`;
    return [{
      ...edge,
      path,
      labelX: (source.x + target.x) / 2,
      labelY: (source.y + target.y) / 2 - 8,
    }];
  });
  return { ...normalized, edges };
}

export function stableObjectTypeColor(objectType: string): string {
  const palette = ["#4f8bd8", "#6f61d7", "#38a69a", "#d28a39", "#b95f8b", "#5d9a55", "#be6559"];
  let hash = 0;
  for (let index = 0; index < objectType.length; index += 1) {
    hash = ((hash << 5) - hash + objectType.charCodeAt(index)) | 0;
  }
  return palette[Math.abs(hash) % palette.length];
}
