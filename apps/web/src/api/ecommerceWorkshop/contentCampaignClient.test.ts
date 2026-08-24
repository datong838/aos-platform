import { describe, expect, it, vi } from "vitest";

import { EcommerceWorkshopClient } from "./client";

describe("ContentCampaign client", () => {
  it("只发送 canonical GET 且严格解析可信空三切片", async () => {
    const cutoff = "2026-08-24T13:00:00Z";
    const payload = { schemaVersion: "aos.ecommerce-workshop.content-campaign-view/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded", slices: (["plan", "calendar", "content"] as const).map((sliceId) => ({ sliceId, status: "ready", dataCutoff: cutoff, authorityRefs: [], items: [], blockers: [], countLedger: { eligible: 0, attached: 0, unmatched: 0, conflicted: 0 } })), page: { limit: 100, count: 0, hasMore: false, nextCursor: null } };
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = new EcommerceWorkshopClient({ fetch, getBaseUrl: () => "http://api.test", getAuthHeaders: () => ({ Authorization: "Bearer test" }) });
    await expect(client.getContentCampaignView()).resolves.toMatchObject({ page: { count: 0 }, slices: [{ sliceId: "plan" }, { sliceId: "calendar" }, { sliceId: "content" }] });
    expect(fetch).toHaveBeenCalledWith("http://api.test/v1/ecommerce-workshop/views/content-campaign", expect.objectContaining({ method: "GET", headers: expect.objectContaining({ Authorization: "Bearer test" }) }));
  });
});
