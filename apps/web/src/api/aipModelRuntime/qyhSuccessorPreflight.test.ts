import { describe, expect, it } from "vitest";
import type { ExactRuntimeRef, ModelRouteRevision, RegisteredModelRevision, RuntimePolicyRevision } from "./contracts";
import { inspectQyhSuccessorPreflight } from "./qyhSuccessorPreflight";

const H = "a".repeat(64);
const PAIR = "b".repeat(64);
const tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = (assetType: string, assetId: string): ExactRuntimeRef => ({ assetType, assetId, revision: 1, contentHash: H });
const model: RegisteredModelRevision = { tenant, registeredModelId: "a0v-agnes-2-5-flash-readonly-dev", revision: 12, contentHash: H,
  provider: ref("ProviderInstanceRevision", "provider"), providerModelId: "agnes-2.5-flash", inputModalities: ["text"], outputModalities: ["text"], capabilities: ["chat"], contextWindow: 128000,
  quotaPolicyRef: ref("QuotaPolicyRevision", "quota"), budgetPolicyRef: ref("BudgetPolicyRevision", "old-budget"), priceSnapshotRef: ref("ModelPriceSnapshotRevision", "old-price"), evalGateRef: ref("EvalGateDecision", "gate"), lifecycle: "active", createdBy: "owner", createdAt: "2026-10-31T00:00:00Z" };
const policy: RuntimePolicyRevision = { tenant, policyId: "a0v-ecommerce-runtime-policy-v1", revision: 13, contentHash: H,
  networkPolicyRef: ref("NetworkPolicyRevision", "network"), egressPolicyRef: ref("EgressPolicyRevision", "egress"), dataClassificationPolicyRef: ref("DataClassificationPolicyRevision", "classification"), quotaPolicyRef: ref("QuotaPolicyRevision", "quota"), budgetPolicyRef: ref("BudgetPolicyRevision", "old-budget"), deadlineMs: 30000, maxAttempts: 1, allowedFallbackReasons: [], unknownUsageBehavior: "block", unknownPriceBehavior: "block", killSwitchEnabled: true, lifecycle: "active", createdBy: "owner", createdAt: "2026-10-31T00:00:00Z" };
const route: ModelRouteRevision = { tenant, routeId: "a0v-ecommerce-text-readonly-v1", revision: 12, contentHash: H,
  taskTypes: ["copy.generate"], requiredInputModality: "text", requiredOutputModality: "text", requiredCapabilities: ["chat"], candidates: [{ model: { ...ref("RegisteredModelRevision", model.registeredModelId), revision: model.revision }, weight: 100 }], strategy: "failover", runtimePolicyRef: { ...ref("RuntimePolicyRevision", policy.policyId), revision: policy.revision }, evalGateRef: ref("EvalGateDecision", "gate"), lifecycle: "active", createdBy: "owner", createdAt: "2026-10-31T00:00:00Z" };

describe("QYH model/runtime/route successor preflight", () => {
  it("only marks the three draft preparations ready for the exact QYH chain", () => {
    const result = inspectQyhSuccessorPreflight({ model, policy, route,
      pairedPolicyRef: ref("BudgetPolicyRevision", `window-policy-${PAIR}`), pairedPriceRef: ref("ModelPriceSnapshotRevision", `window-price-${PAIR}`) });
    expect(result.ready).toBe(true);
    expect(result.steps.map((item) => item.status)).toEqual(["ready", "ready", "ready"]);
    expect(result.executionAllowed).toBe(false);
  });
  it.each([
    { name: "foreign tenant", patch: { model: { ...model, tenant: { orgId: "dev-org", projectId: "dev-project" } } } },
    { name: "wrong provider model", patch: { model: { ...model, providerModelId: "another-model" } } },
    { name: "route candidate drift", patch: { route: { ...route, candidates: [{ model: ref("RegisteredModelRevision", "another-model"), weight: 100 }] } } },
    { name: "unsafe policy", patch: { policy: { ...policy, killSwitchEnabled: false } } },
    { name: "wrong paired ref", patch: { pairedPriceRef: ref("RegisteredModelRevision", `window-price-${PAIR}`) } },
    { name: "mismatched pair", patch: { pairedPriceRef: ref("ModelPriceSnapshotRevision", `window-price-${"c".repeat(64)}`) } },
  ])("fails closed on $name", ({ patch }) => {
    const result = inspectQyhSuccessorPreflight({ model, policy, route,
      pairedPolicyRef: ref("BudgetPolicyRevision", `window-policy-${PAIR}`), pairedPriceRef: ref("ModelPriceSnapshotRevision", `window-price-${PAIR}`), ...patch });
    expect(result.ready).toBe(false);
    expect(result.steps.some((item) => item.status === "blocked")).toBe(true);
    expect(result.executionAllowed).toBe(false);
  });
});
