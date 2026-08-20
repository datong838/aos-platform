import { describe, expect, it } from "vitest";
import { parseModelRuntimeOverview, parseProviderInstanceRevision, parseProviderPluginRevision } from "./parser";

const H = "a".repeat(64);
const ref = (assetType: string, assetId: string) => ({ assetType, assetId, revision: 1, contentHash: H });
const empty = { tenant: { orgId: "org-org", projectId: "dev-project" }, providers: [], models: [], routes: [], policies: [], priceSnapshots: [], evalGates: [], capacityPools: [], healthObservations: [], resolutions: [], generatedAt: "2026-08-14T00:00:00Z" };

describe("AIP-7 exact model runtime parser", () => {
  it("接受真实空 authority", () => { expect(parseModelRuntimeOverview(empty).tenant.orgId).toBe("org-org"); });
  it("解析租户内最新 Health 且保留时效边界", () => {
    const parsed = parseModelRuntimeOverview({ ...empty, healthObservations: [{ tenant: empty.tenant, observationId: "health-1", provider: ref("ProviderInstanceRevision", "agnes-text"), status: "healthy", availabilityPct: 100, p50LatencyMs: 88, observedAt: "2026-08-14T00:00:00Z", expiresAt: "2026-08-14T00:05:00Z" }] });
    expect(parsed.healthObservations[0].provider.assetId).toBe("agnes-text");
  });
  it("拒绝非法 exact hash", () => { expect(() => parseModelRuntimeOverview({ ...empty, providers: [{ ref: { ...ref("ProviderInstanceRevision", "p1"), contentHash: "masked" }, lifecycle: "active", dependencyRefs: [] }] })).toThrow(/SHA-256/); });
  it("拒绝用 selected 缺失冒充 ready", () => { expect(() => parseModelRuntimeOverview({ ...empty, resolutions: [{ route: ref("ModelRouteRevision", "r1"), policy: ref("RuntimePolicyRevision", "p1"), readiness: "ready", selectedModel: null, selectedProvider: null, selectedPriceSnapshot: null, blockerCodes: [], resolvedAt: empty.generatedAt }] })).toThrow(/ready 合同不完整/); });
  it("接受带明确 blocker 的 blocked", () => { const parsed = parseModelRuntimeOverview({ ...empty, resolutions: [{ route: ref("ModelRouteRevision", "r1"), policy: ref("RuntimePolicyRevision", "p1"), readiness: "blocked", selectedModel: null, selectedProvider: null, selectedPriceSnapshot: null, blockerCodes: ["provider_health_unavailable_or_stale"], resolvedAt: empty.generatedAt }] }); expect(parsed.resolutions[0].blockerCodes).toEqual(["provider_health_unavailable_or_stale"]); });
  it("拒绝 Provider 详情中的明文凭据字段", () => {
    const provider = { tenant: empty.tenant, providerInstanceId: "agnes-text", revision: 1, contentHash: H, pluginRef: ref("ProviderPluginRevision", "agnes-text"), endpointProfile: { baseUrl: "https://api.agnes-ai.cn/v1", region: "Singapore (International)", timeoutMs: 30000, metadata: {} }, secretRef: "keychain://aos/agnes", secretVersion: "1", egressPolicyRef: ref("EgressPolicyRevision", "egress"), dataClassificationPolicyRef: ref("DataClassificationPolicyRevision", "classification"), lifecycle: "active", createdBy: "fde", createdAt: empty.generatedAt };
    expect(parseProviderInstanceRevision(provider).secretBackend).toBe("keychain");
    expect(() => parseProviderInstanceRevision({ ...provider, apiKey: "plaintext" })).toThrow(/凭据字段/);
  });
  it("解析 Provider 插件审批权威", () => {
    const plugin = parseProviderPluginRevision({ providerPluginId: "agnes-text", revision: 1, contentHash: H, manifestVersion: "1.0.0", manifestSourceHash: H, sourceRef: "plugins/llm-providers/agnes-text/manifest.json", owner: "AOS/FDE", usageBasis: "internal", approvedCapabilities: ["text", "llm", "chat"], deniedCapabilities: ["image", "audio", "video", "tool_execution"], modalities: ["text"], defaultModels: ["agnes-2.5-flash"], allowedTenants: [empty.tenant], approvalStatus: "approved", approvedBy: "owner", approvedAt: empty.generatedAt });
    expect(plugin.approvalStatus).toBe("approved");
  });
});
