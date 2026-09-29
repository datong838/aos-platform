import { apiGetAuthoritative, apiPostUnqueued } from "../client";
import { getTenant } from "../tenant";
import { deriveSkillBindingEvaluationCandidate, type SkillBindingEvaluationCandidate } from "./skillBindingLifecycle";

type RecordValue = Record<string, unknown>;
type Binding = Parameters<typeof deriveSkillBindingEvaluationCandidate>[0];
type Role = { instance: Parameters<typeof deriveSkillBindingEvaluationCandidate>[3] | null };
type ShortSkill = { skillId: string; revision: number; contentHash: string; lifecycle: string };
type CandidateResult = ReturnType<typeof deriveSkillBindingEvaluationCandidate>;
type Ref = SkillBindingEvaluationCandidate["skill"];

function object(value: unknown, label: string): RecordValue {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} 格式错误`);
  return value as RecordValue;
}

function sameTenant(value: unknown): boolean {
  const row = object(value, "租户");
  const current = getTenant();
  return row.orgId === current.orgId && row.projectId === current.projectId;
}

function refEquals(value: unknown, expected: Ref): boolean {
  const row = object(value, "精确引用");
  return row.assetType === expected.assetType && row.assetId === expected.assetId
    && row.revision === expected.revision && row.contentHash === expected.contentHash;
}

function dependenciesEqual(value: unknown, expected: SkillBindingEvaluationCandidate["dependencies"]): boolean {
  const row = object(value, "评估依赖");
  return refEquals(row.modelRouteRef, expected.modelRouteRef)
    && refEquals(row.runtimePolicyRef, expected.runtimePolicyRef)
    && refEquals(row.evalGateRef, expected.evalGateRef)
    && refEquals(row.budgetPolicyRef, expected.budgetPolicyRef)
    && row.providerRef == null && row.evalContractRef == null
    && (row.licenseEvidenceRefs == null || Array.isArray(row.licenseEvidenceRefs) && row.licenseEvidenceRefs.length === 0)
    && (row.dataDependencyRefs == null || Array.isArray(row.dataDependencyRefs) && row.dataDependencyRefs.length === 0)
    && (row.toolDependencyRefs == null || Array.isArray(row.toolDependencyRefs) && row.toolDependencyRefs.length === 0)
    && (row.allowDegraded == null || row.allowDegraded === false);
}

function verifyBinding(value: unknown, candidate: SkillBindingEvaluationCandidate, expectedVersion: number,
                       expectedStatus: string): RecordValue {
  const row = object(value, "技能绑定");
  if (!sameTenant(row.tenant) || row.bindingId !== candidate.bindingId
      || row.instanceId !== candidate.instanceId || row.version !== expectedVersion
      || row.status !== expectedStatus || !refEquals(row.skill, candidate.skill)
      || !refEquals(row.budgetPolicyRef, candidate.budgetPolicyRef)
      || !Array.isArray(row.capabilityBindingIds)
      || JSON.stringify(row.capabilityBindingIds) !== JSON.stringify(candidate.capabilityBindingIds)) {
    throw new Error("技能绑定精确回读不一致");
  }
  return row;
}

function verifyReceipt(value: unknown, candidate: SkillBindingEvaluationCandidate,
                       operation: string, resourceType: string, idempotencyKey: string): string {
  const row = object(value, "技能绑定回执");
  const resultRef = object(row.resultRef, "回执目标");
  if (!sameTenant(row.tenant) || row.operation !== operation
      || row.idempotencyKey !== idempotencyKey
      || typeof row.receiptId !== "string" || !row.receiptId
      || resultRef.resourceType !== resourceType || resultRef.resourceId !== candidate.bindingId) {
    throw new Error("技能绑定回执与原命令不一致");
  }
  return row.receiptId;
}

function verifyReadiness(value: unknown, candidate: SkillBindingEvaluationCandidate): RecordValue {
  const row = object(value, "绑定预览");
  if (!dependenciesEqual(row.dependencies, candidate.dependencies)
      || typeof row.dependencySnapshotHash !== "string"
      || !/^[0-9a-f]{64}$/.test(row.dependencySnapshotHash)
      || !["available", "degraded", "disabled", "blocked", "unknown"].includes(String(row.readiness))
      || !Array.isArray(row.reasons)
      || typeof row.evaluatedAt !== "string" || !Number.isFinite(Date.parse(row.evaluatedAt))
      || typeof row.expiresAt !== "string" || !Number.isFinite(Date.parse(row.expiresAt))
      || Date.parse(row.expiresAt) <= Date.parse(row.evaluatedAt)) {
    throw new Error("绑定预览与当前精确依赖不一致");
  }
  return row;
}

export async function loadSkillBindingEvaluationCandidate(
  binding: Binding, role: Role, selected: ShortSkill,
): Promise<CandidateResult> {
  if (selected.lifecycle !== "published") return { candidate: null, blockers: ["SKILL_NOT_PUBLISHED"] };
  if (!sameTenant(binding.tenant) || !role.instance || !sameTenant(role.instance.tenant)
      || binding.skill.assetId !== selected.skillId || binding.skill.revision !== selected.revision
      || binding.skill.contentHash !== selected.contentHash) {
    throw new Error("技能绑定与当前目录精确身份或租户不一致");
  }
  const list = object(await apiGetAuthoritative<unknown>("/v1/aip/skills?lifecycle=published&limit=200"), "正式技能目录");
  if (!sameTenant(list.tenant) || !Array.isArray(list.items)
      || list.count !== list.items.length || list.items.length > 200) throw new Error("正式技能目录租户或数量不一致");
  const matches = list.items.map((item) => object(item, "技能修订")).filter((item) =>
    item.skillId === selected.skillId && item.revision === selected.revision
      && item.contentHash === selected.contentHash);
  if (matches.length !== 1) throw new Error("正式技能精确修订不存在或歧义");
  const source = matches[0];
  const policyRef = source.runtimePolicyRef;
  if (!policyRef || typeof policyRef !== "object" || Array.isArray(policyRef)) {
    return { candidate: null, blockers: ["RUNTIME_POLICY_REF_MISSING"] };
  }
  const runtimeRef = policyRef as RecordValue;
  if (runtimeRef.assetType !== "RuntimePolicyRevision" || typeof runtimeRef.assetId !== "string"
      || !runtimeRef.assetId.trim() || !Number.isInteger(runtimeRef.revision)
      || Number(runtimeRef.revision) < 1
      || typeof runtimeRef.contentHash !== "string" || !/^[0-9a-f]{64}$/.test(runtimeRef.contentHash)) {
    return { candidate: null, blockers: ["RUNTIME_POLICY_REF_INVALID"] };
  }
  const policy = object(await apiGetAuthoritative<unknown>(
    `/v1/aip/model-runtime/policies/${encodeURIComponent(runtimeRef.assetId)}?revision=${runtimeRef.revision}`,
  ), "运行策略");
  if (!sameTenant(policy.tenant)) throw new Error("运行策略租户不一致");
  return deriveSkillBindingEvaluationCandidate(binding, {
    skillId: String(source.skillId), revision: Number(source.revision),
    contentHash: String(source.contentHash), lifecycle: String(source.lifecycle),
    publicationTenant: source.publicationTenant as ReturnType<typeof getTenant> | null,
    modelRouteRef: source.modelRouteRef as Ref | null,
    runtimePolicyRef: source.runtimePolicyRef as Ref,
    releaseGateRef: source.releaseGateRef as Ref | null,
  }, {
    tenant: getTenant(), policyId: String(policy.policyId), revision: Number(policy.revision),
    contentHash: String(policy.contentHash), lifecycle: String(policy.lifecycle),
    budgetPolicyRef: policy.budgetPolicyRef as Ref | null,
  }, role.instance, getTenant());
}

export async function previewSkillBindingEvaluation(candidate: SkillBindingEvaluationCandidate): Promise<RecordValue> {
  const response = object(await apiPostUnqueued<unknown>("/v1/aip/skill-bindings/preview", {
    instanceId: candidate.instanceId, skill: candidate.skill,
    capabilityBindingIds: candidate.capabilityBindingIds,
    budgetPolicyRef: candidate.budgetPolicyRef, dependencies: candidate.dependencies,
  }, {}), "绑定预览响应");
  if (!sameTenant(response.tenant)) throw new Error("绑定预览租户不一致");
  return verifyReadiness(response.readiness, candidate);
}

export async function evaluateSkillBinding(
  candidate: SkillBindingEvaluationCandidate, previewHash: string, idempotencyKey: string,
  onBeforeSend?: () => void,
): Promise<{ version: number; receiptId: string; dependencySnapshotHash: string; readiness: string; expiresAt: string }> {
  if (!/^[0-9a-f]{64}$/.test(previewHash) || !idempotencyKey.trim()) throw new Error("预览快照或幂等键无效");
  const path = `/v1/aip/skill-bindings/${encodeURIComponent(candidate.bindingId)}`;
  const before = object(await apiGetAuthoritative<unknown>(path), "评估前绑定");
  if (before.status !== "provisioning" && before.status !== "suspended") throw new Error("绑定状态不允许评估");
  verifyBinding(before, candidate, candidate.expectedVersion, before.status);
  onBeforeSend?.();
  const response = object(await apiPostUnqueued<unknown>(`${path}/evaluate`, {
    expectedVersion: candidate.expectedVersion,
    expectedDependencySnapshotHash: previewHash,
    dependencies: candidate.dependencies,
  }, { "Idempotency-Key": idempotencyKey }), "绑定评估响应");
  if (!sameTenant(response.tenant)) throw new Error("绑定评估租户不一致");
  const version = candidate.expectedVersion + 1;
  const written = verifyBinding(response.binding, candidate, version, before.status);
  const readiness = verifyReadiness(response.readiness, candidate);
  if (!dependenciesEqual(written.dependencies, candidate.dependencies)
      || written.dependencySnapshotHash !== readiness.dependencySnapshotHash
      || written.readiness !== readiness.readiness
      || written.readinessExpiresAt !== readiness.expiresAt) throw new Error("绑定评估结果与快照不一致");
  const receiptId = verifyReceipt(response.receipt, candidate, "skill_binding.evaluate", "SkillBindingReadiness", idempotencyKey);
  const readback = verifyBinding(await apiGetAuthoritative<unknown>(path), candidate, version, before.status);
  if (readback.dependencySnapshotHash !== readiness.dependencySnapshotHash
      || readback.readiness !== readiness.readiness
      || readback.readinessExpiresAt !== readiness.expiresAt
      || !dependenciesEqual(readback.dependencies, candidate.dependencies)) throw new Error("绑定评估权威回读不一致");
  return { version, receiptId, dependencySnapshotHash: readiness.dependencySnapshotHash as string,
    readiness: readiness.readiness as string, expiresAt: readiness.expiresAt as string };
}

export async function activateSkillBinding(
  candidate: SkillBindingEvaluationCandidate, version: number, snapshotHash: string, idempotencyKey: string,
  onBeforeSend?: () => void,
): Promise<{ version: number; receiptId: string }> {
  if (!Number.isInteger(version) || version < 1 || !/^[0-9a-f]{64}$/.test(snapshotHash)
      || !idempotencyKey.trim()) throw new Error("激活版本、快照或幂等键无效");
  const path = `/v1/aip/skill-bindings/${encodeURIComponent(candidate.bindingId)}`;
  const source = object(await apiGetAuthoritative<unknown>(path), "激活前绑定");
  if (source.status !== "provisioning" && source.status !== "suspended") throw new Error("绑定状态不允许激活");
  const before = verifyBinding(source, candidate, version, source.status);
  if (before.readiness !== "available" || before.dependencySnapshotHash !== snapshotHash
      || typeof before.readinessExpiresAt !== "string" || Date.parse(before.readinessExpiresAt) <= Date.now()
      || !dependenciesEqual(before.dependencies, candidate.dependencies)) throw new Error("绑定就绪快照过期或漂移");
  onBeforeSend?.();
  const response = object(await apiPostUnqueued<unknown>(`${path}/activate`, {
    expectedVersion: version, expectedDependencySnapshotHash: snapshotHash,
    occurredAt: new Date().toISOString(),
  }, { "Idempotency-Key": idempotencyKey }), "绑定激活响应");
  if (!sameTenant(response.tenant)) throw new Error("绑定激活租户不一致");
  const nextVersion = version + 1;
  const written = verifyBinding(response.binding, candidate, nextVersion, "active");
  if (written.dependencySnapshotHash !== snapshotHash || !dependenciesEqual(written.dependencies, candidate.dependencies)) {
    throw new Error("绑定激活响应快照不一致");
  }
  const receiptId = verifyReceipt(response.receipt, candidate, "skill_binding.update", "SkillBinding", idempotencyKey);
  const readback = verifyBinding(await apiGetAuthoritative<unknown>(path), candidate, nextVersion, "active");
  if (readback.dependencySnapshotHash !== snapshotHash || !dependenciesEqual(readback.dependencies, candidate.dependencies)) {
    throw new Error("绑定激活权威回读不一致");
  }
  return { version: nextVersion, receiptId };
}

/** Read-only state aid; without the original Receipt it never clears an unknown command. */
export async function readSkillBindingForReconciliation(bindingId: string): Promise<{ status: string; version: number }> {
  if (!bindingId.trim()) throw new Error("绑定 ID 无效");
  const row = object(await apiGetAuthoritative<unknown>(
    `/v1/aip/skill-bindings/${encodeURIComponent(bindingId)}`), "绑定只读对账");
  if (!sameTenant(row.tenant) || row.bindingId !== bindingId
      || typeof row.status !== "string" || !Number.isInteger(row.version)) {
    throw new Error("绑定只读对账身份不一致");
  }
  return { status: row.status, version: row.version as number };
}
