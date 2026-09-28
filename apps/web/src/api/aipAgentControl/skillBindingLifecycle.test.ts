import { describe, expect, it } from "vitest";
import { deriveSkillBindingEvaluationCandidate } from "./skillBindingLifecycle";

const hash = "a".repeat(64);
const otherHash = "b".repeat(64);
const tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = (assetType: string, assetId: string) => ({ assetType, assetId, revision: 1, contentHash: hash });
const skill = {
  skillId: "ecommerce.skill.D01", revision: 2, contentHash: hash,
  lifecycle: "published", publicationTenant: tenant,
  modelRouteRef: ref("ModelRouteRevision", "route"),
  runtimePolicyRef: ref("RuntimePolicyRevision", "policy"),
  releaseGateRef: ref("EvalGateDecision", "gate"),
};
const policy = {
  tenant, policyId: "policy", revision: 1, contentHash: hash,
  lifecycle: "active", budgetPolicyRef: ref("BudgetPolicyRevision", "budget"),
};
const binding = {
  tenant, bindingId: "binding-d01", instanceId: "ecommerce.data_advisor.default",
  skill: { ...ref("SkillTemplate", skill.skillId), revision: 2 },
  capabilityBindingIds: ["cap-data"], budgetPolicyRef: ref("BudgetPolicyRevision", "budget"),
  status: "provisioning", version: 1,
};
const instance = { tenant, instanceId: binding.instanceId, status: "active" };

describe("BG-00g exact SkillBinding lifecycle candidate", () => {
  it("compiles only the four refs accepted by the existing Owner", () => {
    const result = deriveSkillBindingEvaluationCandidate(binding, skill, policy, instance, tenant);
    expect(result.blockers).toEqual([]);
    expect(result.candidate).toEqual({
      bindingId: "binding-d01", instanceId: binding.instanceId, expectedVersion: 1,
      skill: binding.skill, capabilityBindingIds: ["cap-data"], budgetPolicyRef: binding.budgetPolicyRef,
      dependencies: {
        modelRouteRef: skill.modelRouteRef, runtimePolicyRef: skill.runtimePolicyRef,
        evalGateRef: skill.releaseGateRef, budgetPolicyRef: binding.budgetPolicyRef,
      },
    });
  });

  it("rejects current evaluated D01, cross-tenant and inactive instance", () => {
    expect(deriveSkillBindingEvaluationCandidate(binding, { ...skill, lifecycle: "evaluated" }, policy, instance, tenant).candidate).toBeNull();
    expect(deriveSkillBindingEvaluationCandidate(binding, { ...skill, publicationTenant: { orgId: "dev-org", projectId: "dev-project" } }, policy, instance, tenant).candidate).toBeNull();
    expect(deriveSkillBindingEvaluationCandidate(binding, skill, policy, { ...instance, status: "provisioning" }, tenant).candidate).toBeNull();
  });

  it("rejects exact Skill, policy, budget and version drift", () => {
    expect(deriveSkillBindingEvaluationCandidate({ ...binding, skill: { ...binding.skill, contentHash: otherHash } }, skill, policy, instance, tenant).candidate).toBeNull();
    expect(deriveSkillBindingEvaluationCandidate(binding, skill, { ...policy, contentHash: otherHash }, instance, tenant).candidate).toBeNull();
    expect(deriveSkillBindingEvaluationCandidate(binding, skill, { ...policy, budgetPolicyRef: ref("BudgetPolicyRevision", "other") }, instance, tenant).candidate).toBeNull();
    expect(deriveSkillBindingEvaluationCandidate({ ...binding, version: 0 }, skill, policy, instance, tenant).candidate).toBeNull();
  });
});
