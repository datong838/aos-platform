import { describe, expect, it } from "vitest";
import {
  parseAgentCatalog,
  parseAgentInstances,
  parseCapabilities,
  parseInstall,
  parseRuntimeReadiness,
} from "./parser";

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

  it("拒绝顶层和嵌套额外字段", () => {
    expect(() => parseCapabilities({tenant:{orgId:"org-org",projectId:"dev-project"},count:0,availableCount:0,items:[],unexpected:true})).toThrow("额外字段");
    expect(() => parseAgentInstances({tenant:{orgId:"org-org",projectId:"dev-project",unexpected:true},count:0,items:[]})).toThrow("额外字段");
  });

  it("拒绝响应租户与当前工作区不一致", () => {
    expect(() => parseRuntimeReadiness({
      tenant:{orgId:"dev-org",projectId:"dev-project"},
      catalog:{tenant:{orgId:"dev-org",projectId:"dev-project"},items:[],stats:{definitionCount:0,installedCount:0,runnableCount:0,skillDefinitionCount:0,capabilityDefinitionCount:0}},
      capabilityBindings:[],skillBindings:[],
      bindingStats:{capabilityBindingCount:0,skillBindingCount:0,activeCapabilityBindingCount:0,activeSkillBindingCount:0},
      evaluatedAt:"2026-08-15T06:00:00Z",
    }, {orgId:"org-org",projectId:"dev-project"})).toThrow("tenant echo 不一致");
  });

  it("严格解析 runtime readiness 聚合空态", () => {
    const catalog = {tenant:{orgId:"org-org",projectId:"dev-project"},items:[],stats:{definitionCount:6,installedCount:6,runnableCount:0,skillDefinitionCount:37,capabilityDefinitionCount:10}};
    const parsed = parseRuntimeReadiness({
      tenant:{orgId:"org-org",projectId:"dev-project"},catalog,
      capabilityBindings:[],skillBindings:[],
      bindingStats:{capabilityBindingCount:0,skillBindingCount:0,activeCapabilityBindingCount:0,activeSkillBindingCount:0},
      evaluatedAt:"2026-08-15T06:00:00Z",
    }, {orgId:"org-org",projectId:"dev-project"});
    expect(parsed.catalog.stats.skillDefinitionCount).toBe(37);
    expect(parsed.bindingStats.activeCapabilityBindingCount).toBe(0);
  });

  it("catalog 顶层同样执行 exact-key", () => {
    expect(() => parseAgentCatalog({tenant:{orgId:"org-org",projectId:"dev-project"},items:[],stats:{definitionCount:0,installedCount:0,runnableCount:0,skillDefinitionCount:0,capabilityDefinitionCount:0},shadow:"mock"})).toThrow("额外字段");
  });

  it("catalog 允许真实 runnableCount 与 runtimeReadiness=runnable", () => {
    const catalog = {tenant:{orgId:"org-org",projectId:"dev-project"},items:[],stats:{definitionCount:6,installedCount:6,runnableCount:1,skillDefinitionCount:37,capabilityDefinitionCount:10}};
    const parsed = parseRuntimeReadiness({
      tenant:{orgId:"org-org",projectId:"dev-project"},catalog,
      capabilityBindings:[],skillBindings:[],
      bindingStats:{capabilityBindingCount:1,skillBindingCount:1,activeCapabilityBindingCount:1,activeSkillBindingCount:1},
      evaluatedAt:"2026-08-18T13:34:01Z",
    }, {orgId:"org-org",projectId:"dev-project"});
    expect(parsed.catalog.stats.runnableCount).toBe(1);
  });

  it("安装响应保留并校验 SolutionPack 容器版本", () => {
    const payload = {tenant:{orgId:"org-org",projectId:"dev-project"},solutionPackId:"solution.ecommerce.growth",solutionPackVersion:"1.3.0",status:"installed",items:[],createdCount:0,existingCount:6,runnableCount:0};
    expect(parseInstall(payload).solutionPackVersion).toBe("1.3.0");
    expect(() => parseInstall({...payload,solutionPackVersion:"latest"})).toThrow("solutionPackVersion 非法");
    expect(() => parseInstall({...payload,runnableCount:1})).toThrow("runnableCount 必须为 0");
  });
});
