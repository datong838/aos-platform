import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../client", () => ({ apiGetAuthoritative: vi.fn(), apiPostUnqueued: vi.fn() }));
vi.mock("../tenant", () => ({ getTenant: () => ({ orgId: "org-org", projectId: "dev-project" }) }));
import { apiGetAuthoritative, apiPostUnqueued } from "../client";
import { createProvisioningSkillBinding, loadSkillBindingCandidate } from "./skillBindingProduct";

const hash = "a".repeat(64);
const tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = (assetType: string, assetId: string) => ({ assetType, assetId, revision: 1, contentHash: hash });
const skill = {
  skillId: "ecommerce.skill.D01", revision: 2, contentHash: hash, lifecycle: "published",
  publicationTenant: tenant, modelRouteRef: ref("ModelRouteRevision", "route"),
  runtimePolicyRef: ref("RuntimePolicyRevision", "policy"), releaseGateRef: ref("EvalGateDecision", "gate"),
  requiredCapabilities: [],
};
const role = { instance: { tenant, instanceId: "ecommerce.data_advisor.default", status: "provisioning" }, skills: [skill] };
const snapshot = { tenant, capabilityBindings: [], skillBindings: [] };
const policy = { tenant, policyId: "policy", revision: 1, contentHash: hash, lifecycle: "active", budgetPolicyRef: ref("BudgetPolicyRevision", "budget") };

describe("SkillBinding product source and command", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("returns no candidate for the current evaluated D01 without querying a policy or writing", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValue({ tenant, items: [], count: 0 });
    const result = await loadSkillBindingCandidate(role, { ...skill, revision: 1, lifecycle: "evaluated" }, snapshot);
    expect(result.candidate).toBeNull();
    expect(result.blockers).toContain("SKILL_NOT_PUBLISHED");
    expect(apiGetAuthoritative).not.toHaveBeenCalled();
    expect(apiPostUnqueued).not.toHaveBeenCalled();
  });

  it("reads exact published Skill and policy before forming the Owner request", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce({ tenant, items: [skill], count: 1 }).mockResolvedValueOnce(policy);
    const result = await loadSkillBindingCandidate(role, skill, snapshot);
    expect(result.blockers).toEqual([]);
    expect(result.candidate?.budgetPolicyRef).toEqual(ref("BudgetPolicyRevision", "budget"));
    expect(vi.mocked(apiGetAuthoritative).mock.calls.map(([path]) => path)).toEqual([
      "/v1/aip/skills?lifecycle=published&limit=200", "/v1/aip/model-runtime/policies/policy?revision=1",
    ]);
  });

  it("fails closed on tenant or published source drift", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce({ tenant: { orgId: "dev-org", projectId: "dev-project" }, items: [skill], count: 1 });
    await expect(loadSkillBindingCandidate(role, skill, snapshot)).rejects.toThrow(/租户/);
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce({ tenant, items: [{ ...skill, contentHash: "b".repeat(64) }], count: 1 });
    await expect(loadSkillBindingCandidate(role, skill, snapshot)).rejects.toThrow(/修订/);
    expect(apiPostUnqueued).not.toHaveBeenCalled();
  });

  it("requires same-tenant exact Binding and Receipt readback after one unqueued POST", async () => {
    const candidate = { instanceId: role.instance.instanceId, skill: { ...ref("SkillTemplate", skill.skillId), revision: 2 }, capabilityBindingIds: [], budgetPolicyRef: ref("BudgetPolicyRevision", "budget"), initialStatus: "provisioning" as const };
    const binding = { tenant, bindingId: "binding-new", ...candidate, status: "provisioning", version: 1 };
    const receipt = { tenant, receiptId: "receipt-1", operation: "skill_binding.create", resultRef: { resourceType: "SkillBinding", resourceId: "binding-new" } };
    vi.mocked(apiPostUnqueued).mockResolvedValue({ tenant, binding, receipt });
    vi.mocked(apiGetAuthoritative).mockResolvedValue(binding);
    const result = await createProvisioningSkillBinding(candidate, "binding-new", "key-1");
    expect(result.receiptId).toBe("receipt-1");
    expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
    expect(apiPostUnqueued).toHaveBeenCalledWith("/v1/aip/skill-bindings", { bindingId: "binding-new", ...candidate }, { "Idempotency-Key": "key-1" });
    expect(apiGetAuthoritative).toHaveBeenCalledWith("/v1/aip/skill-bindings/binding-new");
    vi.mocked(apiPostUnqueued).mockResolvedValue({ tenant, binding: { ...binding, skill: { ...candidate.skill, contentHash: "b".repeat(64) } }, receipt });
    await expect(createProvisioningSkillBinding(candidate, "binding-new", "key-2")).rejects.toThrow(/回读/);
  });
});
