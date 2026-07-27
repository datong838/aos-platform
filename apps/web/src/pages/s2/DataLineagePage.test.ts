import { describe, expect, it } from "vitest";
import {
  NODE_TYPE_LABEL,
  NODE_TYPE_TONE,
  NODE_STATUS_LABEL,
  NODE_STATUS_TONE,
  formatTimestamp,
  filterNodes,
  upstreamNodes,
  downstreamNodes,
  computeImpact,
  filterByLevel,
  countByType,
  countByStatus,
  edgePath,
  type LineageNode,
  type LineageGraph,
} from "./DataLineagePage";

const MOCK_NODES: LineageNode[] = [
  { id: "src1", name: "Source A", type: "source", status: "healthy", level: 0, x: 0, y: 0 },
  { id: "ds1", name: "Dataset B", type: "dataset", status: "healthy", level: 1, x: 100, y: 0 },
  { id: "pl1", name: "Pipeline C", type: "pipeline", status: "healthy", level: 2, x: 200, y: 0 },
  { id: "ot1", name: "OrderType", type: "object_type", status: "healthy", level: 3, x: 300, y: 0 },
  { id: "fn1", name: "Funnel D", type: "funnel", status: "error", level: 3, x: 300, y: 50 },
  { id: "ds2", name: "Dataset E", type: "dataset", status: "stale", level: 4, x: 400, y: 0 },
];

const MOCK_EDGES = [
  { id: "e1", source: "src1", target: "ds1" },
  { id: "e2", source: "ds1", target: "pl1" },
  { id: "e3", source: "pl1", target: "ot1" },
  { id: "e4", source: "pl1", target: "fn1" },
  { id: "e5", source: "ot1", target: "ds2" },
];

const MOCK_GRAPH: LineageGraph = { nodes: MOCK_NODES, edges: MOCK_EDGES };

// ── Labels ────────────────────────────────────────────
describe("DataLineagePage · NODE_TYPE_LABEL", () => {
  it("source → 数据源", () => {
    expect(NODE_TYPE_LABEL.source).toBe("数据源");
  });
  it("has 5 types", () => {
    expect(Object.keys(NODE_TYPE_LABEL)).toHaveLength(5);
  });
});

describe("DataLineagePage · NODE_TYPE_TONE", () => {
  it("source → ok", () => {
    expect(NODE_TYPE_TONE.source).toBe("ok");
  });
  it("funnel → bad", () => {
    expect(NODE_TYPE_TONE.funnel).toBe("bad");
  });
});

describe("DataLineagePage · NODE_STATUS_LABEL", () => {
  it("healthy → 健康", () => {
    expect(NODE_STATUS_LABEL.healthy).toBe("健康");
  });
  it("error → 错误", () => {
    expect(NODE_STATUS_LABEL.error).toBe("错误");
  });
});

describe("DataLineagePage · NODE_STATUS_TONE", () => {
  it("healthy → ok", () => {
    expect(NODE_STATUS_TONE.healthy).toBe("ok");
  });
  it("error → bad", () => {
    expect(NODE_STATUS_TONE.error).toBe("bad");
  });
  it("stale → warn", () => {
    expect(NODE_STATUS_TONE.stale).toBe("warn");
  });
});

// ── formatTimestamp ───────────────────────────────────
describe("DataLineagePage · formatTimestamp", () => {
  it("empty → —", () => {
    expect(formatTimestamp("")).toBe("—");
  });
  it("just now", () => {
    expect(formatTimestamp(new Date().toISOString())).toBe("刚刚");
  });
});

// ── filterNodes ───────────────────────────────────────
describe("DataLineagePage · filterNodes", () => {
  it("no filter → all", () => {
    expect(filterNodes(MOCK_NODES, "all", "")).toHaveLength(6);
  });
  it("filter by type", () => {
    expect(filterNodes(MOCK_NODES, "dataset", "")).toHaveLength(2);
  });
  it("filter by query", () => {
    expect(filterNodes(MOCK_NODES, "all", "source")).toHaveLength(1);
  });
  it("no match", () => {
    expect(filterNodes(MOCK_NODES, "all", "xyz")).toHaveLength(0);
  });
});

// ── upstreamNodes ─────────────────────────────────────
describe("DataLineagePage · upstreamNodes", () => {
  it("finds direct + transitive upstream", () => {
    const up = upstreamNodes(MOCK_GRAPH, "ot1");
    const ids = up.map((n) => n.id);
    expect(ids).toContain("pl1");
    expect(ids).toContain("ds1");
    expect(ids).toContain("src1");
    expect(up).toHaveLength(3);
  });
  it("source node has no upstream", () => {
    expect(upstreamNodes(MOCK_GRAPH, "src1")).toHaveLength(0);
  });
});

// ── downstreamNodes ───────────────────────────────────
describe("DataLineagePage · downstreamNodes", () => {
  it("finds direct + transitive downstream", () => {
    const down = downstreamNodes(MOCK_GRAPH, "src1");
    const ids = down.map((n) => n.id);
    expect(ids).toContain("ds1");
    expect(ids).toContain("pl1");
    expect(ids).toContain("ot1");
    expect(ids).toContain("fn1");
    expect(ids).toContain("ds2");
  });
  it("leaf node has no downstream", () => {
    expect(downstreamNodes(MOCK_GRAPH, "ds2")).toHaveLength(0);
  });
});

// ── computeImpact ─────────────────────────────────────
describe("DataLineagePage · computeImpact", () => {
  it("computes upstream + downstream", () => {
    const impact = computeImpact(MOCK_GRAPH, "pl1");
    expect(impact.upstream).toBe(2);  // src1, ds1
    expect(impact.downstream).toBe(3); // ot1, fn1, ds2
    expect(impact.affected).toBe(5);
  });
  it("leaf node has 0 downstream", () => {
    const impact = computeImpact(MOCK_GRAPH, "ds2");
    expect(impact.downstream).toBe(0);
  });
  it("root node has 0 upstream", () => {
    const impact = computeImpact(MOCK_GRAPH, "src1");
    expect(impact.upstream).toBe(0);
  });
});

// ── filterByLevel ─────────────────────────────────────
describe("DataLineagePage · filterByLevel", () => {
  it("max level 0 → only level 0", () => {
    expect(filterByLevel(MOCK_NODES, 0)).toHaveLength(1);
  });
  it("max level 2 → levels 0-2", () => {
    expect(filterByLevel(MOCK_NODES, 2)).toHaveLength(3);
  });
  it("max level 4 → all", () => {
    expect(filterByLevel(MOCK_NODES, 4)).toHaveLength(6);
  });
});

// ── countByType ───────────────────────────────────────
describe("DataLineagePage · countByType", () => {
  it("counts each type", () => {
    const counts = countByType(MOCK_NODES);
    expect(counts.source).toBe(1);
    expect(counts.dataset).toBe(2);
    expect(counts.pipeline).toBe(1);
    expect(counts.object_type).toBe(1);
    expect(counts.funnel).toBe(1);
  });
});

// ── countByStatus ─────────────────────────────────────
describe("DataLineagePage · countByStatus", () => {
  it("counts each status", () => {
    const counts = countByStatus(MOCK_NODES);
    expect(counts.healthy).toBe(4);
    expect(counts.error).toBe(1);
    expect(counts.stale).toBe(1);
  });
});

// ── edgePath ──────────────────────────────────────────
describe("DataLineagePage · edgePath", () => {
  it("returns SVG path string", () => {
    const path = edgePath(MOCK_EDGES[0], MOCK_NODES);
    expect(path).toContain("M ");
    expect(path).toContain("C ");
  });
  it("missing nodes → empty string", () => {
    const path = edgePath({ id: "x", source: "missing", target: "ds1" }, MOCK_NODES);
    expect(path).toBe("");
  });
});
