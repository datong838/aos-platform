import { describe, expect, it, vi } from "vitest";
import type { ExactRuntimeRef, ModelRouteRevision, RegisteredModelRevision, RuntimePolicyRevision } from "./contracts";
import { buildQyhModelDraft, buildQyhPolicyDraft, buildQyhRouteDraft, canonicalRuntimeHash, inspectQyhSuccessorDraftState, prepareQyhSuccessorDrafts, type QyhSuccessorDraftClient } from "./successorDrafts";

const H = "a".repeat(64), PAIR = "b".repeat(64);
const tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = (assetType: string, assetId: string, revision = 1, contentHash = H): ExactRuntimeRef => ({ assetType, assetId, revision, contentHash });
const pairedPolicyRef = ref("BudgetPolicyRevision", `window-policy-${PAIR}`);
const pairedPriceRef = ref("ModelPriceSnapshotRevision", `window-price-${PAIR}`);
const model: RegisteredModelRevision = { tenant, registeredModelId: "a0v-agnes-2-5-flash-readonly-dev", revision: 12, contentHash: H,
  provider: ref("ProviderInstanceRevision", "provider"), providerModelId: "agnes-2.5-flash", inputModalities: ["text"], outputModalities: ["text"], capabilities: ["chat"], contextWindow: 128000,
  quotaPolicyRef: ref("QuotaPolicyRevision", "quota"), budgetPolicyRef: ref("BudgetPolicyRevision", "old-budget"), priceSnapshotRef: ref("ModelPriceSnapshotRevision", "old-price"), evalGateRef: ref("EvalGateDecision", "gate"), lifecycle: "active", createdBy: "owner", createdAt: "2026-10-31T00:00:00Z" };
const policy: RuntimePolicyRevision = { tenant, policyId: "a0v-ecommerce-runtime-policy-v1", revision: 13, contentHash: H,
  networkPolicyRef: ref("NetworkPolicyRevision", "network"), egressPolicyRef: ref("EgressPolicyRevision", "egress"), dataClassificationPolicyRef: ref("DataClassificationPolicyRevision", "classification"), quotaPolicyRef: ref("QuotaPolicyRevision", "quota"), budgetPolicyRef: ref("BudgetPolicyRevision", "old-budget"), deadlineMs: 30000, maxAttempts: 1, allowedFallbackReasons: [], unknownUsageBehavior: "block", unknownPriceBehavior: "block", killSwitchEnabled: true, lifecycle: "active", createdBy: "owner", createdAt: "2026-10-31T00:00:00Z" };
const route: ModelRouteRevision = { tenant, routeId: "a0v-ecommerce-text-readonly-v1", revision: 12, contentHash: H,
  taskTypes: ["copy.generate"], requiredInputModality: "text", requiredOutputModality: "text", requiredCapabilities: ["chat"], candidates: [{ model: ref("RegisteredModelRevision", model.registeredModelId, model.revision), weight: 100 }], strategy: "failover", runtimePolicyRef: ref("RuntimePolicyRevision", policy.policyId, policy.revision), evalGateRef: ref("EvalGateDecision", "gate"), lifecycle: "active", createdBy: "owner", createdAt: "2026-10-31T00:00:00Z" };

async function drafts() {
  const nextModel = await buildQyhModelDraft(model, pairedPolicyRef, pairedPriceRef, "2026-10-31T01:00:00Z");
  const nextPolicy = await buildQyhPolicyDraft(policy, pairedPolicyRef, "2026-10-31T01:00:00Z");
  const nextRoute = await buildQyhRouteDraft(route, nextModel, nextPolicy, "2026-10-31T01:00:00Z");
  return { nextModel, nextPolicy, nextRoute };
}

function clientFactory(options: { modelPost?: "success" | "unknown_after_write" | "unknown_without_write" } = {}) {
  let currentModel = structuredClone(model), currentPolicy = structuredClone(policy), currentRoute = structuredClone(route);
  const client: QyhSuccessorDraftClient = {
    model: vi.fn(async (_id: string, revision?: number) => revision === model.revision ? model : currentModel),
    policy: vi.fn(async (_id: string, revision?: number) => revision === policy.revision ? policy : currentPolicy),
    route: vi.fn(async (_id: string, revision?: number) => revision === route.revision ? route : currentRoute),
    publishModel: vi.fn(async (item) => {
      if (options.modelPost === "unknown_without_write") throw new Error("network unknown");
      currentModel = structuredClone(item);
      if (options.modelPost === "unknown_after_write") throw new Error("network unknown");
      return currentModel;
    }),
    publishPolicy: vi.fn(async (item) => { currentPolicy = structuredClone(item); return currentPolicy; }),
    publishRoute: vi.fn(async (item) => { currentRoute = structuredClone(item); return currentRoute; }),
  };
  return client;
}

describe("QYH successor drafts", () => {
  it("matches the server canonical JSON SHA-256 vector", async () => {
    await expect(canonicalRuntimeHash({ z: 1, a: { β: "值", x: [true, null, 3] } })).resolves.toBe("bf72fef90ce770065eeda153b10b06e953d1ecc66ce68dd002641c5e80fa2a39");
  });
  it("changes only paired refs, draft lifecycle, revision and eval backrefs", async () => {
    const { nextModel, nextPolicy, nextRoute } = await drafts();
    expect(nextModel).toMatchObject({ revision: 13, budgetPolicyRef: pairedPolicyRef, priceSnapshotRef: pairedPriceRef, lifecycle: "draft", evalGateRef: null });
    expect(nextPolicy).toMatchObject({ revision: 14, budgetPolicyRef: pairedPolicyRef, lifecycle: "draft", killSwitchEnabled: true, unknownUsageBehavior: "block", unknownPriceBehavior: "block" });
    expect(nextRoute).toMatchObject({ revision: 13, lifecycle: "draft", evalGateRef: null, candidates: [{ model: { revision: 13, contentHash: nextModel.contentHash }, weight: 100 }], runtimePolicyRef: { revision: 14, contentHash: nextPolicy.contentHash } });
    expect(nextModel.contentHash).toMatch(/^[0-9a-f]{64}$/);
  });
  it("publishes model and policy before the route with stable idempotency and reread", async () => {
    const client = clientFactory();
    const result = await prepareQyhSuccessorDrafts({ pairedPolicyRef, pairedPriceRef, now: () => "2026-10-31T01:00:00Z" }, client);
    expect(result.status).toBe("prepared");
    expect(vi.mocked(client.publishModel).mock.calls[0]?.[1]).toMatch(/^qyh-successor-model-/);
    expect(vi.mocked(client.publishPolicy).mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(client.publishRoute).mock.invocationCallOrder[0]!);
    expect(vi.mocked(client.publishModel).mock.calls[0]?.[2]).toBe(model.revision);
    expect(vi.mocked(client.publishRoute)).toHaveBeenCalledTimes(1);
  });
  it("reconciles an unknown model response only by GET and never resends", async () => {
    const client = clientFactory({ modelPost: "unknown_after_write" });
    await expect(prepareQyhSuccessorDrafts({ pairedPolicyRef, pairedPriceRef, now: () => "2026-10-31T01:00:00Z" }, client)).resolves.toMatchObject({ status: "prepared" });
    expect(client.publishModel).toHaveBeenCalledTimes(1);
    expect(client.model).toHaveBeenCalledWith(model.registeredModelId);
  });
  it("stops after an unknown write with no exact readback and never posts later stages", async () => {
    const client = clientFactory({ modelPost: "unknown_without_write" });
    await expect(prepareQyhSuccessorDrafts({ pairedPolicyRef, pairedPriceRef, now: () => "2026-10-31T01:00:00Z" }, client)).rejects.toThrow(/未确认/);
    expect(client.publishModel).toHaveBeenCalledTimes(1);
    expect(client.publishPolicy).not.toHaveBeenCalled();
    expect(client.publishRoute).not.toHaveBeenCalled();
  });
  it("recognizes exact existing drafts and resumes without duplicate posts", async () => {
    const { nextModel, nextPolicy } = await drafts();
    const client = clientFactory();
    vi.mocked(client.model).mockImplementation(async (_id, revision) => revision === model.revision ? model : nextModel);
    vi.mocked(client.policy).mockImplementation(async (_id, revision) => revision === policy.revision ? policy : nextPolicy);
    const result = await prepareQyhSuccessorDrafts({ pairedPolicyRef, pairedPriceRef, now: () => "2026-10-31T02:00:00Z" }, client);
    expect(result.status).toBe("prepared");
    expect(client.publishModel).not.toHaveBeenCalled();
    expect(client.publishPolicy).not.toHaveBeenCalled();
    expect(client.publishRoute).toHaveBeenCalledTimes(1);
  });
  it("rejects a drifted current route before any POST", async () => {
    const client = clientFactory();
    vi.mocked(client.route).mockResolvedValue({ ...route, candidates: [{ model: ref("RegisteredModelRevision", "other", 1), weight: 100 }] });
    await expect(prepareQyhSuccessorDrafts({ pairedPolicyRef, pairedPriceRef, now: () => "2026-10-31T01:00:00Z" }, client)).rejects.toThrow(/漂移/);
    expect(client.publishModel).not.toHaveBeenCalled();
  });
  it("repeats the complete preflight immediately before writes", async () => {
    const client = clientFactory();
    vi.mocked(client.model).mockResolvedValue({ ...model, priceSnapshotRef: ref("OtherPriceRevision", "old-price") });
    await expect(prepareQyhSuccessorDrafts({ pairedPolicyRef, pairedPriceRef, now: () => "2026-10-31T01:00:00Z" }, client)).rejects.toThrow(/完整接续预检已漂移/);
    expect(client.publishModel).not.toHaveBeenCalled();
    expect(client.publishPolicy).not.toHaveBeenCalled();
    expect(client.publishRoute).not.toHaveBeenCalled();
  });
  it("recognizes three exact current drafts after a page reload without publishing", async () => {
    const { nextModel, nextPolicy, nextRoute } = await drafts();
    const client = clientFactory();
    vi.mocked(client.model).mockImplementation(async (_id, revision) => revision === model.revision ? model : nextModel);
    vi.mocked(client.policy).mockImplementation(async (_id, revision) => revision === policy.revision ? policy : nextPolicy);
    vi.mocked(client.route).mockImplementation(async (_id, revision) => revision === route.revision ? route : nextRoute);
    await expect(inspectQyhSuccessorDraftState({ pairedPolicyRef, pairedPriceRef, now: () => "2026-10-31T03:00:00Z" }, client)).resolves.toMatchObject({
      status: "prepared",
      observed: { model: true, policy: true, route: true },
      model: { revision: 13 }, policy: { revision: 14 }, route: { revision: 13 },
    });
    expect(client.publishModel).not.toHaveBeenCalled();
    expect(client.publishPolicy).not.toHaveBeenCalled();
    expect(client.publishRoute).not.toHaveBeenCalled();
  });
  it("freezes a partially observed chain without filling or resending missing drafts", async () => {
    const { nextModel } = await drafts();
    const client = clientFactory();
    vi.mocked(client.model).mockImplementation(async (_id, revision) => revision === model.revision ? model : nextModel);
    await expect(inspectQyhSuccessorDraftState({ pairedPolicyRef, pairedPriceRef, now: () => "2026-10-31T03:00:00Z" }, client)).resolves.toMatchObject({
      status: "partial_observed",
      observed: { model: true, policy: false, route: false },
    });
    expect(client.publishModel).not.toHaveBeenCalled();
    expect(client.publishPolicy).not.toHaveBeenCalled();
    expect(client.publishRoute).not.toHaveBeenCalled();
  });
});
