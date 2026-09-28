import { apiGetAuthoritative, apiPostUnqueued } from "../client";
import { getTenant } from "../tenant";
import { deriveSkillBindingCandidate, type SkillBindingCandidateResult, type SkillBindingCreateCandidate } from "./skillBindingCandidate";

type Role = Parameters<typeof deriveSkillBindingCandidate>[0];
type Snapshot = Parameters<typeof deriveSkillBindingCandidate>[3];
type ShortSkill = { skillId: string; revision: number; contentHash: string; lifecycle: string };
type RecordValue = Record<string, unknown>;

function object(value: unknown, label: string): RecordValue {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} 回读格式错误`);
  return value as RecordValue;
}

function sameTenant(value: unknown): boolean {
  const tenant = object(value, "租户");
  const current = getTenant();
  return tenant.orgId === current.orgId && tenant.projectId === current.projectId;
}

function exactRef(value: unknown, kind: string): value is { assetType: string; assetId: string; revision: number; contentHash: string } {
  const row = object(value, "精确引用");
  return row.assetType === kind && typeof row.assetId === "string" && !!row.assetId.trim()
    && Number.isInteger(row.revision) && Number(row.revision) > 0
    && typeof row.contentHash === "string" && /^[0-9a-f]{64}$/.test(row.contentHash);
}

function sameRef(left: unknown, right: SkillBindingCreateCandidate["skill"]): boolean {
  const ref = object(left, "绑定引用");
  return ref.assetType === right.assetType && ref.assetId === right.assetId
    && ref.revision === right.revision && ref.contentHash === right.contentHash;
}

export async function loadSkillBindingCandidate(
  role: Role, selected: ShortSkill, snapshot: Snapshot,
): Promise<SkillBindingCandidateResult> {
  if (selected.lifecycle !== "published") return { candidate: null, blockers: ["SKILL_NOT_PUBLISHED"] };
  if (!sameTenant(snapshot.tenant) || !role.instance || !sameTenant(role.instance.tenant)) {
    throw new Error("技能绑定候选租户不一致");
  }
  const response = object(await apiGetAuthoritative<unknown>("/v1/aip/skills?lifecycle=published&limit=200"), "技能目录");
  if (!sameTenant(response.tenant)) throw new Error("技能目录租户不一致");
  if (!Array.isArray(response.items) || response.count !== response.items.length || response.items.length > 200) {
    throw new Error("技能目录数量或格式不一致");
  }
  const matches = response.items.map((value) => object(value, "技能修订")).filter((value) =>
    value.skillId === selected.skillId && value.revision === selected.revision);
  if (matches.length !== 1 || matches[0].contentHash !== selected.contentHash) {
    throw new Error("技能精确修订不存在或漂移");
  }
  const source = matches[0];
  if (source.lifecycle !== "published" || !exactRef(source.runtimePolicyRef, "RuntimePolicyRevision")) {
    return { candidate: null, blockers: ["SKILL_NOT_PUBLISHED", "RUNTIME_POLICY_DRIFTED"] };
  }
  const policyRef = source.runtimePolicyRef;
  const policy = object(await apiGetAuthoritative<unknown>(
    `/v1/aip/model-runtime/policies/${encodeURIComponent(policyRef.assetId)}?revision=${policyRef.revision}`,
  ), "运行策略");
  if (!sameTenant(policy.tenant)) throw new Error("运行策略租户不一致");
  return deriveSkillBindingCandidate(role, {
    tenant: getTenant(),
    skillId: String(source.skillId), revision: Number(source.revision),
    contentHash: String(source.contentHash), lifecycle: String(source.lifecycle),
    publicationTenant: source.publicationTenant as ReturnType<typeof getTenant> | null,
    modelRouteRef: source.modelRouteRef as SkillBindingCreateCandidate["skill"] | null,
    runtimePolicyRef: policyRef,
    releaseGateRef: source.releaseGateRef as SkillBindingCreateCandidate["skill"] | null,
    requiredCapabilities: Array.isArray(source.requiredCapabilities)
      && source.requiredCapabilities.every((value) => typeof value === "string")
      ? source.requiredCapabilities as string[] : [""],
  }, {
    tenant: getTenant(), policyId: String(policy.policyId), revision: Number(policy.revision),
    contentHash: String(policy.contentHash), lifecycle: String(policy.lifecycle),
    budgetPolicyRef: policy.budgetPolicyRef as SkillBindingCreateCandidate["budgetPolicyRef"] | null,
  }, snapshot);
}

function verifyBinding(value: unknown, candidate: SkillBindingCreateCandidate, bindingId: string): void {
  const binding = object(value, "技能绑定");
  if (!sameTenant(binding.tenant) || binding.bindingId !== bindingId
      || binding.instanceId !== candidate.instanceId || binding.status !== "provisioning"
      || !sameRef(binding.skill, candidate.skill)
      || !sameRef(binding.budgetPolicyRef, candidate.budgetPolicyRef)
      || !Array.isArray(binding.capabilityBindingIds)
      || JSON.stringify(binding.capabilityBindingIds) !== JSON.stringify(candidate.capabilityBindingIds)) {
    throw new Error("技能绑定回读与提交的精确候选不一致");
  }
}

export async function createProvisioningSkillBinding(
  candidate: SkillBindingCreateCandidate, bindingId: string, idempotencyKey: string,
): Promise<{ receiptId: string }> {
  if (!bindingId.trim() || bindingId.length > 200 || !idempotencyKey.trim() || idempotencyKey.length > 120) {
    throw new Error("绑定 ID 或幂等键无效");
  }
  const response = object(await apiPostUnqueued<unknown>(
    "/v1/aip/skill-bindings", { bindingId, ...candidate }, { "Idempotency-Key": idempotencyKey },
  ), "技能绑定命令");
  if (!sameTenant(response.tenant)) throw new Error("技能绑定命令租户回读不一致");
  verifyBinding(response.binding, candidate, bindingId);
  const receipt = object(response.receipt, "技能绑定回执");
  const resultRef = object(receipt.resultRef, "技能绑定回执目标");
  if (!sameTenant(receipt.tenant) || receipt.operation !== "skill_binding.create"
      || typeof receipt.receiptId !== "string" || !receipt.receiptId
      || resultRef.resourceType !== "SkillBinding" || resultRef.resourceId !== bindingId) {
    throw new Error("技能绑定回执与提交目标不一致");
  }
  const readback = await apiGetAuthoritative<unknown>(`/v1/aip/skill-bindings/${encodeURIComponent(bindingId)}`);
  verifyBinding(readback, candidate, bindingId);
  return { receiptId: receipt.receiptId };
}
