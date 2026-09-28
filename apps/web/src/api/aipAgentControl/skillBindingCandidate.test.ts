import { describe, expect, it } from "vitest";
import { deriveSkillBindingCandidate } from "./skillBindingCandidate";

const hash = "a".repeat(64);
const otherHash = "b".repeat(64);
const tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = (assetType: string, assetId: string) => ({ assetType, assetId, revision: 1, contentHash: hash });
const skill = {
  tenant, skillId: "ecommerce.skill.D01", revision: 2, contentHash: hash,
  lifecycle: "published", publicationTenant: tenant,
  modelRouteRef: ref("ModelRouteRevision", "route"),
  runtimePolicyRef: ref("RuntimePolicyRevision", "policy"),
  releaseGateRef: ref("EvalGateDecision", "gate"),
  requiredCapabilities: ["data.query"],
};
const item = {
  template: { templateId: "ecommerce.data_advisor" },
  instance: { tenant, instanceId: "ecommerce.data_advisor.default", status: "provisioning" },
  skills: [{ skillId: skill.skillId, revision: 2, contentHash: hash, lifecycle: "published" }],
};
const policy = {
  tenant, policyId: "policy", revision: 1, contentHash: hash,
  lifecycle: "active", budgetPolicyRef: ref("BudgetPolicyRevision", "budget"),
};
const capability = {
  tenant, bindingId: "cap-data", capability: ref("CapabilityRevision", "data.query"),
  status: "active", health: "healthy", operationalReadiness: "available", dependencySnapshotHash: otherHash,
  readinessExpiresAt: "2099-01-01T00:00:00Z",
};
const snapshot = { tenant, capabilityBindings: [capability], skillBindings: [] };

describe("BG-00f exact SkillBinding candidate", () => {
  it("derives a provisioning request only from same-tenant published exact sources", () => {
    const result = deriveSkillBindingCandidate(item, skill, policy, snapshot, Date.parse("2026-09-28T15:00:00Z"));
    expect(result.blockers).toEqual([]);
    expect(result.candidate).toEqual({
      instanceId: "ecommerce.data_advisor.default",
      skill: { ...ref("SkillTemplate", "ecommerce.skill.D01"), revision: 2 },
      capabilityBindingIds: ["cap-data"], budgetPolicyRef: ref("BudgetPolicyRevision", "budget"),
      initialStatus: "provisioning",
    });
  });

  it("keeps current evaluated D01 closed without a published revision", () => {
    const result = deriveSkillBindingCandidate(item, { ...skill, lifecycle: "evaluated" }, policy, snapshot);
    expect(result.candidate).toBeNull();
    expect(result.blockers).toContain("SKILL_NOT_PUBLISHED");
  });

  it("rejects tenant drift, exact policy drift and missing budget authority", () => {
    expect(deriveSkillBindingCandidate(item, { ...skill, publicationTenant: { orgId: "dev-org", projectId: "dev-project" } }, policy, snapshot).candidate).toBeNull();
    expect(deriveSkillBindingCandidate(item, skill, { ...policy, contentHash: otherHash }, snapshot).blockers).toContain("RUNTIME_POLICY_DRIFTED");
    expect(deriveSkillBindingCandidate(item, skill, { ...policy, budgetPolicyRef: null }, snapshot).blockers).toContain("BUDGET_POLICY_MISSING");
  });

  it("rejects ambiguous, stale or cross-tenant capability bindings", () => {
    expect(deriveSkillBindingCandidate(item, skill, policy, { ...snapshot, capabilityBindings: [capability, { ...capability, bindingId: "cap-data-2" }] }).blockers).toContain("CAPABILITY_BINDING_AMBIGUOUS:data.query");
    expect(deriveSkillBindingCandidate(item, skill, policy, { ...snapshot, capabilityBindings: [{ ...capability, readinessExpiresAt: "2026-01-01T00:00:00Z" }] }).candidate).toBeNull();
    expect(deriveSkillBindingCandidate(item, skill, policy, { ...snapshot, capabilityBindings: [{ ...capability, health: "degraded" }] }).candidate).toBeNull();
    expect(deriveSkillBindingCandidate(item, skill, policy, { ...snapshot, capabilityBindings: [{ ...capability, tenant: { orgId: "dev-org", projectId: "dev-project" } }] }).candidate).toBeNull();
  });

  it("does not offer a second binding for the same instance and Skill", () => {
    const existing = { tenant, instanceId: item.instance.instanceId, skill: { ...ref("SkillTemplate", skill.skillId), revision: 2 }, status: "provisioning" };
    expect(deriveSkillBindingCandidate(item, skill, policy, { ...snapshot, skillBindings: [existing] }).blockers).toContain("SKILL_BINDING_ALREADY_EXISTS");
  });
});
