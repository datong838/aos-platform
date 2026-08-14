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

export type ModelRuntimeOverview = {
  tenant: { orgId: string; projectId: string };
  providers: RuntimeAssetSummary[];
  models: RuntimeAssetSummary[];
  routes: RuntimeAssetSummary[];
  policies: RuntimeAssetSummary[];
  priceSnapshots: RuntimeAssetSummary[];
  evalGates: RuntimeEvalGateSummary[];
  capacityPools: RuntimeCapacityPoolSummary[];
  resolutions: RuntimeResolution[];
  generatedAt: string;
};
