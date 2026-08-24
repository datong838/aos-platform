import { describe, expect, it } from "vitest";
import type { AgentRuntimeReadinessResponse } from "../aipAgentControl";
import { projectProfessionalBindings } from "./agentReadiness";

const hash = "a".repeat(64);
const tenant = { orgId: "org-org", projectId: "dev-project" };

function readiness(): AgentRuntimeReadinessResponse {
  return {
    tenant,
    catalog: {
      tenant,
      stats: { definitionCount: 1, installedCount: 1, runnableCount: 0, skillDefinitionCount: 1, capabilityDefinitionCount: 1 },
      items: [{
        template: { templateId: "ecommerce.data_advisor", revision: 1, displayName: "数据参谋", roleKey: "data_advisor", lifecycle: "published", sourceRef: { resourceType: "SolutionPack", resourceId: "solution.ecommerce.growth", revision: "1.3.0", authority: "bundle" }, sourceLicense: "internal", manifest: { logicIds: ["D03"], responsibility: "增长方案", runtimeReadiness: "blocked", blockers: ["SKILL_BINDING_BLOCKED"] }, contentHash: hash },
        instance: { tenant, instanceId: "agent-1", instanceRef: { assetType: "AgentInstance", assetId: "agent-1", revision: 2, contentHash: hash }, template: { assetType: "AgentTemplate", assetId: "ecommerce.data_advisor", revision: 1, contentHash: hash }, status: "active", overlay: { displayName: "数据参谋", allowedCapabilityIds: [] }, version: 2, updatedAt: "2026-08-24T10:00:00Z" },
        skills: [{ skillId: "ecommerce.skill.D03", revision: 4, canonicalLogicId: "D03", lifecycle: "published", requiredCapabilities: ["strategy.plan"], riskLevel: "medium", contentHash: hash, logicRevisionRef: { assetType: "LogicRevision", assetId: "ecommerce.logic.D03", revision: 2, contentHash: hash } }],
        requiredCapabilityIds: ["strategy.plan"], runtimeReadiness: "blocked", blockers: ["SKILL_BINDING_BLOCKED"],
      }],
    },
    capabilityBindings: [],
    skillBindings: [{ tenant, bindingId: "binding-1", instanceId: "agent-1", skill: { assetType: "SkillTemplate", assetId: "ecommerce.skill.D03", revision: 4, contentHash: hash }, capabilityBindingIds: [], budgetPolicyRef: { assetType: "BudgetPolicyRevision", assetId: "budget-1", revision: 1, contentHash: hash }, dependencies: { providerRef: null, modelRouteRef: null, runtimePolicyRef: null, evalGateRef: null, evalContractRef: null, licenseEvidenceRefs: [], dataDependencyRefs: [], toolDependencyRefs: [], budgetPolicyRef: null, allowDegraded: false }, readiness: "blocked", readinessReasons: ["MODEL_ROUTE_MISSING"], dependencySnapshotHash: null, lastEvaluatedAt: "2026-08-24T10:00:00Z", readinessExpiresAt: "2026-08-24T10:05:00Z", status: "active", version: 1, createdAt: "2026-08-24T09:00:00Z", updatedAt: "2026-08-24T10:00:00Z" }],
    bindingStats: { capabilityBindingCount: 0, skillBindingCount: 1, activeCapabilityBindingCount: 0, activeSkillBindingCount: 1 },
    evaluatedAt: "2026-08-24T10:00:00Z",
  };
}

describe("Workshop professional binding projection", () => {
  it("按 Skill → Logic → 数字同事绑定输出并保留 blocker", () => {
    const projected = projectProfessionalBindings(readiness(), new Date("2026-08-24T10:01:00Z"));
    expect(projected).toHaveLength(1);
    expect(projected[0]).toMatchObject({ readiness: "blocked", skillRef: { assetId: "ecommerce.skill.D03", revision: 4 }, logicRef: { assetId: "ecommerce.logic.D03", revision: 2 }, agentInstanceRef: { assetId: "agent-1", revision: 2 }, bindingId: "binding-1", blockerCodes: expect.arrayContaining(["MODEL_ROUTE_MISSING"]) });
  });

  it("缺失 binding 或 readiness 过期时失败关闭", () => {
    const missing = readiness(); missing.skillBindings = [];
    expect(projectProfessionalBindings(missing, new Date("2026-08-24T10:01:00Z"))[0]).toMatchObject({ readiness: "blocked", blockerCodes: expect.arrayContaining(["SKILL_BINDING_MISSING"]) });
    expect(projectProfessionalBindings(readiness(), new Date("2026-08-24T10:06:00Z"))[0]).toMatchObject({ readiness: "blocked", blockerCodes: expect.arrayContaining(["SKILL_BINDING_STALE"]) });
  });
});
