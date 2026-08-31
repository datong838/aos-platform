import { describe, expect, it } from "vitest";
import { parseModelRouteRevision, parseModelRuntimeCostOverview, parseModelRuntimeOverview, parseProviderInstanceRevision, parseProviderPluginRevision, parseRegisteredModelRevision } from "./parser";

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
  it("解析模型到 Provider、价格、容量和 Eval 的 exact 关系", () => {
    const model = parseRegisteredModelRevision({ tenant: empty.tenant, registeredModelId: "model-1", revision: 1, contentHash: H, provider: ref("ProviderInstanceRevision", "provider-1"), providerModelId: "agnes-2.5-flash", inputModalities: ["text"], outputModalities: ["text"], capabilities: ["chat", "function-calling"], contextWindow: 128000, quotaPolicyRef: ref("QuotaPolicyRevision", "quota-1"), budgetPolicyRef: ref("BudgetPolicyRevision", "budget-1"), priceSnapshotRef: ref("ModelPriceSnapshotRevision", "price-1"), evalGateRef: ref("EvalGateDecision", "gate-1"), lifecycle: "active", createdBy: "fde", createdAt: empty.generatedAt });
    expect(model.providerModelId).toBe("agnes-2.5-flash");
    expect(model.evalGateRef.assetId).toBe("gate-1");
  });
  it("解析不可变路由 revision 与 exact Eval/Policy 关系", () => {
    const route = parseModelRouteRevision({ tenant: empty.tenant, routeId: "route-1", revision: 3, contentHash: H, taskTypes: ["summary"], requiredInputModality: "text", requiredOutputModality: "text", requiredCapabilities: ["chat"], candidates: [{ model: ref("RegisteredModelRevision", "model-1"), weight: 100 }], strategy: "failover", runtimePolicyRef: ref("RuntimePolicyRevision", "policy-1"), evalGateRef: ref("EvalGateDecision", "gate-1"), lifecycle: "active", createdBy: "fde", createdAt: empty.generatedAt });
    expect(route.lifecycle).toBe("active");
    expect(route.candidates[0].model.assetId).toBe("model-1");
  });
  it("拒绝错误 exact ref、重复候选和不守恒权重", () => {
    const base = { tenant: empty.tenant, routeId: "route-1", revision: 3, contentHash: H, taskTypes: ["summary"], requiredInputModality: "text", requiredOutputModality: "text", requiredCapabilities: ["chat"], candidates: [{ model: ref("RegisteredModelRevision", "model-1"), weight: 60 }, { model: ref("RegisteredModelRevision", "model-2"), weight: 30 }], strategy: "weighted", runtimePolicyRef: ref("RuntimePolicyRevision", "policy-1"), evalGateRef: ref("EvalGateDecision", "gate-1"), lifecycle: "validated", createdBy: "fde", createdAt: empty.generatedAt };
    expect(() => parseModelRouteRevision(base)).toThrow("权重总和必须为 100");
    expect(() => parseModelRouteRevision({ ...base, candidates: [{ model: ref("RegisteredModelRevision", "model-1"), weight: 50 }, { model: ref("RegisteredModelRevision", "model-1"), weight: 50 }] })).toThrow("不能重复引用同一模型");
    expect(() => parseModelRouteRevision({ ...base, candidates: [{ model: ref("RegisteredModelRevision", "model-1"), weight: 100 }], strategy: "failover", runtimePolicyRef: ref("RegisteredModelRevision", "policy-1") })).toThrow("runtimePolicyRef 类型非法");
  });
});

describe("AIP-7 cost authority parser", () => {
  const cost = {
    tenant: empty.tenant,
    modelPrices: [],
    budgets: [],
    usage: { state: "unobserved", receiptCount: 0, measuredCount: 0, estimatedCount: 0, unknownCount: 0, adjustmentCount: 0, costTotals: {}, latestObservedAt: null, truncated: false },
    generatedAt: empty.generatedAt,
  };
  it("保留未观测而非伪造零成本", () => {
    expect(parseModelRuntimeCostOverview(cost).usage.state).toBe("unobserved");
  });
  it("拒绝质量计数与 Receipt 总数不一致", () => {
    expect(() => parseModelRuntimeCostOverview({ ...cost, usage: { ...cost.usage, state: "partial", receiptCount: 2, measuredCount: 1 } })).toThrow(/计数不一致/);
  });
  it("解析单位不匹配的图像价格权威", () => {
    const parsed = parseModelRuntimeCostOverview({ ...cost, modelPrices: [{ modelRef: ref("RegisteredModelRevision", "image"), providerModelId: "agnes-image-2.1-flash", outputModalities: ["image"], priceSnapshotRef: ref("ModelPriceSnapshotRevision", "price-image"), status: "unit_mismatch", currency: "CNY", inputTokenPrice: 0, outputTokenPrice: 0, cachedTokenPrice: null, tokenUnit: 1000, effectiveFrom: empty.generatedAt, effectiveUntil: null, zeroPriceApprovalRef: null, blockerCodes: ["TOKEN_PRICE_UNIT_MISMATCH"] }] });
    expect(parsed.modelPrices[0].status).toBe("unit_mismatch");
  });
});
