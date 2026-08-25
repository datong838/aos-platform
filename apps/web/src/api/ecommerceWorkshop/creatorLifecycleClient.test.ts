import { describe, expect, it, vi } from "vitest";
import { EcommerceWorkshopClient } from "./client";
import { parseCreatorLifecycleView } from "./parser";

const blocked = {
  schemaVersion: "aos.ecommerce-workshop.creator-lifecycle/v1",
  tenant: { orgId: "org-org", projectId: "dev-project" },
  evaluatedAt: "2026-08-25T08:00:00Z",
  latestStart: null,
  ledger: { eligibleItems: 0, lanes: 0, prepared: 0, accepted: 0, applied: 0, failed: 0, unknown: 0, disputed: 0, completed: 0 },
  contracts: [], deliveries: [], relationships: [],
  blockers: ["CREATOR_BATCH_START_NOT_AVAILABLE"],
  allowedCommands: ["START_CREATOR_BATCH_GOVERNANCE"], externalEffectsAllowed: false,
};

describe("Creator lifecycle strict client", () => {
  it("读取独立生命周期 authority 并拒绝伪外部授权", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(blocked)));
    const client = new EcommerceWorkshopClient({ fetch, getBaseUrl: () => "http://api.test", getAuthHeaders: () => ({ Authorization: "Bearer test" }) });
    await expect(client.getCreatorLifecycleView()).resolves.toMatchObject({ latestStart: null, externalEffectsAllowed: false });
    expect(fetch).toHaveBeenCalledWith("http://api.test/v1/ecommerce-workshop/views/creator-growth/lifecycle", expect.objectContaining({ method: "GET" }));
    expect(() => parseCreatorLifecycleView({ ...blocked, externalEffectsAllowed: true })).toThrow(/漂移/);
    expect(() => parseCreatorLifecycleView({ ...blocked, blockers: [] })).toThrow(/漂移/);
  });
});
