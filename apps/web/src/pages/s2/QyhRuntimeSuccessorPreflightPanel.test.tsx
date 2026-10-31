import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ExactRuntimeRef } from "../../api/aipModelRuntime";
import { inspectQyhSuccessorDraftState, prepareQyhSuccessorDrafts } from "../../api/aipModelRuntime/successorDrafts";
import { QyhRuntimeSuccessorPreflightPanel } from "./QyhRuntimeSuccessorPreflightPanel";

vi.mock("../../api/aipModelRuntime", async (load) => {
  const actual = await load<typeof import("../../api/aipModelRuntime")>();
  return { ...actual, aipModelRuntime: { ...actual.aipModelRuntime, model: vi.fn(), policy: vi.fn(), route: vi.fn() } };
});
vi.mock("../../api/aipModelRuntime/successorDrafts", () => ({ inspectQyhSuccessorDraftState: vi.fn(), prepareQyhSuccessorDrafts: vi.fn() }));
const H = "a".repeat(64), PAIR = "b".repeat(64), tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = (assetType: string, assetId: string): ExactRuntimeRef => ({ assetType, assetId, revision: 1, contentHash: H });
const model = { tenant, registeredModelId: "a0v-agnes-2-5-flash-readonly-dev", revision: 12, contentHash: H, provider: ref("ProviderInstanceRevision", "provider"), providerModelId: "agnes-2.5-flash", inputModalities: ["text"], outputModalities: ["text"], capabilities: ["chat"], contextWindow: 128000, quotaPolicyRef: ref("QuotaPolicyRevision", "quota"), budgetPolicyRef: ref("BudgetPolicyRevision", "old-budget"), priceSnapshotRef: ref("ModelPriceSnapshotRevision", "old-price"), evalGateRef: ref("EvalGateDecision", "gate"), lifecycle: "active" as const, createdBy: "owner", createdAt: "2026-10-31T00:00:00Z" };
const policy = { tenant, policyId: "a0v-ecommerce-runtime-policy-v1", revision: 13, contentHash: H, networkPolicyRef: ref("NetworkPolicyRevision", "network"), egressPolicyRef: ref("EgressPolicyRevision", "egress"), dataClassificationPolicyRef: ref("DataClassificationPolicyRevision", "classification"), quotaPolicyRef: ref("QuotaPolicyRevision", "quota"), budgetPolicyRef: ref("BudgetPolicyRevision", "old-budget"), deadlineMs: 30000, maxAttempts: 1, allowedFallbackReasons: [], unknownUsageBehavior: "block" as const, unknownPriceBehavior: "block" as const, killSwitchEnabled: true, lifecycle: "active" as const, createdBy: "owner", createdAt: "2026-10-31T00:00:00Z" };
const route = { tenant, routeId: "a0v-ecommerce-text-readonly-v1", revision: 12, contentHash: H, taskTypes: ["copy.generate"], requiredInputModality: "text", requiredOutputModality: "text", requiredCapabilities: ["chat"], candidates: [{ model: { ...ref("RegisteredModelRevision", model.registeredModelId), revision: model.revision }, weight: 100 }], strategy: "failover" as const, runtimePolicyRef: { ...ref("RuntimePolicyRevision", policy.policyId), revision: policy.revision }, evalGateRef: ref("EvalGateDecision", "gate"), lifecycle: "active" as const, createdBy: "owner", createdAt: "2026-10-31T00:00:00Z" };
const preflight = { ready: true, executionAllowed: false as const, steps: [
  { id: "model" as const, label: "注册模型草稿", status: "ready" as const, reason: "可准备" },
  { id: "policy" as const, label: "运行策略草稿", status: "ready" as const, reason: "可准备" },
  { id: "route" as const, label: "模型路由草稿", status: "ready" as const, reason: "可准备" },
] };
const state = (status: "ready_to_prepare" | "partial_observed" | "prepared", observed = { model: false, policy: false, route: false }) => ({ status, observed, model, policy, route, preflight });
let host: HTMLDivElement;
afterEach(() => { vi.clearAllMocks(); host?.remove(); });
async function render() { host = document.createElement("div"); document.body.append(host); const root = createRoot(host); await act(async () => { root.render(<MemoryRouter><QyhRuntimeSuccessorPreflightPanel pairedPolicyRef={ref("BudgetPolicyRevision", `window-policy-${PAIR}`)} pairedPriceRef={ref("ModelPriceSnapshotRevision", `window-price-${PAIR}`)} /></MemoryRouter>); }); return root; }

describe("QYH successor preflight panel", () => {
  it("performs only the read-only draft inspection and labels the result as preparation", async () => {
    vi.mocked(inspectQyhSuccessorDraftState).mockResolvedValue(state("ready_to_prepare"));
    const root = await render();
    expect(host.textContent).toContain("三个追加式草稿可准备");
    expect(host.textContent).toContain("尚未评测、不可调用");
    expect(inspectQyhSuccessorDraftState).toHaveBeenCalledTimes(1);
    expect(prepareQyhSuccessorDrafts).not.toHaveBeenCalled();
    await act(async () => root.unmount());
  });
  it("publishes drafts only after one explicit confirmation and never calls a model", async () => {
    vi.mocked(inspectQyhSuccessorDraftState).mockResolvedValue(state("ready_to_prepare"));
    vi.mocked(prepareQyhSuccessorDrafts).mockResolvedValue({ status: "prepared", model, policy, route });
    const root = await render();
    const button = Array.from(host.querySelectorAll("button")).find((item) => item.textContent?.includes("确认准备三个草稿"));
    expect(button).toBeTruthy();
    expect(prepareQyhSuccessorDrafts).not.toHaveBeenCalled();
    await act(async () => { button!.click(); });
    expect(prepareQyhSuccessorDrafts).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("三个草稿已精确回读");
    expect(host.textContent).toContain("仍未评测、未激活、未调用模型");
    await act(async () => root.unmount());
  });
  it("fails closed when an authority read fails", async () => {
    vi.mocked(inspectQyhSuccessorDraftState).mockRejectedValue(new Error("unavailable"));
    const root = await render();
    expect(host.textContent).toContain("接续预检未确认");
    expect(host.textContent).not.toContain("三个追加式草稿可准备");
    await act(async () => root.unmount());
  });
  it("recovers three prepared drafts after reload and only links to Eval", async () => {
    vi.mocked(inspectQyhSuccessorDraftState).mockResolvedValue(state("prepared", { model: true, policy: true, route: true }));
    const root = await render();
    expect(host.textContent).toContain("三个追加式草稿已准备");
    expect(host.textContent).toContain("待办理 Eval，仍未评测、未激活、不可调用");
    expect(host.querySelector<HTMLAnchorElement>('a[href="/aip/evals"]')).toBeTruthy();
    expect(host.textContent).not.toContain("确认准备三个草稿");
    expect(prepareQyhSuccessorDrafts).not.toHaveBeenCalled();
    await act(async () => root.unmount());
  });
  it("freezes a partially observed draft chain without retry controls", async () => {
    vi.mocked(inspectQyhSuccessorDraftState).mockResolvedValue(state("partial_observed", { model: true, policy: false, route: false }));
    const root = await render();
    expect(host.textContent).toContain("检测到部分草稿，已冻结自动续接");
    expect(host.textContent).toContain("为避免 unknown 重发，不自动补写");
    expect(host.textContent).not.toContain("确认准备三个草稿");
    expect(prepareQyhSuccessorDrafts).not.toHaveBeenCalled();
    await act(async () => root.unmount());
  });
});
