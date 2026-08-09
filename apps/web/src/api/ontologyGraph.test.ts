import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./tenant", () => ({ getTenant: () => ({ orgId: "org-org", projectId: "dev-project" }) }));

import { normalizeGraphSnapshot } from "./ontologyGraph";

function snapshot() {
  return {
    scope: { orgId: "org-org", workspaceId: "dev-project" },
    sourceAuthority: "ecom_authoritative",
    graphDomain: "domain",
    schemaEtag: "schema:1",
    snapshot: { asOf: "2026-08-10T00:00:00Z", watermark: "2026-08-09T00:00:00Z" },
    nodes: [
      { key: "Order:1", objectType: "Order", objectId: "1", label: "Order · 1", depth: 0, masked: true },
      { key: "Payment:2", objectType: "Payment", objectId: "2", label: "Payment · 2", depth: 1, masked: true },
    ],
    edges: [{
      key: "edge-1", relationType: "Order.hasPayment", source: "Order:1", target: "Payment:2",
      direction: "out", graphDomain: "domain", edgeAuthority: "authoritative",
    }],
    page: { truncated: false, nextCursor: null },
    limits: { maxNodes: 100, maxHops: 2 },
  };
}

describe("normalizeGraphSnapshot", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("accepts a scoped authoritative domain snapshot", () => {
    expect(normalizeGraphSnapshot(snapshot()).edges).toHaveLength(1);
  });

  it("rejects cross-tenant and unknown authority responses", () => {
    expect(() => normalizeGraphSnapshot({ ...snapshot(), scope: { orgId: "dev-org", workspaceId: "dev-project" } }))
      .toThrow("scope");
    expect(() => normalizeGraphSnapshot({ ...snapshot(), sourceAuthority: "compat_projection" }))
      .toThrow("ecom_authoritative");
  });

  it("rejects edges with missing endpoints", () => {
    const value = snapshot();
    value.edges[0].target = "Customer:missing";
    expect(() => normalizeGraphSnapshot(value)).toThrow("edge authority");
  });
});
