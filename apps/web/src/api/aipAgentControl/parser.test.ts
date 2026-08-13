import { describe, expect, it } from "vitest";
import { parseAgentInstances, parseCapabilities } from "./parser";

const hash = "a".repeat(64);
describe("aipAgentControl strict parser", () => {
  it("解析租户隔离的 AgentInstance", () => {
    const parsed = parseAgentInstances({ tenant:{orgId:"org-org",projectId:"dev-project"}, count:1, items:[{tenant:{orgId:"org-org",projectId:"dev-project"},instanceId:"ecommerce.data_advisor.default",instanceRef:{assetType:"AgentInstance",assetId:"x",revision:1,contentHash:hash},template:{assetType:"AgentTemplate",assetId:"ecommerce.data_advisor",revision:1,contentHash:hash},status:"provisioning",overlay:{displayName:"数据参谋",allowedCapabilityIds:[]},version:1,updatedAt:"2026-08-13T00:00:00Z"}] });
    expect(parsed.items[0].tenant.orgId).toBe("org-org");
  });
  it("拒绝未知 readiness", () => {
    expect(() => parseCapabilities({tenant:{orgId:"org-org",projectId:"dev-project"},count:1,availableCount:0,items:[{capabilityId:"copy.generate",revision:1,displayName:"文案生成",lifecycle:"published",aliases:[],riskLevel:"medium",readiness:"magic",readinessReasons:[],contentHash:hash}]})).toThrow("readiness 非法");
  });
  it("拒绝错误 hash", () => {
    expect(() => parseAgentInstances({tenant:{orgId:"o",projectId:"p"},count:1,items:[{tenant:{orgId:"o",projectId:"p"},instanceId:"x",instanceRef:{assetType:"AgentInstance",assetId:"x",revision:1,contentHash:"bad"},template:{assetType:"AgentTemplate",assetId:"x",revision:1,contentHash:hash},status:"provisioning",overlay:{displayName:null,allowedCapabilityIds:[]},version:1,updatedAt:"now"}]})).toThrow("SHA-256");
  });
});
