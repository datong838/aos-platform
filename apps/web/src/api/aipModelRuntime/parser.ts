import type { ExactRuntimeRef, ModelPriceAuthoritySummary, ModelRouteRevision, ModelRuntimeCostOverview, ModelRuntimeOverview, ProviderHealthObservation, ProviderInstanceRevision, ProviderPluginRevision, RegisteredModelRevision, RuntimeAssetSummary, RuntimeBudgetAuthoritySummary, RuntimeCapacityPoolSummary, RuntimeEvalGateSummary, RuntimeLifecycle, RuntimeQuotaAuthoritySummary, RuntimeReadiness, RuntimeResolution, RuntimeUsageAttributionDimension, RuntimeUsageAuthoritySummary } from "./contracts";

function object(value: unknown, label: string): Record<string, unknown> { if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} 必须是对象`); return value as Record<string, unknown>; }
function array(value: unknown, label: string): unknown[] { if (!Array.isArray(value)) throw new Error(`${label} 必须是数组`); return value; }
function string(value: unknown, label: string): string { if (typeof value !== "string" || !value.trim()) throw new Error(`${label} 必须是非空字符串`); return value; }
function integer(value: unknown, label: string, min = 0): number { if (typeof value !== "number" || !Number.isInteger(value) || value < min) throw new Error(`${label} 必须是大于等于 ${min} 的整数`); return value; }
function enumeration<T extends string>(value: unknown, label: string, values: readonly T[]): T { const result = string(value, label) as T; if (!values.includes(result)) throw new Error(`${label} 非法`); return result; }
function sha(value: unknown, label: string): string { const result = string(value, label); if (!/^[0-9a-f]{64}$/.test(result)) throw new Error(`${label} 非 SHA-256`); return result; }
function iso(value: unknown, label: string): string { const result = string(value, label); if (Number.isNaN(Date.parse(result))) throw new Error(`${label} 非时间`); return result; }
function numberOrNull(value: unknown, label: string, min = 0, max = Number.POSITIVE_INFINITY): number | null { if (value === null) return null; if (typeof value !== "number" || !Number.isFinite(value) || value < min || value > max) throw new Error(`${label} 非法`); return value; }
function integerOrNull(value: unknown, label: string, min = 0): number | null { return value === null ? null : integer(value, label, min); }
function isoOrNull(value: unknown, label: string): string | null { return value === null ? null : iso(value, label); }
function stringOrNull(value: unknown, label: string): string | null { return value === null ? null : string(value, label); }
function booleanOrNull(value: unknown, label: string): boolean | null { if (value === null) return null; if (typeof value !== "boolean") throw new Error(`${label} 必须是布尔值`); return value; }
function tenant(value: unknown, label: string) { const raw = object(value, label); return { orgId: string(raw.orgId, `${label}.orgId`), projectId: string(raw.projectId, `${label}.projectId`) }; }
function strings(value: unknown, label: string): string[] { return array(value, label).map((item, index) => string(item, `${label}[${index}]`)); }
function forbidCredentialPayload(raw: Record<string, unknown>, label: string) { const forbidden = ["apiKey", "api_key", "token", "secret", "password", "authorization", "apiKeyMasked", "api_key_masked"]; const found = forbidden.find((key) => key in raw); if (found) throw new Error(`${label} 含禁止的明文凭据字段 ${found}`); }

function ref(value: unknown, label: string): ExactRuntimeRef { const raw = object(value, label); return { assetType: string(raw.assetType, `${label}.assetType`), assetId: string(raw.assetId, `${label}.assetId`), revision: integer(raw.revision, `${label}.revision`, 1), contentHash: sha(raw.contentHash, `${label}.contentHash`) }; }
function asset(value: unknown, label: string): RuntimeAssetSummary { const raw = object(value, label); return { ref: ref(raw.ref, `${label}.ref`), lifecycle: enumeration<RuntimeLifecycle>(raw.lifecycle, `${label}.lifecycle`, ["draft", "validated", "active", "suspended", "revoked"]), dependencyRefs: array(raw.dependencyRefs, `${label}.dependencyRefs`).map((item, index) => ref(item, `${label}.dependencyRefs[${index}]`)) }; }
function gate(value: unknown, label: string): RuntimeEvalGateSummary { const raw = object(value, label); return { ref: ref(raw.ref, `${label}.ref`), status: enumeration(raw.status, `${label}.status`, ["passed", "failed", "blocked", "unknown"] as const) }; }
function pool(value: unknown, label: string): RuntimeCapacityPoolSummary { const raw = object(value, label); return { poolId: string(raw.poolId, `${label}.poolId`), revision: integer(raw.revision, `${label}.revision`, 1), contentHash: sha(raw.contentHash, `${label}.contentHash`), routeRef: ref(raw.routeRef, `${label}.routeRef`), modelRef: ref(raw.modelRef, `${label}.modelRef`), providerRef: ref(raw.providerRef, `${label}.providerRef`), maxConcurrency: integer(raw.maxConcurrency, `${label}.maxConcurrency`, 1), maxTokenUnits: integer(raw.maxTokenUnits, `${label}.maxTokenUnits`, 1), tokenUnitPerReservation: integer(raw.tokenUnitPerReservation, `${label}.tokenUnitPerReservation`, 1), leaseSeconds: integer(raw.leaseSeconds, `${label}.leaseSeconds`, 1), activeReservations: integer(raw.activeReservations, `${label}.activeReservations`), reservedTokenUnits: integer(raw.reservedTokenUnits, `${label}.reservedTokenUnits`), lifecycle: enumeration<RuntimeLifecycle>(raw.lifecycle, `${label}.lifecycle`, ["draft", "validated", "active", "suspended", "revoked"]) }; }
function resolution(value: unknown, label: string): RuntimeResolution { const raw = object(value, label); const nullable = (item: unknown, nested: string) => item === null ? null : ref(item, nested); const result = { route: ref(raw.route, `${label}.route`), policy: ref(raw.policy, `${label}.policy`), readiness: enumeration<RuntimeReadiness>(raw.readiness, `${label}.readiness`, ["ready", "blocked", "unknown"]), selectedModel: nullable(raw.selectedModel, `${label}.selectedModel`), selectedProvider: nullable(raw.selectedProvider, `${label}.selectedProvider`), selectedPriceSnapshot: nullable(raw.selectedPriceSnapshot, `${label}.selectedPriceSnapshot`), blockerCodes: array(raw.blockerCodes, `${label}.blockerCodes`).map((item, index) => string(item, `${label}.blockerCodes[${index}]`)), resolvedAt: iso(raw.resolvedAt, `${label}.resolvedAt`) }; if (result.readiness === "ready" && (!result.selectedModel || !result.selectedProvider || !result.selectedPriceSnapshot || result.blockerCodes.length)) throw new Error(`${label} ready 合同不完整`); if (result.readiness !== "ready" && (!result.blockerCodes.length || result.selectedModel || result.selectedProvider || result.selectedPriceSnapshot)) throw new Error(`${label} blocked/unknown 合同不诚实`); return result; }
function health(value: unknown, label: string): ProviderHealthObservation { const raw = object(value, label); const result = { tenant: tenant(raw.tenant, `${label}.tenant`), observationId: string(raw.observationId, `${label}.observationId`), provider: ref(raw.provider, `${label}.provider`), status: enumeration(raw.status, `${label}.status`, ["healthy", "degraded", "unavailable", "unknown"] as const), availabilityPct: numberOrNull(raw.availabilityPct, `${label}.availabilityPct`, 0, 100), p50LatencyMs: numberOrNull(raw.p50LatencyMs, `${label}.p50LatencyMs`), observedAt: iso(raw.observedAt, `${label}.observedAt`), expiresAt: iso(raw.expiresAt, `${label}.expiresAt`) }; if (result.provider.assetType !== "ProviderInstanceRevision") throw new Error(`${label}.provider 类型非法`); if (Date.parse(result.expiresAt) <= Date.parse(result.observedAt)) throw new Error(`${label} 时效区间非法`); return result; }

export function parseProviderInstanceRevision(value: unknown): ProviderInstanceRevision {
  const raw = object(value, "ProviderInstanceRevision"); forbidCredentialPayload(raw, "ProviderInstanceRevision");
  const endpoint = object(raw.endpointProfile, "endpointProfile"); forbidCredentialPayload(endpoint, "endpointProfile");
  const secretRef = string(raw.secretRef, "secretRef"); const match = /^(vault|secret|keychain):\/\//.exec(secretRef); if (!match) throw new Error("secretRef 必须是 opaque 引用");
  const pluginRef = ref(raw.pluginRef, "pluginRef"); if (pluginRef.assetType !== "ProviderPluginRevision") throw new Error("pluginRef 类型非法");
  return { tenant: tenant(raw.tenant, "tenant"), providerInstanceId: string(raw.providerInstanceId, "providerInstanceId"), revision: integer(raw.revision, "revision", 1), contentHash: sha(raw.contentHash, "contentHash"), pluginRef, endpointProfile: { baseUrl: string(endpoint.baseUrl, "endpointProfile.baseUrl"), region: string(endpoint.region, "endpointProfile.region"), timeoutMs: integer(endpoint.timeoutMs, "endpointProfile.timeoutMs", 100), metadata: Object.fromEntries(Object.entries(object(endpoint.metadata ?? {}, "endpointProfile.metadata")).map(([key, item]) => [key, string(item, `endpointProfile.metadata.${key}`)])) }, secretBackend: match[1] as "vault" | "secret" | "keychain", secretVersion: string(raw.secretVersion, "secretVersion"), egressPolicyRef: ref(raw.egressPolicyRef, "egressPolicyRef"), dataClassificationPolicyRef: ref(raw.dataClassificationPolicyRef, "dataClassificationPolicyRef"), lifecycle: enumeration<RuntimeLifecycle>(raw.lifecycle, "lifecycle", ["draft", "validated", "active", "suspended", "revoked"]), createdBy: string(raw.createdBy, "createdBy"), createdAt: iso(raw.createdAt, "createdAt") };
}

export function parseRegisteredModelRevision(value: unknown): RegisteredModelRevision {
  const raw = object(value, "RegisteredModelRevision");
  const provider = ref(raw.provider, "provider");
  if (provider.assetType !== "ProviderInstanceRevision") throw new Error("provider 类型非法");
  return {
    tenant: tenant(raw.tenant, "tenant"), registeredModelId: string(raw.registeredModelId, "registeredModelId"),
    revision: integer(raw.revision, "revision", 1), contentHash: sha(raw.contentHash, "contentHash"), provider,
    providerModelId: string(raw.providerModelId, "providerModelId"), inputModalities: strings(raw.inputModalities, "inputModalities"),
    outputModalities: strings(raw.outputModalities, "outputModalities"), capabilities: strings(raw.capabilities, "capabilities"),
    contextWindow: integer(raw.contextWindow, "contextWindow", 1), quotaPolicyRef: ref(raw.quotaPolicyRef, "quotaPolicyRef"),
    budgetPolicyRef: ref(raw.budgetPolicyRef, "budgetPolicyRef"), priceSnapshotRef: ref(raw.priceSnapshotRef, "priceSnapshotRef"),
    evalGateRef: ref(raw.evalGateRef, "evalGateRef"), lifecycle: enumeration<RuntimeLifecycle>(raw.lifecycle, "lifecycle", ["draft", "validated", "active", "suspended", "revoked"]),
    createdBy: string(raw.createdBy, "createdBy"), createdAt: iso(raw.createdAt, "createdAt"),
  };
}

export function parseModelRouteRevision(value: unknown): ModelRouteRevision {
  const raw = object(value, "ModelRouteRevision");
  const candidates = array(raw.candidates, "candidates").map((item, index) => {
    const candidate = object(item, `candidates[${index}]`);
    const model = ref(candidate.model, `candidates[${index}].model`);
    if (model.assetType !== "RegisteredModelRevision") throw new Error(`candidates[${index}].model 类型非法`);
    const weight = integer(candidate.weight, `candidates[${index}].weight`);
    if (weight > 100) throw new Error(`candidates[${index}].weight 不能超过 100`);
    return { model, weight };
  });
  if (!candidates.length) throw new Error("candidates 不能为空");
  const candidateIds = candidates.map((item) => item.model.assetId);
  if (new Set(candidateIds).size !== candidateIds.length) throw new Error("candidates 不能重复引用同一模型");
  const runtimePolicyRef = ref(raw.runtimePolicyRef, "runtimePolicyRef");
  const evalGateRef = ref(raw.evalGateRef, "evalGateRef");
  if (runtimePolicyRef.assetType !== "RuntimePolicyRevision") throw new Error("runtimePolicyRef 类型非法");
  if (evalGateRef.assetType !== "EvalGateDecision") throw new Error("evalGateRef 类型非法");
  const strategy = enumeration(raw.strategy, "strategy", ["failover", "weighted", "lowest_latency", "lowest_cost"] as const);
  if (strategy === "weighted" && candidates.reduce((total, item) => total + item.weight, 0) !== 100) throw new Error("weighted candidates 权重总和必须为 100");
  if (strategy !== "weighted" && candidates.some((item) => item.weight !== 100)) throw new Error("非 weighted candidates 权重必须为 100");
  return {
    tenant: tenant(raw.tenant, "tenant"), routeId: string(raw.routeId, "routeId"),
    revision: integer(raw.revision, "revision", 1), contentHash: sha(raw.contentHash, "contentHash"),
    taskTypes: strings(raw.taskTypes, "taskTypes"), requiredInputModality: string(raw.requiredInputModality, "requiredInputModality"),
    requiredOutputModality: string(raw.requiredOutputModality, "requiredOutputModality"),
    requiredCapabilities: strings(raw.requiredCapabilities, "requiredCapabilities"), candidates,
    strategy,
    runtimePolicyRef, evalGateRef,
    lifecycle: enumeration<RuntimeLifecycle>(raw.lifecycle, "lifecycle", ["draft", "validated", "active", "suspended", "revoked"]),
    createdBy: string(raw.createdBy, "createdBy"), createdAt: iso(raw.createdAt, "createdAt"),
  };
}

export function parseProviderPluginRevision(value: unknown): ProviderPluginRevision {
  const raw = object(value, "ProviderPluginRevision"); forbidCredentialPayload(raw, "ProviderPluginRevision");
  return { providerPluginId: string(raw.providerPluginId, "providerPluginId"), revision: integer(raw.revision, "revision", 1), contentHash: sha(raw.contentHash, "contentHash"), manifestVersion: string(raw.manifestVersion, "manifestVersion"), manifestSourceHash: sha(raw.manifestSourceHash, "manifestSourceHash"), sourceRef: string(raw.sourceRef, "sourceRef"), owner: string(raw.owner, "owner"), usageBasis: string(raw.usageBasis, "usageBasis"), approvedCapabilities: strings(raw.approvedCapabilities, "approvedCapabilities"), deniedCapabilities: strings(raw.deniedCapabilities, "deniedCapabilities"), modalities: strings(raw.modalities, "modalities"), defaultModels: strings(raw.defaultModels, "defaultModels"), allowedTenants: array(raw.allowedTenants, "allowedTenants").map((item, index) => tenant(item, `allowedTenants[${index}]`)), approvalStatus: string(raw.approvalStatus, "approvalStatus"), approvedBy: string(raw.approvedBy, "approvedBy"), approvedAt: iso(raw.approvedAt, "approvedAt") };
}

export function parseModelRuntimeOverview(value: unknown): ModelRuntimeOverview {
  const raw = object(value, "ModelRuntimeOverview"); const tenantRaw = object(raw.tenant, "tenant");
  const map = <T>(key: string, parser: (item: unknown, label: string) => T) => array(raw[key], key).map((item, index) => parser(item, `${key}[${index}]`));
  return { tenant: { orgId: string(tenantRaw.orgId, "tenant.orgId"), projectId: string(tenantRaw.projectId, "tenant.projectId") }, providers: map("providers", asset), models: map("models", asset), routes: map("routes", asset), policies: map("policies", asset), priceSnapshots: map("priceSnapshots", asset), evalGates: map("evalGates", gate), capacityPools: map("capacityPools", pool), healthObservations: map("healthObservations", health), resolutions: map("resolutions", resolution), generatedAt: iso(raw.generatedAt, "generatedAt") };
}

function priceAuthority(value: unknown, label: string): ModelPriceAuthoritySummary {
  const raw = object(value, label);
  return {
    modelRef: ref(raw.modelRef, `${label}.modelRef`),
    providerModelId: string(raw.providerModelId, `${label}.providerModelId`),
    outputModalities: strings(raw.outputModalities, `${label}.outputModalities`),
    priceSnapshotRef: raw.priceSnapshotRef === null ? null : ref(raw.priceSnapshotRef, `${label}.priceSnapshotRef`),
    status: enumeration(raw.status, `${label}.status`, ["priced", "approved_zero", "unknown", "inactive", "out_of_window", "unit_mismatch", "drifted"] as const),
    currency: stringOrNull(raw.currency, `${label}.currency`),
    inputTokenPrice: numberOrNull(raw.inputTokenPrice, `${label}.inputTokenPrice`),
    outputTokenPrice: numberOrNull(raw.outputTokenPrice, `${label}.outputTokenPrice`),
    cachedTokenPrice: numberOrNull(raw.cachedTokenPrice, `${label}.cachedTokenPrice`),
    tokenUnit: integerOrNull(raw.tokenUnit, `${label}.tokenUnit`, 1),
    effectiveFrom: isoOrNull(raw.effectiveFrom, `${label}.effectiveFrom`),
    effectiveUntil: isoOrNull(raw.effectiveUntil, `${label}.effectiveUntil`),
    zeroPriceApprovalRef: stringOrNull(raw.zeroPriceApprovalRef, `${label}.zeroPriceApprovalRef`),
    blockerCodes: strings(raw.blockerCodes, `${label}.blockerCodes`),
  };
}

function budgetAuthority(value: unknown, label: string): RuntimeBudgetAuthoritySummary {
  const raw = object(value, label);
  return {
    budgetPolicyRef: ref(raw.budgetPolicyRef, `${label}.budgetPolicyRef`),
    budgetRef: raw.budgetRef === null ? null : ref(raw.budgetRef, `${label}.budgetRef`),
    status: enumeration(raw.status, `${label}.status`, ["active", "inactive", "out_of_window", "drifted", "unknown"] as const),
    currency: stringOrNull(raw.currency, `${label}.currency`),
    dailyLimitMinor: integerOrNull(raw.dailyLimitMinor, `${label}.dailyLimitMinor`),
    monthlyLimitMinor: integerOrNull(raw.monthlyLimitMinor, `${label}.monthlyLimitMinor`),
    hardStop: booleanOrNull(raw.hardStop, `${label}.hardStop`),
    unknownUsageBehavior: stringOrNull(raw.unknownUsageBehavior, `${label}.unknownUsageBehavior`),
    unknownPriceBehavior: stringOrNull(raw.unknownPriceBehavior, `${label}.unknownPriceBehavior`),
    effectiveFrom: isoOrNull(raw.effectiveFrom, `${label}.effectiveFrom`),
    effectiveUntil: isoOrNull(raw.effectiveUntil, `${label}.effectiveUntil`),
    blockerCodes: strings(raw.blockerCodes, `${label}.blockerCodes`),
  };
}

function quotaAuthority(value: unknown, label: string): RuntimeQuotaAuthoritySummary {
  const raw = object(value, label);
  return {
    quotaPolicyRef: ref(raw.quotaPolicyRef, `${label}.quotaPolicyRef`),
    headRef: raw.headRef === null ? null : ref(raw.headRef, `${label}.headRef`),
    headVersion: integerOrNull(raw.headVersion, `${label}.headVersion`, 1),
    status: enumeration(raw.status, `${label}.status`, ["active", "inactive", "out_of_window", "drifted", "unknown"] as const),
    lifecycle: raw.lifecycle === null ? null : enumeration(raw.lifecycle, `${label}.lifecycle`, ["draft", "blocked", "active", "suspended", "revoked", "expired"] as const),
    owner: stringOrNull(raw.owner, `${label}.owner`),
    approvalRef: stringOrNull(raw.approvalRef, `${label}.approvalRef`),
    rpmLimit: integerOrNull(raw.rpmLimit, `${label}.rpmLimit`, 1),
    tpmLimit: integerOrNull(raw.tpmLimit, `${label}.tpmLimit`, 1),
    maxConcurrency: integerOrNull(raw.maxConcurrency, `${label}.maxConcurrency`, 1),
    maxInputTokens: integerOrNull(raw.maxInputTokens, `${label}.maxInputTokens`, 1),
    maxOutputTokens: integerOrNull(raw.maxOutputTokens, `${label}.maxOutputTokens`, 1),
    hourlyRequestLimit: integerOrNull(raw.hourlyRequestLimit, `${label}.hourlyRequestLimit`, 1),
    dailyRequestLimit: integerOrNull(raw.dailyRequestLimit, `${label}.dailyRequestLimit`, 1),
    overflowBehavior: stringOrNull(raw.overflowBehavior, `${label}.overflowBehavior`),
    reservationLeaseSeconds: integerOrNull(raw.reservationLeaseSeconds, `${label}.reservationLeaseSeconds`, 1),
    allowPublicProviderFallback: booleanOrNull(raw.allowPublicProviderFallback, `${label}.allowPublicProviderFallback`),
    allowAutoScale: booleanOrNull(raw.allowAutoScale, `${label}.allowAutoScale`),
    effectiveFrom: isoOrNull(raw.effectiveFrom, `${label}.effectiveFrom`),
    effectiveUntil: isoOrNull(raw.effectiveUntil, `${label}.effectiveUntil`),
    blockerCodes: strings(raw.blockerCodes, `${label}.blockerCodes`),
  };
}

function attributionDimension(value: unknown, label: string): RuntimeUsageAttributionDimension {
  const raw = object(value, label);
  return {
    dimension: enumeration(raw.dimension, `${label}.dimension`, ["tenant", "task", "agent", "logic", "model"] as const),
    source: enumeration(raw.source, `${label}.source`, ["tenant_scope", "lineage", "explicit"] as const),
    attributedReceiptCount: integer(raw.attributedReceiptCount, `${label}.attributedReceiptCount`),
    missingReceiptCount: integer(raw.missingReceiptCount, `${label}.missingReceiptCount`),
    entries: array(raw.entries, `${label}.entries`).map((entryValue, index) => {
      const entry = object(entryValue, `${label}.entries[${index}]`);
      const quantityTotals = Object.fromEntries(Object.entries(object(entry.quantityTotals, `${label}.entries[${index}].quantityTotals`)).map(([key, amount]) => {
        const parsed = numberOrNull(amount, `${label}.entries[${index}].quantityTotals.${key}`);
        if (parsed === null) throw new Error(`${label}.entries[${index}].quantityTotals.${key} 不能为空`);
        return [key, parsed];
      }));
      return {
        subjectId: string(entry.subjectId, `${label}.entries[${index}].subjectId`),
        subjectRevision: string(entry.subjectRevision, `${label}.entries[${index}].subjectRevision`),
        receiptCount: integer(entry.receiptCount, `${label}.entries[${index}].receiptCount`),
        quantityTotals,
      };
    }),
  };
}

function usageAuthority(value: unknown, label: string): RuntimeUsageAuthoritySummary {
  const raw = object(value, label);
  const costTotals = Object.fromEntries(Object.entries(object(raw.costTotals, `${label}.costTotals`)).map(([currency, amount]) => {
    const parsed = numberOrNull(amount, `${label}.costTotals.${currency}`);
    if (parsed === null) throw new Error(`${label}.costTotals.${currency} 不能为空`);
    return [currency, parsed];
  }));
  const result: RuntimeUsageAuthoritySummary = {
    state: enumeration(raw.state, `${label}.state`, ["unobserved", "measured", "partial", "unknown"] as const),
    receiptCount: integer(raw.receiptCount, `${label}.receiptCount`),
    measuredCount: integer(raw.measuredCount, `${label}.measuredCount`),
    estimatedCount: integer(raw.estimatedCount, `${label}.estimatedCount`),
    unknownCount: integer(raw.unknownCount, `${label}.unknownCount`),
    adjustmentCount: integer(raw.adjustmentCount, `${label}.adjustmentCount`),
    costTotals,
    latestObservedAt: isoOrNull(raw.latestObservedAt, `${label}.latestObservedAt`),
    truncated: typeof raw.truncated === "boolean" ? raw.truncated : (() => { throw new Error(`${label}.truncated 必须是布尔值`); })(),
    periods: array(raw.periods, `${label}.periods`).map((item, index) => {
      const periodRaw = object(item, `${label}.periods[${index}]`);
      const quantityTotals = Object.fromEntries(Object.entries(object(periodRaw.quantityTotals, `${label}.periods[${index}].quantityTotals`)).map(([key, amount]) => {
        const parsed = numberOrNull(amount, `${label}.periods[${index}].quantityTotals.${key}`);
        if (parsed === null) throw new Error(`${label}.periods[${index}].quantityTotals.${key} 不能为空`);
        return [key, parsed];
      }));
      const providerCounts = Object.fromEntries(Object.entries(object(periodRaw.providerCounts, `${label}.periods[${index}].providerCounts`)).map(([key, amount]) => [key, integer(amount, `${label}.periods[${index}].providerCounts.${key}`)]));
      const period = {
        period: enumeration(periodRaw.period, `${label}.periods[${index}].period`, ["today", "week", "month"] as const),
        timeZone: string(periodRaw.timeZone, `${label}.periods[${index}].timeZone`),
        startsAt: iso(periodRaw.startsAt, `${label}.periods[${index}].startsAt`),
        endsAt: iso(periodRaw.endsAt, `${label}.periods[${index}].endsAt`),
        receiptCount: integer(periodRaw.receiptCount, `${label}.periods[${index}].receiptCount`),
        measuredCount: integer(periodRaw.measuredCount, `${label}.periods[${index}].measuredCount`),
        estimatedCount: integer(periodRaw.estimatedCount, `${label}.periods[${index}].estimatedCount`),
        unknownCount: integer(periodRaw.unknownCount, `${label}.periods[${index}].unknownCount`),
        quantityTotals,
        providerCounts,
        attributionDimensions: array(periodRaw.attributionDimensions, `${label}.periods[${index}].attributionDimensions`).map((dimension, dimensionIndex) => attributionDimension(dimension, `${label}.periods[${index}].attributionDimensions[${dimensionIndex}]`)),
      };
      if (period.measuredCount + period.estimatedCount + period.unknownCount !== period.receiptCount) throw new Error(`${label}.periods[${index}] 用量质量计数不一致`);
      return period;
    }),
  };
  if (result.measuredCount + result.estimatedCount + result.unknownCount !== result.receiptCount) throw new Error(`${label} 用量质量计数不一致`);
  if ((result.state === "unobserved") !== (result.receiptCount === 0)) throw new Error(`${label} 未观测状态与回执数量不一致`);
  return result;
}

export function parseModelRuntimeCostOverview(value: unknown): ModelRuntimeCostOverview {
  const raw = object(value, "ModelRuntimeCostOverview");
  return {
    tenant: tenant(raw.tenant, "tenant"),
    modelPrices: array(raw.modelPrices, "modelPrices").map((item, index) => priceAuthority(item, `modelPrices[${index}]`)),
    budgets: array(raw.budgets, "budgets").map((item, index) => budgetAuthority(item, `budgets[${index}]`)),
    quotas: array(raw.quotas, "quotas").map((item, index) => quotaAuthority(item, `quotas[${index}]`)),
    usage: usageAuthority(raw.usage, "usage"),
    generatedAt: iso(raw.generatedAt, "generatedAt"),
  };
}
