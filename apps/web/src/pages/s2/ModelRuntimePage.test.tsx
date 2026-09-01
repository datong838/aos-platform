import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { aipModelRuntime, type ModelRuntimeChainOverview, type ModelRuntimeCostOverview, type ModelRuntimeOverview } from "../../api/aipModelRuntime";
import { controlledTrialLabel, ModelRuntimePage, modelRuntimeControlStatus } from "./ModelRuntimePage";

const hash = "a".repeat(64);
const base = {
  tenant: { orgId: "org-org", projectId: "dev-project" },
  providers: [],
  models: [],
  routes: [],
  policies: [],
  priceSnapshots: [],
  evalGates: [],
  capacityPools: [],
  healthObservations: [],
  resolutions: [],
  generatedAt: "2026-08-14T00:00:00Z",
} satisfies ModelRuntimeOverview;

const emptyCost = {
  tenant: base.tenant,
  modelPrices: [], budgets: [], quotas: [],
  usage: { state: "unobserved", receiptCount: 0, measuredCount: 0, estimatedCount: 0, unknownCount: 0, adjustmentCount: 0, costTotals: {}, periods: [], attributionDimensions: [] },
  generatedAt: base.generatedAt,
} satisfies ModelRuntimeCostOverview;

afterEach(() => {
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

describe("ModelRuntimePage control status", () => {
  it("真实渲染六节点、关闭试聊门和同凭证双向追溯", async () => {
    const route = { assetType: "ModelRouteRevision", assetId: "route-text", revision: 1, contentHash: hash };
    const model = { assetType: "RegisteredModelRevision", assetId: "model-text", revision: 1, contentHash: hash };
    const node = (stage: "provider" | "secret_ref" | "policy" | "eval" | "health" | "capacity") => ({
      stage, status: "blocked" as const, title: `${stage} 需复核`, exactRef: null, observedAt: base.generatedAt,
      expiresAt: null, blockerCode: `${stage.toUpperCase()}_NOT_READY`, impact: "影响经营任务运行", ownerEntry: "/aip/model-router", recheckAction: "回到责任入口复核后刷新",
    });
    const chain = {
      tenant: base.tenant,
      chains: [{ route, candidateModel: model, taskTypes: ["经营分析"], readiness: "blocked", nodes: [node("provider"), node("secret_ref"), node("policy"), node("eval"), node("health"), node("capacity")], controlledTrialAllowed: false, resolvedAt: base.generatedAt }],
      taskTraces: [{ task: { resourceType: "task", resourceId: "task-1", revision: "1" }, receiptCount: 1, models: [{ resourceType: "model", resourceId: "model-text", revision: "1" }], agents: [{ resourceType: "agent", resourceId: "数据参谋", revision: "1" }], logics: [{ resourceType: "logic", resourceId: "经营复盘", revision: "1" }], missingDimensions: [] }],
      modelImpacts: [{ model: { resourceType: "model", resourceId: "model-text", revision: "1" }, receiptCount: 1, tasks: [{ resourceType: "task", resourceId: "task-1", revision: "1" }], agents: [{ resourceType: "agent", resourceId: "数据参谋", revision: "1" }], logics: [{ resourceType: "logic", resourceId: "经营复盘", revision: "1" }] }],
      generatedAt: base.generatedAt,
    } satisfies ModelRuntimeChainOverview;
    vi.spyOn(aipModelRuntime, "overview").mockResolvedValue({ ...base, routes: [{ ref: route, lifecycle: "active", dependencyRefs: [] }] });
    vi.spyOn(aipModelRuntime, "chainOverview").mockResolvedValue(chain);
    vi.spyOn(aipModelRuntime, "costOverview").mockResolvedValue(emptyCost);
    const host = document.createElement("div"); document.body.append(host); const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><ModelRuntimePage /></MemoryRouter>));
    await act(async () => undefined);
    expect(host.querySelectorAll('[aria-label="模型运行六节点链路"] .notice').length).toBe(6);
    const trial = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("当前链路不可试聊"));
    expect(trial?.hasAttribute("disabled")).toBe(true);
    expect(host.textContent).toContain("任务与模型双向追溯");
    expect(host.textContent).toContain("数字同事：数据参谋");
    await act(async () => root.unmount());
  });
  it("受控试聊按钮不把关闭状态写成可执行", () => {
    expect(controlledTrialLabel(true)).toBe("进入受控试聊");
    expect(controlledTrialLabel(false)).toBe("当前链路不可试聊");
  });
  it("真实空 authority 不冒充 ready", () => expect(modelRuntimeControlStatus(base)).toBe("empty"));
  it("有资产但没有 resolution 时保持 blocked", () =>
    expect(
      modelRuntimeControlStatus({
        ...base,
        providers: [
          {
            ref: { assetType: "ProviderInstanceRevision", assetId: "p", revision: 1, contentHash: hash },
            lifecycle: "active",
            dependencyRefs: [],
          },
        ],
      }),
    ).toBe("blocked"));
  it("部分 route ready 时为 partial，不冒充全绿", () => {
    const routeText = { assetType: "ModelRouteRevision" as const, assetId: "route-text", revision: 1, contentHash: hash };
    const routeVideo = { assetType: "ModelRouteRevision" as const, assetId: "route-video", revision: 1, contentHash: hash };
    const policy = { assetType: "RuntimePolicyRevision" as const, assetId: "pol", revision: 1, contentHash: hash };
    const model = { assetType: "RegisteredModelRevision" as const, assetId: "m", revision: 1, contentHash: hash };
    const provider = { assetType: "ProviderInstanceRevision" as const, assetId: "p", revision: 1, contentHash: hash };
    const price = { assetType: "PriceSnapshotRevision" as const, assetId: "price", revision: 1, contentHash: hash };
    expect(
      modelRuntimeControlStatus({
        ...base,
        providers: [{ ref: provider, lifecycle: "active", dependencyRefs: [] }],
        resolutions: [
          {
            route: routeText,
            policy,
            readiness: "ready",
            selectedModel: model,
            selectedProvider: provider,
            selectedPriceSnapshot: price,
            blockerCodes: [],
            resolvedAt: base.generatedAt,
          },
          {
            route: routeVideo,
            policy,
            readiness: "blocked",
            selectedModel: null,
            selectedProvider: null,
            selectedPriceSnapshot: null,
            blockerCodes: ["provider_health_unavailable_or_stale"],
            resolvedAt: base.generatedAt,
          },
        ],
      }),
    ).toBe("partial");
  });
  it("全部 route ready 时为 ready", () => {
    const route = { assetType: "ModelRouteRevision" as const, assetId: "route-text", revision: 1, contentHash: hash };
    const model = { assetType: "RegisteredModelRevision" as const, assetId: "m", revision: 1, contentHash: hash };
    const provider = { assetType: "ProviderInstanceRevision" as const, assetId: "p", revision: 1, contentHash: hash };
    const price = { assetType: "PriceSnapshotRevision" as const, assetId: "price", revision: 1, contentHash: hash };
    const policy = { assetType: "RuntimePolicyRevision" as const, assetId: "pol", revision: 1, contentHash: hash };
    expect(
      modelRuntimeControlStatus({
        ...base,
        providers: [{ ref: provider, lifecycle: "active", dependencyRefs: [] }],
        resolutions: [
          {
            route,
            policy,
            readiness: "ready",
            selectedModel: model,
            selectedProvider: provider,
            selectedPriceSnapshot: price,
            blockerCodes: [],
            resolvedAt: base.generatedAt,
          },
        ],
      }),
    ).toBe("ready");
  });
});
