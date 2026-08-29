import { describe, expect, it } from "vitest";
import { EcommerceWorkshopClient } from "./client";

const cutoff = "2026-08-24T08:00:00Z";
const blocker = { code: "CUSTOMER_AUTHORITY_NOT_AVAILABLE", dependency: "customer", requiredAction: "attach exact privacy-safe authority" };
const payload = { schemaVersion: "aos.ecommerce-workshop.customer-view/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, resourceRevision: 3, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded", views: ["customer", "segment", "journey", "dialogue"].map((viewId) => ({ viewId, status: "blocked", resourceRevision: 3, dataCutoff: cutoff, readinessAxes: ["customer_lite", "consent", "segment", "journey", "dialogue", "outreach_batch"].map((axis) => ({ axis, status: "blocked", exactRef: null, blockers: [blocker] })), items: [], authorityRefs: [], blockers: [{ ...blocker, code: `CUSTOMER_${viewId.toUpperCase()}_AUTHORITY_NOT_AVAILABLE` }], countLedger: { input: 0, eligible: 0, excluded: 0, unknown: 0, deduplicated: 0 } })), page: { limit: 100, count: 0, hasMore: false, nextCursor: null } };

describe("customer strict client", () => {
  it("只调用 tenant-scoped GET 并保留四视图六轴", async () => { const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = []; const client = new EcommerceWorkshopClient({ fetch: async (input, init) => { calls.push({ input, init }); return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } }); }, getBaseUrl: () => "http://example.test", getAuthHeaders: () => ({}) }); const result = await client.getCustomerView(); expect(result.views).toHaveLength(4); expect(result.views[0]?.readinessAxes).toHaveLength(6); expect(calls[0]?.init?.method).toBe("GET"); expect(String(calls[0]?.input)).toContain("/v1/ecommerce-workshop/views/customer"); });
  it("接受正式来源计数但在同意条件不足时不披露客户条目", async () => {
    const countOnly: Record<string, any> = structuredClone(payload);
    const ref = { resourceType: "CustomerLiteProjection", resourceId: "P08-customer-lite-qyh", revision: 29799420, contentHash: `sha256:${"b".repeat(64)}`, receiptId: "scr-natural-cron" };
    for (const view of countOnly.views) {
      view.readinessAxes[0] = { axis: "customer_lite", status: "ready", exactRef: ref, blockers: [] };
      view.authorityRefs = [ref];
      view.countLedger = { input: 54, eligible: 0, excluded: 0, unknown: 54, deduplicated: 0 };
    }
    const client = new EcommerceWorkshopClient({ fetch: async () => new Response(JSON.stringify(countOnly), { status: 200, headers: { "Content-Type": "application/json" } }), getBaseUrl: () => "http://example.test", getAuthHeaders: () => ({}) });
    const result = await client.getCustomerView();
    expect(result.views[0]?.countLedger).toEqual({ input: 54, eligible: 0, excluded: 0, unknown: 54, deduplicated: 0 });
    expect(result.views[0]?.items).toEqual([]);
  });
  it("拒绝将未知同意状态计入 eligible", async () => { const drift: Record<string, any> = structuredClone(payload); const ref = { resourceType: "CustomerLiteRevision", resourceId: "customer-ref-1", revision: 1, contentHash: `sha256:${"a".repeat(64)}`, receiptId: "receipt-1" }; drift.views[0]!.items = [{ customerRef: ref, purpose: "retention", disclosure: "unknown", freshness: "fresh", quality: "pass", consent: "unknown", retention: "active", kAnonymitySatisfied: null, originalRefs: [], blockers: [blocker] }]; drift.views[0]!.countLedger = { input: 1, eligible: 1, excluded: 0, unknown: 0, deduplicated: 0 }; drift.page.count = 1; const client = new EcommerceWorkshopClient({ fetch: async () => new Response(JSON.stringify(drift), { status: 200, headers: { "Content-Type": "application/json" } }), getBaseUrl: () => "http://example.test", getAuthHeaders: () => ({}) }); await expect(client.getCustomerView()).rejects.toThrow(); });
});
