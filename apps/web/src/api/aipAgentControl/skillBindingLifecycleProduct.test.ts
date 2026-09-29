import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../client", () => ({ apiGetAuthoritative: vi.fn(), apiPostUnqueued: vi.fn() }));
vi.mock("../tenant", () => ({ getTenant: () => ({ orgId: "org-org", projectId: "dev-project" }) }));
import { apiGetAuthoritative, apiPostUnqueued } from "../client";
import { activateSkillBinding, evaluateSkillBinding, loadSkillBindingEvaluationCandidate, previewSkillBindingEvaluation, readSkillBindingForReconciliation } from "./skillBindingLifecycleProduct";

const hash = "a".repeat(64);
const tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = (assetType: string, assetId: string) => ({ assetType, assetId, revision: 1, contentHash: hash });
const skill = { skillId: "ecommerce.skill.D01", revision: 2, contentHash: hash, lifecycle: "published",
  publicationTenant: tenant, modelRouteRef: ref("ModelRouteRevision", "route"),
  runtimePolicyRef: ref("RuntimePolicyRevision", "policy"), releaseGateRef: ref("EvalGateDecision", "gate") };
const policy = { tenant, policyId: "policy", revision: 1, contentHash: hash,
  lifecycle: "active", budgetPolicyRef: ref("BudgetPolicyRevision", "budget") };
const binding = { tenant, bindingId: "binding-d01", instanceId: "ecommerce.data_advisor.default",
  skill: { ...ref("SkillTemplate", skill.skillId), revision: 2 }, capabilityBindingIds: ["cap-data"],
  budgetPolicyRef: ref("BudgetPolicyRevision", "budget"), status: "provisioning", version: 1,
  readiness: "unknown", dependencySnapshotHash: null, readinessExpiresAt: null };
const role = { instance: { tenant, instanceId: binding.instanceId, status: "active" }, skills: [skill] };
const candidate = { bindingId: binding.bindingId, instanceId: binding.instanceId,
  expectedVersion: 1, skill: binding.skill, capabilityBindingIds: ["cap-data"], budgetPolicyRef: binding.budgetPolicyRef,
  dependencies: { modelRouteRef: skill.modelRouteRef, runtimePolicyRef: skill.runtimePolicyRef,
    evalGateRef: skill.releaseGateRef, budgetPolicyRef: binding.budgetPolicyRef } };
const readiness = { readiness: "available", reasons: [], dependencies: candidate.dependencies,
  dependencySnapshotHash: hash, evaluatedAt: "2026-09-29T01:00:00Z", expiresAt: "2099-09-29T01:15:00Z" };
const receipt = (operation: string, resourceType: string, idempotencyKey: string) => ({ tenant, receiptId: "receipt-1", operation, idempotencyKey,
  resultRef: { resourceType, resourceId: binding.bindingId } });

describe("BG-00g SkillBinding Owner product lifecycle", () => {
  beforeEach(() => vi.clearAllMocks());

  it("keeps evaluated D01 closed before any request", async () => {
    const result = await loadSkillBindingEvaluationCandidate(binding, role, { ...skill, lifecycle: "evaluated" });
    expect(result.candidate).toBeNull();
    expect(apiGetAuthoritative).not.toHaveBeenCalled();
    expect(apiPostUnqueued).not.toHaveBeenCalled();
  });

  it("loads exact published Skill and RuntimePolicy for the current binding", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce({ tenant, items: [skill], count: 1 }).mockResolvedValueOnce(policy);
    const result = await loadSkillBindingEvaluationCandidate(binding, role, skill);
    expect(result.candidate).toEqual(candidate);
    expect(vi.mocked(apiGetAuthoritative).mock.calls.map(([path]) => path)).toEqual([
      "/v1/aip/skills?lifecycle=published&limit=200", "/v1/aip/model-runtime/policies/policy?revision=1",
    ]);
  });

  it("previews without persisting, then evaluates once with CAS and exact readback", async () => {
    vi.mocked(apiPostUnqueued).mockResolvedValueOnce({ tenant, readiness }).mockResolvedValueOnce({
      tenant, binding: { ...binding, version: 2, readiness: "available", dependencySnapshotHash: hash,
        readinessExpiresAt: readiness.expiresAt, dependencies: candidate.dependencies },
      readiness, receipt: receipt("skill_binding.evaluate", "SkillBindingReadiness", "idem-evaluate-1"),
    });
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce(binding).mockResolvedValueOnce({
      ...binding, version: 2, readiness: "available", dependencySnapshotHash: hash,
      readinessExpiresAt: readiness.expiresAt, dependencies: candidate.dependencies,
    });
    expect((await previewSkillBindingEvaluation(candidate)).dependencySnapshotHash).toBe(hash);
    const beforeSend = vi.fn();
    const evaluated = await evaluateSkillBinding(candidate, hash, "idem-evaluate-1", beforeSend);
    expect(evaluated.version).toBe(2);
    expect(beforeSend).toHaveBeenCalledTimes(1);
    expect(apiPostUnqueued).toHaveBeenCalledTimes(2);
    expect(apiPostUnqueued).toHaveBeenLastCalledWith(
      "/v1/aip/skill-bindings/binding-d01/evaluate",
      { expectedVersion: 1, expectedDependencySnapshotHash: hash, dependencies: candidate.dependencies },
      { "Idempotency-Key": "idem-evaluate-1" },
    );
  });

  it("activates only fresh exact evaluated binding and verifies update Receipt", async () => {
    const evaluated = { ...binding, version: 2, readiness: "available", dependencySnapshotHash: hash,
      readinessExpiresAt: readiness.expiresAt, dependencies: candidate.dependencies };
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce(evaluated).mockResolvedValueOnce({ ...evaluated, status: "active", version: 3 });
    vi.mocked(apiPostUnqueued).mockResolvedValueOnce({ tenant, binding: { ...evaluated, status: "active", version: 3 },
      receipt: receipt("skill_binding.update", "SkillBinding", "idem-activate-1") });
    const beforeSend = vi.fn();
    const activated = await activateSkillBinding(candidate, 2, hash, "idem-activate-1", beforeSend);
    expect(activated.version).toBe(3);
    expect(beforeSend).toHaveBeenCalledTimes(1);
    expect(apiPostUnqueued).toHaveBeenCalledWith("/v1/aip/skill-bindings/binding-d01/activate",
      { expectedVersion: 2, expectedDependencySnapshotHash: hash, occurredAt: expect.any(String) },
      { "Idempotency-Key": "idem-activate-1" });
  });

  it("accepts the Owner's suspended to active transition after fresh readback", async () => {
    const suspended = { ...binding, status: "suspended", version: 2, readiness: "available",
      dependencySnapshotHash: hash, readinessExpiresAt: readiness.expiresAt, dependencies: candidate.dependencies };
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce(suspended)
      .mockResolvedValueOnce({ ...suspended, status: "active", version: 3 });
    vi.mocked(apiPostUnqueued).mockResolvedValueOnce({ tenant,
      binding: { ...suspended, status: "active", version: 3 },
      receipt: receipt("skill_binding.update", "SkillBinding", "idem-resume-1") });
    expect((await activateSkillBinding(candidate, 2, hash, "idem-resume-1")).version).toBe(3);
  });

  it("never writes when prior binding is stale or cross-tenant", async () => {
    const beforeSend = vi.fn();
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce({ ...binding, tenant: { orgId: "dev-org", projectId: "dev-project" } });
    await expect(evaluateSkillBinding(candidate, hash, "idem-evaluate-2", beforeSend)).rejects.toThrow(/租户|精确/);
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce({ ...binding, version: 2, readiness: "available",
      status: "provisioning",
      dependencySnapshotHash: hash, readinessExpiresAt: "2026-01-01T00:00:00Z", dependencies: candidate.dependencies });
    await expect(activateSkillBinding(candidate, 2, hash, "idem-activate-2", beforeSend)).rejects.toThrow(/过期/);
    expect(beforeSend).not.toHaveBeenCalled();
    expect(apiPostUnqueued).not.toHaveBeenCalled();
  });

  it("does not send when the durable unknown-result marker cannot be stored", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce(binding);
    await expect(evaluateSkillBinding(candidate, hash, "idem-marker-failed", () => {
      throw new Error("marker unavailable");
    })).rejects.toThrow(/marker unavailable/);
    expect(apiPostUnqueued).not.toHaveBeenCalled();
  });

  it("supports read-only unknown-result reconciliation without clearing the original key", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce(binding);
    expect(await readSkillBindingForReconciliation(binding.bindingId)).toEqual({ status: "provisioning", version: 1 });
    expect(apiPostUnqueued).not.toHaveBeenCalled();
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce({ ...binding, tenant: { orgId: "dev-org", projectId: "dev-project" } });
    await expect(readSkillBindingForReconciliation(binding.bindingId)).rejects.toThrow(/身份/);
  });

  it("treats a mismatched post-write Receipt as unresolved instead of success", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce(binding);
    vi.mocked(apiPostUnqueued).mockResolvedValueOnce({ tenant,
      binding: { ...binding, version: 2, readiness: "available", dependencySnapshotHash: hash,
        readinessExpiresAt: readiness.expiresAt, dependencies: candidate.dependencies },
      readiness, receipt: receipt("skill_binding.evaluate", "SkillBindingReadiness", "different-key"),
    });
    await expect(evaluateSkillBinding(candidate, hash, "idem-evaluate-expected")).rejects.toThrow(/回执/);
    expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
  });

  it("rejects a malformed preview expiry before an evaluate command", async () => {
    vi.mocked(apiPostUnqueued).mockResolvedValueOnce({ tenant, readiness: { ...readiness, expiresAt: "not-a-date" } });
    await expect(previewSkillBindingEvaluation(candidate)).rejects.toThrow(/预览/);
    expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
  });
});
