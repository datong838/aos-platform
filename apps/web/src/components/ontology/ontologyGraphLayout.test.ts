import { describe, expect, it } from "vitest";
import type { GraphSnapshot } from "../../api/ontologyExplorerContracts";
import { layoutOntologyGraph, stableObjectTypeColor } from "./ontologyGraphLayout";

function snapshot(size: number): GraphSnapshot {
  const nodes = Array.from({ length: size }, (_, index) => ({
    key: `Order:${index}`,
    objectType: index % 3 === 0 ? "Order" : index % 3 === 1 ? "Payment" : "CustomerLite",
    objectId: String(index),
    label: `对象 ${index}`,
    depth: index === 0 ? 0 : 1 + (index % 5),
    masked: true,
  }));
  return {
    scope: { orgId: "org-org", workspaceId: "dev-project" },
    sourceAuthority: "ecom_authoritative",
    graphDomain: "domain",
    schemaEtag: "schema",
    snapshot: { asOf: "2026-08-10T00:00:00Z", watermark: "w1" },
    nodes,
    edges: nodes.slice(1).map((node, index) => ({
      key: `edge:${index}`,
      relationType: "connectedTo",
      source: nodes[index].key,
      target: node.key,
      direction: "out" as const,
      graphDomain: "domain" as const,
      edgeAuthority: "authoritative" as const,
    })),
    page: { truncated: false, nextCursor: null },
    limits: { maxNodes: size, maxHops: 5 },
  };
}

describe("O1-UX4 deterministic graph layout", () => {
  it("produces the same radial positions and valid edge paths", () => {
    const input = snapshot(32);
    const first = layoutOntologyGraph(input, "radial");
    const second = layoutOntologyGraph(input, "radial");
    expect(first).toEqual(second);
    expect(first.nodes).toHaveLength(32);
    expect(first.edges).toHaveLength(31);
    expect(first.nodes.every((node) => node.x >= 0 && node.y >= 0)).toBe(true);
    expect(first.edges.every((edge) => edge.path.startsWith("M "))).toBe(true);
  });

  it.each([100, 300, 500])("lays out %i nodes within the UX4 budget", (size) => {
    const started = performance.now();
    const result = layoutOntologyGraph(snapshot(size), "layered");
    const elapsed = performance.now() - started;
    console.info(`[O1-UX4 benchmark] ${size} nodes: ${elapsed.toFixed(3)}ms`);
    expect(result.nodes).toHaveLength(size);
    expect(result.edges).toHaveLength(size - 1);
    expect(elapsed).toBeLessThan(500);
  });

  it("keeps object type colors stable", () => {
    expect(stableObjectTypeColor("Order")).toBe(stableObjectTypeColor("Order"));
    expect(stableObjectTypeColor("Order")).not.toBe(stableObjectTypeColor("Payment"));
  });
});
