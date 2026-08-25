import { describe, expect, it, vi } from "vitest";
import { EcommerceWorkshopClient } from "./client";
import { parseCreatorContributionView } from "./parser";

const cutoff = "2026-08-25T05:00:00Z";
const blocked = {
  schemaVersion: "aos.ecommerce-workshop.creator-prepare/v1",
  tenant: { orgId: "org-org", projectId: "dev-project" },
  evaluatedAt: cutoff,
  atomicSkillRefs: [], logicRef: null, primaryColleague: "导购顾问",
  collaboratorColleagues: ["数据参谋", "内容官", "活动策划师"], latestBatch: null,
  blockers: ["CREATOR_BATCH_PREPARATION_NOT_AVAILABLE"],
  allowedCommands: ["PREPARE_CREATOR_BATCH", "FREEZE_CREATOR_BATCH"], externalEffectsAllowed: false,
};

describe("Creator contribution strict client", () => {
  it("uses the canonical GET and rejects any external-effect flag", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(blocked)));
    const client = new EcommerceWorkshopClient({ fetch, getBaseUrl: () => "http://api.test", getAuthHeaders: () => ({ Authorization: "Bearer test" }) });
    await expect(client.getCreatorContributionView()).resolves.toMatchObject({ primaryColleague: "导购顾问", externalEffectsAllowed: false });
    expect(fetch).toHaveBeenCalledWith("http://api.test/v1/ecommerce-workshop/views/creator-growth/contributions", expect.objectContaining({ method: "GET" }));
    expect(() => parseCreatorContributionView({ ...blocked, externalEffectsAllowed: true })).toThrow(/漂移/);
  });
});
