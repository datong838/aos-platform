export type RuntimeLifecycle = "draft" | "validated" | "active" | "suspended" | "revoked";
export type RuntimeReadiness = "ready" | "blocked" | "unknown";

export type ExactRuntimeRef = {
  assetType: string;
  assetId: string;
  revision: number;
  contentHash: string;
};

export type RuntimeAssetSummary = {
  ref: ExactRuntimeRef;
  lifecycle: RuntimeLifecycle;
  dependencyRefs: ExactRuntimeRef[];
};

export type RuntimeEvalGateSummary = { ref: ExactRuntimeRef; status: "passed" | "failed" | "blocked" | "unknown" };

export type RuntimeCapacityPoolSummary = {
  poolId: string;
  revision: number;
  contentHash: string;
  routeRef: ExactRuntimeRef;
  modelRef: ExactRuntimeRef;
  providerRef: ExactRuntimeRef;
  maxConcurrency: number;
  maxTokenUnits: number;
  tokenUnitPerReservation: number;
  leaseSeconds: number;
  activeReservations: number;
  reservedTokenUnits: number;
  lifecycle: RuntimeLifecycle;
};

export type RuntimeResolution = {
  route: ExactRuntimeRef;
  policy: ExactRuntimeRef;
  readiness: RuntimeReadiness;
  selectedModel: ExactRuntimeRef | null;
  selectedProvider: ExactRuntimeRef | null;
  selectedPriceSnapshot: ExactRuntimeRef | null;
  blockerCodes: string[];
  resolvedAt: string;
};

export type ProviderHealthObservation = {
  tenant: { orgId: string; projectId: string };
  observationId: string;
  provider: ExactRuntimeRef;
  status: "healthy" | "degraded" | "unavailable" | "unknown";
  availabilityPct: number | null;
  p50LatencyMs: number | null;
  observedAt: string;
  expiresAt: string;
};

export type ProviderInstanceRevision = {
  tenant: { orgId: string; projectId: string };
  providerInstanceId: string;
  revision: number;
  contentHash: string;
  pluginRef: ExactRuntimeRef;
  endpointProfile: { baseUrl: string; region: string; timeoutMs: number; metadata: Record<string, string> };
  secretBackend: "vault" | "secret" | "keychain";
  secretVersion: string;
  egressPolicyRef: ExactRuntimeRef;
  dataClassificationPolicyRef: ExactRuntimeRef;
  lifecycle: RuntimeLifecycle;
  createdBy: string;
  createdAt: string;
};

export type RegisteredModelRevision = {
  tenant: { orgId: string; projectId: string };
  registeredModelId: string;
  revision: number;
  contentHash: string;
  provider: ExactRuntimeRef;
  providerModelId: string;
  inputModalities: string[];
  outputModalities: string[];
  capabilities: string[];
  contextWindow: number;
  quotaPolicyRef: ExactRuntimeRef;
  budgetPolicyRef: ExactRuntimeRef;
  priceSnapshotRef: ExactRuntimeRef;
  evalGateRef: ExactRuntimeRef;
  lifecycle: RuntimeLifecycle;
  createdBy: string;
  createdAt: string;
};

export type ModelRouteRevision = {
  tenant: { orgId: string; projectId: string };
  routeId: string;
  revision: number;
  contentHash: string;
  taskTypes: string[];
  requiredInputModality: string;
  requiredOutputModality: string;
  requiredCapabilities: string[];
  candidates: Array<{ model: ExactRuntimeRef; weight: number }>;
  strategy: "failover" | "weighted" | "lowest_latency" | "lowest_cost";
  runtimePolicyRef: ExactRuntimeRef;
  evalGateRef: ExactRuntimeRef;
  lifecycle: RuntimeLifecycle;
  createdBy: string;
  createdAt: string;
};

export type ProviderPluginRevision = {
  providerPluginId: string;
  revision: number;
  contentHash: string;
  manifestVersion: string;
  manifestSourceHash: string;
  sourceRef: string;
  owner: string;
  usageBasis: string;
  approvedCapabilities: string[];
  deniedCapabilities: string[];
  modalities: string[];
  defaultModels: string[];
  allowedTenants: Array<{ orgId: string; projectId: string }>;
  approvalStatus: string;
  approvedBy: string;
  approvedAt: string;
};

export type ModelRuntimeOverview = {
  tenant: { orgId: string; projectId: string };
  providers: RuntimeAssetSummary[];
  models: RuntimeAssetSummary[];
  routes: RuntimeAssetSummary[];
  policies: RuntimeAssetSummary[];
  priceSnapshots: RuntimeAssetSummary[];
  evalGates: RuntimeEvalGateSummary[];
  capacityPools: RuntimeCapacityPoolSummary[];
  healthObservations: ProviderHealthObservation[];
  resolutions: RuntimeResolution[];
  generatedAt: string;
};

export type ModelPriceAuthorityStatus =
  | "priced"
  | "approved_zero"
  | "unknown"
  | "inactive"
  | "out_of_window"
  | "unit_mismatch"
  | "drifted";

export type ModelPriceAuthoritySummary = {
  modelRef: ExactRuntimeRef;
  providerModelId: string;
  outputModalities: string[];
  priceSnapshotRef: ExactRuntimeRef | null;
  status: ModelPriceAuthorityStatus;
  currency: string | null;
  inputTokenPrice: number | null;
  outputTokenPrice: number | null;
  cachedTokenPrice: number | null;
  tokenUnit: number | null;
  effectiveFrom: string | null;
  effectiveUntil: string | null;
  zeroPriceApprovalRef: string | null;
  blockerCodes: string[];
};

export type RuntimeBudgetAuthoritySummary = {
  budgetPolicyRef: ExactRuntimeRef;
  budgetRef: ExactRuntimeRef | null;
  status: "active" | "inactive" | "out_of_window" | "drifted" | "unknown";
  currency: string | null;
  dailyLimitMinor: number | null;
  monthlyLimitMinor: number | null;
  hardStop: boolean | null;
  unknownUsageBehavior: string | null;
  unknownPriceBehavior: string | null;
  effectiveFrom: string | null;
  effectiveUntil: string | null;
  blockerCodes: string[];
};

export type RuntimeQuotaAuthoritySummary = {
  quotaPolicyRef: ExactRuntimeRef;
  headRef: ExactRuntimeRef | null;
  headVersion: number | null;
  status: "active" | "inactive" | "out_of_window" | "drifted" | "unknown";
  lifecycle: "draft" | "blocked" | "active" | "suspended" | "revoked" | "expired" | null;
  owner: string | null;
  approvalRef: string | null;
  rpmLimit: number | null;
  tpmLimit: number | null;
  maxConcurrency: number | null;
  maxInputTokens: number | null;
  maxOutputTokens: number | null;
  hourlyRequestLimit: number | null;
  dailyRequestLimit: number | null;
  overflowBehavior: string | null;
  reservationLeaseSeconds: number | null;
  allowPublicProviderFallback: boolean | null;
  allowAutoScale: boolean | null;
  effectiveFrom: string | null;
  effectiveUntil: string | null;
  blockerCodes: string[];
};

export type RuntimeUsageAttributionEntry = {
  subjectId: string;
  subjectRevision: string;
  receiptCount: number;
  quantityTotals: Record<string, number>;
};

export type RuntimeUsageAttributionDimension = {
  dimension: "tenant" | "task" | "agent" | "logic" | "model";
  source: "tenant_scope" | "lineage" | "explicit";
  attributedReceiptCount: number;
  missingReceiptCount: number;
  entries: RuntimeUsageAttributionEntry[];
};

export type RuntimeUsageAuthoritySummary = {
  state: "unobserved" | "measured" | "partial" | "unknown";
  receiptCount: number;
  measuredCount: number;
  estimatedCount: number;
  unknownCount: number;
  adjustmentCount: number;
  costTotals: Record<string, number>;
  latestObservedAt: string | null;
  truncated: boolean;
  periods: RuntimeUsagePeriodSummary[];
};

export type RuntimeUsagePeriodSummary = {
  period: "today" | "week" | "month";
  timeZone: string;
  startsAt: string;
  endsAt: string;
  receiptCount: number;
  measuredCount: number;
  estimatedCount: number;
  unknownCount: number;
  quantityTotals: Record<string, number>;
  providerCounts: Record<string, number>;
  attributionDimensions: RuntimeUsageAttributionDimension[];
};

export type ModelRuntimeCostOverview = {
  tenant: { orgId: string; projectId: string };
  modelPrices: ModelPriceAuthoritySummary[];
  budgets: RuntimeBudgetAuthoritySummary[];
  quotas: RuntimeQuotaAuthoritySummary[];
  usage: RuntimeUsageAuthoritySummary;
  generatedAt: string;
};
