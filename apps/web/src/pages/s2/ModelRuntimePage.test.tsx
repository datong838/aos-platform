import { describe, expect, it } from "vitest";
import type { ModelRuntimeOverview } from "../../api/aipModelRuntime";
import { modelRuntimeControlStatus } from "./ModelRuntimePage";

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

describe("ModelRuntimePage control status", () => {
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
