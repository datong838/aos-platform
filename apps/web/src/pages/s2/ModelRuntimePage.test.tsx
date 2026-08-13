import { describe, expect, it } from "vitest";
import type { ModelRuntimeOverview } from "../../api/aipModelRuntime";
import { modelRuntimeControlStatus } from "./ModelRuntimePage";

const base = { tenant: { orgId: "org-org", projectId: "dev-project" }, providers: [], models: [], routes: [], policies: [], priceSnapshots: [], evalGates: [], capacityPools: [], resolutions: [], generatedAt: "2026-08-14T00:00:00Z" } satisfies ModelRuntimeOverview;
describe("ModelRuntimePage control status", () => {
  it("真实空 authority 不冒充 ready", () => expect(modelRuntimeControlStatus(base)).toBe("empty"));
  it("有资产但没有 resolution 时保持 blocked", () => expect(modelRuntimeControlStatus({ ...base, providers: [{ ref: { assetType: "ProviderInstanceRevision", assetId: "p", revision: 1, contentHash: "a".repeat(64) }, lifecycle: "active", dependencyRefs: [] }] })).toBe("blocked"));
});
