import { describe, expect, it } from "vitest";
import { parseModelRuntimeOverview } from "./parser";

const H = "a".repeat(64);
const ref = (assetType: string, assetId: string) => ({ assetType, assetId, revision: 1, contentHash: H });
const empty = { tenant: { orgId: "org-org", projectId: "dev-project" }, providers: [], models: [], routes: [], policies: [], priceSnapshots: [], evalGates: [], capacityPools: [], resolutions: [], generatedAt: "2026-08-14T00:00:00Z" };

describe("AIP-7 exact model runtime parser", () => {
  it("接受真实空 authority", () => { expect(parseModelRuntimeOverview(empty).tenant.orgId).toBe("org-org"); });
  it("拒绝非法 exact hash", () => { expect(() => parseModelRuntimeOverview({ ...empty, providers: [{ ref: { ...ref("ProviderInstanceRevision", "p1"), contentHash: "masked" }, lifecycle: "active", dependencyRefs: [] }] })).toThrow(/SHA-256/); });
  it("拒绝用 selected 缺失冒充 ready", () => { expect(() => parseModelRuntimeOverview({ ...empty, resolutions: [{ route: ref("ModelRouteRevision", "r1"), policy: ref("RuntimePolicyRevision", "p1"), readiness: "ready", selectedModel: null, selectedProvider: null, selectedPriceSnapshot: null, blockerCodes: [], resolvedAt: empty.generatedAt }] })).toThrow(/ready 合同不完整/); });
  it("接受带明确 blocker 的 blocked", () => { const parsed = parseModelRuntimeOverview({ ...empty, resolutions: [{ route: ref("ModelRouteRevision", "r1"), policy: ref("RuntimePolicyRevision", "p1"), readiness: "blocked", selectedModel: null, selectedProvider: null, selectedPriceSnapshot: null, blockerCodes: ["provider_health_unavailable_or_stale"], resolvedAt: empty.generatedAt }] }); expect(parsed.resolutions[0].blockerCodes).toEqual(["provider_health_unavailable_or_stale"]); });
});
