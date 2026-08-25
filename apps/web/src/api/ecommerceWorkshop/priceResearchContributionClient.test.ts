import { describe, expect, it } from "vitest";
import { EcommerceWorkshopClient } from "./client";
import { parsePriceResearchContributionView } from "./parser";

const cutoff = "2026-08-25T07:00:00Z";
const blocked = { schemaVersion: "aos.ecommerce-workshop.price-research/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: cutoff, atomicSkillRefs: [], logicRef: null, primaryColleague: "数据参谋", collaboratorColleagues: ["活动策划师", "导购顾问"], latestBatch: null, blockers: ["PRICE_RESEARCH_BATCH_NOT_AVAILABLE"], allowedCommands: ["PREPARE_PRICE_RESEARCH_BATCH", "FREEZE_PRICE_RESEARCH_BATCH"], externalEffectsAllowed: false };

describe("price research contribution", () => {
  it("只调用只读 contribution route 并失败关闭", async () => { const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = []; const client = new EcommerceWorkshopClient({ fetch: async (input, init) => { calls.push({ input, init }); return new Response(JSON.stringify(blocked), { status: 200, headers: { "Content-Type": "application/json" } }); }, getBaseUrl: () => "http://example.test", getAuthHeaders: () => ({}) }); const result = await client.getPriceResearchContributionView(); expect(result.latestBatch).toBeNull(); expect(result.externalEffectsAllowed).toBe(false); expect(calls[0]?.init?.method).toBe("GET"); expect(String(calls[0]?.input)).toContain("/v1/ecommerce-workshop/views/price-governance/contributions"); });
  it("拒绝非零外部效果与伪角色", () => { expect(() => parsePriceResearchContributionView({ ...blocked, externalEffectsAllowed: true })).toThrow(); expect(() => parsePriceResearchContributionView({ ...blocked, primaryColleague: "导购顾问" })).toThrow(); });
});
