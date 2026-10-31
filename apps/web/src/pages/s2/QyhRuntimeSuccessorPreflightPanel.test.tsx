import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { aipModelRuntime, type ExactRuntimeRef } from "../../api/aipModelRuntime";
import { QyhRuntimeSuccessorPreflightPanel } from "./QyhRuntimeSuccessorPreflightPanel";

vi.mock("../../api/aipModelRuntime", async (load) => {
  const actual = await load<typeof import("../../api/aipModelRuntime")>();
  return { ...actual, aipModelRuntime: { ...actual.aipModelRuntime, model: vi.fn(), policy: vi.fn(), route: vi.fn() } };
});
const H = "a".repeat(64), PAIR = "b".repeat(64), tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = (assetType: string, assetId: string): ExactRuntimeRef => ({ assetType, assetId, revision: 1, contentHash: H });
const model = { tenant, registeredModelId: "a0v-agnes-2-5-flash-readonly-dev", revision: 12, contentHash: H, provider: ref("ProviderInstanceRevision", "provider"), providerModelId: "agnes-2.5-flash", inputModalities: ["text"], outputModalities: ["text"], capabilities: ["chat"], contextWindow: 128000, quotaPolicyRef: ref("QuotaPolicyRevision", "quota"), budgetPolicyRef: ref("BudgetPolicyRevision", "old-budget"), priceSnapshotRef: ref("ModelPriceSnapshotRevision", "old-price"), evalGateRef: ref("EvalGateDecision", "gate"), lifecycle: "active" as const, createdBy: "owner", createdAt: "2026-10-31T00:00:00Z" };
const policy = { tenant, policyId: "a0v-ecommerce-runtime-policy-v1", revision: 13, contentHash: H, networkPolicyRef: ref("NetworkPolicyRevision", "network"), egressPolicyRef: ref("EgressPolicyRevision", "egress"), dataClassificationPolicyRef: ref("DataClassificationPolicyRevision", "classification"), quotaPolicyRef: ref("QuotaPolicyRevision", "quota"), budgetPolicyRef: ref("BudgetPolicyRevision", "old-budget"), deadlineMs: 30000, maxAttempts: 1, allowedFallbackReasons: [], unknownUsageBehavior: "block" as const, unknownPriceBehavior: "block" as const, killSwitchEnabled: true, lifecycle: "active" as const, createdBy: "owner", createdAt: "2026-10-31T00:00:00Z" };
const route = { tenant, routeId: "a0v-ecommerce-text-readonly-v1", revision: 12, contentHash: H, taskTypes: ["copy.generate"], requiredInputModality: "text", requiredOutputModality: "text", requiredCapabilities: ["chat"], candidates: [{ model: { ...ref("RegisteredModelRevision", model.registeredModelId), revision: model.revision }, weight: 100 }], strategy: "failover" as const, runtimePolicyRef: { ...ref("RuntimePolicyRevision", policy.policyId), revision: policy.revision }, evalGateRef: ref("EvalGateDecision", "gate"), lifecycle: "active" as const, createdBy: "owner", createdAt: "2026-10-31T00:00:00Z" };
let host: HTMLDivElement;
afterEach(() => { vi.restoreAllMocks(); host?.remove(); });
async function render() { host = document.createElement("div"); document.body.append(host); const root = createRoot(host); await act(async () => { root.render(<QyhRuntimeSuccessorPreflightPanel pairedPolicyRef={ref("BudgetPolicyRevision", `window-policy-${PAIR}`)} pairedPriceRef={ref("ModelPriceSnapshotRevision", `window-price-${PAIR}`)} />); }); return root; }

describe("QYH successor preflight panel", () => {
  it("performs only the three authoritative GET reads and labels the result as preparation", async () => {
    vi.mocked(aipModelRuntime.model).mockResolvedValue(model);
    vi.mocked(aipModelRuntime.policy).mockResolvedValue(policy);
    vi.mocked(aipModelRuntime.route).mockResolvedValue(route);
    const root = await render();
    expect(host.textContent).toContain("三个追加式草稿可准备");
    expect(host.textContent).toContain("尚未发布、未评测、不可调用");
    expect(aipModelRuntime.model).toHaveBeenCalledTimes(1);
    expect(aipModelRuntime.policy).toHaveBeenCalledTimes(1);
    expect(aipModelRuntime.route).toHaveBeenCalledTimes(1);
    await act(async () => root.unmount());
  });
  it("fails closed when an authority read fails", async () => {
    vi.mocked(aipModelRuntime.model).mockResolvedValue(model);
    vi.mocked(aipModelRuntime.policy).mockRejectedValue(new Error("unavailable"));
    vi.mocked(aipModelRuntime.route).mockResolvedValue(route);
    const root = await render();
    expect(host.textContent).toContain("接续预检未确认");
    expect(host.textContent).not.toContain("三个追加式草稿可准备");
    await act(async () => root.unmount());
  });
});
