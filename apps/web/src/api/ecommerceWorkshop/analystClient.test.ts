import { describe, expect, it } from "vitest";

import { EcommerceWorkshopClient } from "./client";

const cutoff = "2026-08-24T08:00:00Z";
const blocker = { code: "ANALYST_AUTHORITY_NOT_AVAILABLE", dependency: "metric_definition", requiredAction: "attach exact ref" };
const payload = {
  schemaVersion: "aos.ecommerce-workshop.analyst-view/v1",
  tenant: { orgId: "org-org", projectId: "dev-project" },
  resourceRevision: 3,
  evaluatedAt: cutoff,
  dataCutoff: cutoff,
  readiness: "degraded",
  views: ["overview", "drivers", "diagnosis", "plan", "effects", "evidence", "quality"].map((viewId) => ({
    viewId,
    status: "blocked",
    resourceRevision: 3,
    dataCutoff: cutoff,
    readinessAxes: ["metric_query", "model", "eval", "plan_materialization", "professional_handoff"].map((axis) => ({ axis, status: "blocked", exactRef: null, blockers: [{ ...blocker, dependency: axis }] })),
    metrics: [],
    authorityRefs: [],
    blockers: [{ ...blocker, code: `ANALYST_${viewId.toUpperCase()}_AUTHORITY_NOT_AVAILABLE` }],
    countLedger: { denominator: 0, ready: 0, unknown: 0, blocked: 0, conflict: 0 },
  })),
  page: { limit: 100, count: 0, hasMore: false, nextCursor: null },
};

describe("analyst strict client", () => {
  it("只调用 tenant-scoped GET 并保留 blocked/unknown 语义", async () => {
    const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const client = new EcommerceWorkshopClient({
      fetch: async (input, init) => { calls.push({ input, init }); return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } }); },
      getBaseUrl: () => "http://example.test",
      getAuthHeaders: () => ({}),
    });
    const result = await client.getAnalystView();
    expect(result.views).toHaveLength(7);
    expect(result.views[0]?.status).toBe("blocked");
    expect(calls[0]?.init?.method).toBe("GET");
    expect(String(calls[0]?.input)).toContain("/v1/ecommerce-workshop/views/analyst");
  });

  it("拒绝把 non-ready 指标伪装为数值 0", async () => {
    const drift: Record<string, any> = structuredClone(payload);
    drift.views[0]!.metrics = [{ metricId: "gmv", status: "unknown", definitionRef: null, observationRef: null, value: 0, unit: null, grain: null, window: null, timezone: null, cohortFilter: null, numerator: null, denominator: null, sourceRunRef: null, qualityRef: null, reconciliationRef: null, lineageId: null, blockers: [blocker] }];
    drift.views[0]!.countLedger = { denominator: 1, ready: 0, unknown: 1, blocked: 0, conflict: 0 };
    drift.page.count = 1;
    const client = new EcommerceWorkshopClient({ fetch: async () => new Response(JSON.stringify(drift), { status: 200, headers: { "Content-Type": "application/json" } }), getBaseUrl: () => "http://example.test", getAuthHeaders: () => ({}) });
    await expect(client.getAnalystView()).rejects.toThrow();
  });
});
