import { describe, expect, it } from "vitest";
import { EcommerceWorkshopClient } from "./client";

const payload = { schemaVersion: "aos.ecommerce-workshop.three-module-closure/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, module: "creator", evaluatedAt: "2026-08-25T09:00:00Z", atomicSkillIds: ["creator-batch-prepare", "creator-lane-reconcile"], logicId: "ecommerce-creator-growth", primaryColleague: "达人运营官", collaboratorColleagues: ["内容官", "数据参谋"], latestClosure: null, latestUsage: null, latestEffect: null, latestHandoff: null, blockers: ["THREE_MODULE_CLOSURE_NOT_COMPILED", "THREE_MODULE_USAGE_NOT_BOUND", "THREE_MODULE_EFFECT_NOT_BOUND", "THREE_MODULE_HANDOFF_NOT_BOUND"], allowedCommands: ["COMPILE_THREE_MODULE_CLOSURE", "BIND_CANONICAL_USAGE", "BIND_CANONICAL_EFFECT_REVIEW", "BIND_CANONICAL_HANDOFF"], handoffConsumeAllowed: false, memoryPromotionAllowed: false, externalEffectsAllowed: false };
function client(body: unknown, calls: string[] = []) { return new EcommerceWorkshopClient({ getBaseUrl: () => "http://127.0.0.1:8000", getAuthHeaders: () => ({ "X-Org-Id": "org-org", "X-Project-Id": "dev-project" }), fetch: async (input) => { calls.push(String(input)); return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } }); } }); }

describe("three-module closure client", () => {
  it("保留只读空命令列表，不补成四个命令", async () => {
    const result = await client({ ...payload, allowedCommands: [] }).getThreeModuleClosureContributionView("creator");
    expect(result.allowedCommands).toEqual([]);
    expect(result.externalEffectsAllowed).toBe(false);
  });
  it("保留原正常四命令合同", async () => {
    expect((await client(payload).getThreeModuleClosureContributionView("creator")).allowedCommands).toEqual(payload.allowedCommands);
  });
  it.each([
    payload.allowedCommands.slice(0, 3), [...payload.allowedCommands].reverse(),
    ["UNKNOWN"], [payload.allowedCommands.join("|")],
    [payload.allowedCommands[0], payload.allowedCommands[0], ...payload.allowedCommands.slice(2)],
  ])("拒绝部分、重排、未知或pipe拼接命令 %#", async (commands) => {
    await expect(client({ ...payload, allowedCommands: commands }).getThreeModuleClosureContributionView("creator")).rejects.toThrow(/漂移/);
  });
  it.each(["handoffConsumeAllowed", "memoryPromotionAllowed", "externalEffectsAllowed"])("空列表不能绕过禁止标志 %s", async (flag) => {
    await expect(client({ ...payload, allowedCommands: [], [flag]: true }).getThreeModuleClosureContributionView("creator")).rejects.toThrow(/漂移/);
  });
  it("只读列表仍拒绝跨租户及隐私内容", async () => {
    await expect(client({ ...payload, allowedCommands: [], tenant: { ...payload.tenant, orgId: "foreign" } }).getThreeModuleClosureContributionView("creator")).rejects.toThrow(/漂移/);
    await expect(client({ ...payload, allowedCommands: [], blockers: ["mobile"] }).getThreeModuleClosureContributionView("creator")).rejects.toThrow(/PII/);
  });
  it("按 Module 读取五轴贡献且无动作权限", async () => { const calls: string[] = []; const result = await client(payload, calls).getThreeModuleClosureContributionView("creator"); expect(result.module).toBe("creator"); expect(result.handoffConsumeAllowed).toBe(false); expect(result.memoryPromotionAllowed).toBe(false); expect(calls[0]).toContain("/views/creator/closure-contributions"); });
  it("拒绝 Module 与路径期望漂移", async () => { await expect(client({ ...payload, module: "price" }).getThreeModuleClosureContributionView("creator")).rejects.toThrow(/module|漂移/); });
  it("拒绝 unknown usage 伪造 0", async () => { const exact = { resourceType: "ThreeModuleClosureRevision", resourceId: "closure-1", revision: 1, contentHash: `sha256:${"a".repeat(64)}`, receiptId: "receipt-closure-1" }; const latestUsage = { tenant: payload.tenant, bindingId: "usage-binding-1", revision: 1, closureRef: exact, usageReceiptRef: { ...exact, resourceType: "UsageReceipt", resourceId: "usage-1", receiptId: "usage-1" }, lineageId: "server-lineage", quality: "unknown", quantity: 0, unit: "tokens", adjustmentTotal: 0, settlement: "unknown", contentHash: "b".repeat(64), boundAt: payload.evaluatedAt }; await expect(client({ ...payload, latestUsage }).getThreeModuleClosureContributionView("creator")).rejects.toThrow(/伪 0/); });
  it("拒绝 PII 或 provider payload 泄漏", async () => { await expect(client({ ...payload, blockers: ["mobile"] }).getThreeModuleClosureContributionView("creator")).rejects.toThrow(/PII/); });
});
