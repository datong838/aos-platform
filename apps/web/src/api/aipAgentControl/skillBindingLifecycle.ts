/** Product-side precheck. The AIP Binding Owner repeats all authority checks. */
type Tenant = { orgId: string; projectId: string };
type Ref = { assetType: string; assetId: string; revision: number; contentHash: string };
type Binding = {
  tenant: Tenant; bindingId: string; instanceId: string; skill: Ref;
  capabilityBindingIds: string[]; budgetPolicyRef: Ref; status: string; version: number;
};
type Skill = {
  skillId: string; revision: number; contentHash: string; lifecycle: string;
  publicationTenant: Tenant | null; modelRouteRef: Ref | null;
  runtimePolicyRef: Ref | null; releaseGateRef: Ref | null;
};
type Policy = {
  tenant: Tenant; policyId: string; revision: number; contentHash: string;
  lifecycle: string; budgetPolicyRef: Ref | null;
};
type Instance = { tenant: Tenant; instanceId: string; status: string };

export type SkillBindingEvaluationCandidate = {
  bindingId: string; instanceId: string; expectedVersion: number;
  skill: Ref; capabilityBindingIds: string[]; budgetPolicyRef: Ref;
  dependencies: {
    modelRouteRef: Ref; runtimePolicyRef: Ref;
    evalGateRef: Ref; budgetPolicyRef: Ref;
  };
};

function sameTenant(left: Tenant | null | undefined, right: Tenant): boolean {
  return left?.orgId === right.orgId && left.projectId === right.projectId;
}

function exactRef(value: Ref | null | undefined, kind: string): value is Ref {
  return value?.assetType === kind && typeof value.assetId === "string" && !!value.assetId.trim()
    && Number.isInteger(value.revision) && value.revision > 0
    && typeof value.contentHash === "string" && /^[0-9a-f]{64}$/.test(value.contentHash);
}

function sameRef(left: Ref | null | undefined, right: Ref | null | undefined): boolean {
  return !!left && !!right && left.assetType === right.assetType && left.assetId === right.assetId
    && left.revision === right.revision && left.contentHash === right.contentHash;
}

export function deriveSkillBindingEvaluationCandidate(
  binding: Binding, skill: Skill, policy: Policy, instance: Instance, tenant: Tenant,
): { candidate: SkillBindingEvaluationCandidate | null; blockers: string[] } {
  const blockers: string[] = [];
  if (!sameTenant(binding.tenant, tenant) || !sameTenant(skill.publicationTenant, tenant)
      || !sameTenant(policy.tenant, tenant) || !sameTenant(instance.tenant, tenant)) {
    blockers.push("TENANT_MISMATCH");
  }
  if (binding.status !== "provisioning" && binding.status !== "suspended") blockers.push("BINDING_STATUS_NOT_EVALUABLE");
  if (!Number.isInteger(binding.version) || binding.version < 1) blockers.push("BINDING_VERSION_INVALID");
  if (!binding.bindingId.trim() || !binding.instanceId.trim() || binding.instanceId !== instance.instanceId
      || instance.status !== "active") blockers.push("AGENT_INSTANCE_NOT_ACTIVE");
  if (skill.lifecycle !== "published" || !exactRef(binding.skill, "SkillTemplate")
      || binding.skill.assetId !== skill.skillId || binding.skill.revision !== skill.revision
      || binding.skill.contentHash !== skill.contentHash) blockers.push("SKILL_EXACT_PUBLICATION_MISSING");
  if (!exactRef(skill.modelRouteRef, "ModelRouteRevision")
      || !exactRef(skill.runtimePolicyRef, "RuntimePolicyRevision")
      || !exactRef(skill.releaseGateRef, "EvalGateDecision")) blockers.push("SKILL_DEPENDENCY_REF_MISSING");
  if (!exactRef(skill.runtimePolicyRef, "RuntimePolicyRevision")
      || policy.policyId !== skill.runtimePolicyRef.assetId
      || policy.revision !== skill.runtimePolicyRef.revision
      || policy.contentHash !== skill.runtimePolicyRef.contentHash
      || policy.lifecycle !== "active") blockers.push("RUNTIME_POLICY_DRIFTED");
  if (!exactRef(binding.budgetPolicyRef, "BudgetPolicyRevision")
      || !exactRef(policy.budgetPolicyRef, "BudgetPolicyRevision")
      || !sameRef(binding.budgetPolicyRef, policy.budgetPolicyRef)) blockers.push("BUDGET_POLICY_DRIFTED");
  if (!Array.isArray(binding.capabilityBindingIds)
      || binding.capabilityBindingIds.some((id) => typeof id !== "string" || !id.trim())
      || new Set(binding.capabilityBindingIds).size !== binding.capabilityBindingIds.length) {
    blockers.push("CAPABILITY_BINDING_IDS_INVALID");
  }
  if (blockers.length || !skill.modelRouteRef || !skill.runtimePolicyRef
      || !skill.releaseGateRef) return { candidate: null, blockers };
  return {
    candidate: {
      bindingId: binding.bindingId, instanceId: binding.instanceId,
      expectedVersion: binding.version, skill: binding.skill,
      capabilityBindingIds: [...binding.capabilityBindingIds],
      budgetPolicyRef: binding.budgetPolicyRef,
      dependencies: {
        modelRouteRef: skill.modelRouteRef, runtimePolicyRef: skill.runtimePolicyRef,
        evalGateRef: skill.releaseGateRef, budgetPolicyRef: binding.budgetPolicyRef,
      },
    },
    blockers: [],
  };
}
