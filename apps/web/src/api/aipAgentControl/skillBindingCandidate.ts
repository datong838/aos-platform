/** A read-only product candidate. The binding Owner repeats every check on POST. */
type Tenant = { orgId: string; projectId: string };
type Ref = { assetType: string; assetId: string; revision: number; contentHash: string };
type ShortSkill = { skillId: string; revision: number; contentHash: string; lifecycle: string };
type RoleItem = {
  instance: { tenant: Tenant; instanceId: string; status: string } | null;
  skills: ShortSkill[];
};
type PublishedSkill = {
  tenant: Tenant; skillId: string; revision: number; contentHash: string;
  lifecycle: string; publicationTenant: Tenant | null;
  modelRouteRef: Ref | null; runtimePolicyRef: Ref | null; releaseGateRef: Ref | null;
  requiredCapabilities: string[];
};
type Policy = {
  tenant: Tenant; policyId: string; revision: number; contentHash: string;
  lifecycle: string; budgetPolicyRef: Ref | null;
} | null;
type CapabilityBinding = {
  tenant: Tenant; bindingId: string; capability: Ref; status: string; health: string;
  operationalReadiness: string; dependencySnapshotHash: string | null;
  readinessExpiresAt: string | null;
};
type ExistingSkillBinding = {
  tenant: Tenant; instanceId: string; skill: Ref; status: string;
};
type Snapshot = {
  tenant: Tenant; capabilityBindings: CapabilityBinding[]; skillBindings: ExistingSkillBinding[];
};
export type SkillBindingCreateCandidate = {
  instanceId: string; skill: Ref; capabilityBindingIds: string[];
  budgetPolicyRef: Ref; initialStatus: "provisioning";
};
export type SkillBindingCandidateResult = {
  candidate: SkillBindingCreateCandidate | null; blockers: string[];
};

function sameTenant(left: Tenant | null | undefined, right: Tenant): boolean {
  return left?.orgId === right.orgId && left.projectId === right.projectId;
}

function exactRef(value: Ref | null | undefined, kind: string): value is Ref {
  return value?.assetType === kind && typeof value.assetId === "string" && !!value.assetId.trim()
    && Number.isInteger(value.revision) && value.revision > 0
    && /^[0-9a-f]{64}$/.test(value.contentHash);
}

export function deriveSkillBindingCandidate(
  item: RoleItem,
  skill: PublishedSkill,
  policy: Policy,
  snapshot: Snapshot,
  now = Date.now(),
): SkillBindingCandidateResult {
  const blockers: string[] = [];
  const tenant = snapshot.tenant;
  if (!sameTenant(skill.tenant, tenant) || !sameTenant(item.instance?.tenant, tenant)) {
    blockers.push("TENANT_MISMATCH");
  }
  if (!item.instance || item.instance.status === "deleted") blockers.push("AGENT_INSTANCE_UNAVAILABLE");
  const listed = item.skills.filter((value) => value.skillId === skill.skillId);
  if (listed.length !== 1 || listed[0].revision !== skill.revision
      || listed[0].contentHash !== skill.contentHash || listed[0].lifecycle !== "published") {
    blockers.push("SKILL_CATALOG_DRIFTED");
  }
  if (skill.lifecycle !== "published" || !sameTenant(skill.publicationTenant, tenant)
      || !exactRef(skill.modelRouteRef, "ModelRouteRevision")
      || !exactRef(skill.runtimePolicyRef, "RuntimePolicyRevision")
      || !exactRef(skill.releaseGateRef, "EvalGateDecision")
      || !/^[0-9a-f]{64}$/.test(skill.contentHash)) {
    blockers.push("SKILL_NOT_PUBLISHED");
  }
  if (!policy || !sameTenant(policy.tenant, tenant)
      || !exactRef(skill.runtimePolicyRef, "RuntimePolicyRevision")
      || policy.policyId !== skill.runtimePolicyRef.assetId
      || policy.revision !== skill.runtimePolicyRef.revision
      || policy.contentHash !== skill.runtimePolicyRef.contentHash
      || policy.lifecycle !== "active") {
    blockers.push("RUNTIME_POLICY_DRIFTED");
  }
  if (!exactRef(policy?.budgetPolicyRef, "BudgetPolicyRevision")) {
    blockers.push("BUDGET_POLICY_MISSING");
  }
  if (new Set(skill.requiredCapabilities).size !== skill.requiredCapabilities.length
      || skill.requiredCapabilities.some((id) => !id.trim())) {
    blockers.push("SKILL_CAPABILITY_REQUIREMENTS_INVALID");
  }
  const capabilityBindingIds: string[] = [];
  for (const capabilityId of skill.requiredCapabilities) {
    const choices = snapshot.capabilityBindings.filter((binding) =>
      sameTenant(binding.tenant, tenant) && binding.capability.assetId === capabilityId
      && exactRef(binding.capability, "CapabilityRevision")
      && binding.status === "active" && binding.health === "healthy"
      && binding.operationalReadiness === "available"
      && binding.dependencySnapshotHash !== null
      && /^[0-9a-f]{64}$/.test(binding.dependencySnapshotHash)
      && binding.readinessExpiresAt !== null
      && Number.isFinite(Date.parse(binding.readinessExpiresAt))
      && Date.parse(binding.readinessExpiresAt) > now,
    );
    if (choices.length !== 1) {
      blockers.push(`${choices.length ? "CAPABILITY_BINDING_AMBIGUOUS" : "CAPABILITY_BINDING_UNAVAILABLE"}:${capabilityId}`);
    } else if (!capabilityBindingIds.includes(choices[0].bindingId)) {
      capabilityBindingIds.push(choices[0].bindingId);
    }
  }
  if (item.instance && snapshot.skillBindings.some((binding) =>
    sameTenant(binding.tenant, tenant) && binding.instanceId === item.instance?.instanceId
    && binding.skill.assetId === skill.skillId && binding.status !== "revoked")) {
    blockers.push("SKILL_BINDING_ALREADY_EXISTS");
  }
  if (blockers.length || !item.instance || !policy || !policy.budgetPolicyRef) {
    return { candidate: null, blockers: [...new Set(blockers)] };
  }
  return {
    candidate: {
      instanceId: item.instance.instanceId,
      skill: { assetType: "SkillTemplate", assetId: skill.skillId,
        revision: skill.revision, contentHash: skill.contentHash },
      capabilityBindingIds,
      budgetPolicyRef: policy.budgetPolicyRef,
      initialStatus: "provisioning",
    },
    blockers: [],
  };
}
