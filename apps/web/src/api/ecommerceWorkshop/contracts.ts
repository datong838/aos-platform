export const ECOMMERCE_WORKSHOP_SCHEMA_VERSION = "aos.ecommerce-workshop/v1" as const;

export type WorkshopReadiness = "available" | "degraded" | "disabled" | "blocked" | "unknown";
export type WorkshopDependencyState = WorkshopReadiness;
export type WorkshopDependencyType = "object" | "capability" | "aip_feature" | "data_scope" | "permission" | "registry" | "installation";

export type WorkshopTenant = { orgId: string; projectId: string };
export type WorkshopInstallationRef = {
  installationId: string;
  revision: number;
  compositionId: string;
  lockRevision: number;
  lockHash: string;
  overlayRevision: string;
};
export type WorkshopModuleRef = {
  publisher: string;
  bundleId: string;
  version: string;
  bundleContentHash: string;
  moduleArtifactRef: string;
  moduleArtifactHash: string;
};
export type WorkshopDependencyRef = {
  resourceType: string;
  resourceId: string;
  revision: string | null;
  contentHash: string | null;
  authority: string;
};
export type WorkshopReadinessBlocker = {
  dependencyType: WorkshopDependencyType;
  dependencyId: string;
  state: WorkshopDependencyState;
  reasonCode: string;
  recoverable: boolean;
  requiredAction: string;
  ref: WorkshopDependencyRef | null;
};
export type WorkshopPermissions = {
  roles: string[];
  markings: string[];
  dataScopes: string[];
  actionTypes: string[];
};
export type EcommerceWorkshopModule = {
  moduleId: string;
  displayName: string;
  menuLabel: string;
  route: string;
  slot: "workshop.primary.ecommerce";
  order: number;
  installationRef: WorkshopInstallationRef;
  moduleRef: WorkshopModuleRef;
  readiness: WorkshopReadiness;
  blockers: WorkshopReadinessBlocker[];
  permissions: WorkshopPermissions;
  requiredObjects: string[];
  requiredCapabilities: string[];
  requiredAipFeatures: string[];
  viewRefs: string[];
  evalPackRefs: string[];
  productionContractRefs: string[];
  responsibilityTemplateRefs: string[];
  impactCalculatorRefs: string[];
  legacyAssetRefs: string[];
  legacyRoutes: string[];
  minimumRuntimeVersion: string;
  lastReceiptRef: WorkshopDependencyRef | null;
};
export type EcommerceWorkshopModuleListResponse = {
  schemaVersion: typeof ECOMMERCE_WORKSHOP_SCHEMA_VERSION;
  tenant: WorkshopTenant;
  evaluatedAt: string;
  dataCutoff: string | null;
  items: EcommerceWorkshopModule[];
  count: number;
};
export type EcommerceWorkshopModuleReadinessResponse = {
  schemaVersion: typeof ECOMMERCE_WORKSHOP_SCHEMA_VERSION;
  tenant: WorkshopTenant;
  evaluatedAt: string;
  dataCutoff: string | null;
  item: EcommerceWorkshopModule;
};

export type EcommerceWorkshopApiErrorBody = {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  traceId: string;
};

export const SOURCE_READINESS_SCHEMA_VERSION = "aos.source-readiness/v1" as const;
export type SourceReadinessStatus = "ready" | "empty" | "degraded" | "unknown" | "stale" | "failed" | "blocked" | "forbidden";
export type SourceReadinessObservationStatus = "succeeded" | "failed" | "running" | "unknown";
export type SourceReadinessPolicyStatus = "pass" | "fail" | "unknown";
export type SourceReadinessExactRef = { resourceType: string; resourceId: string; revision: string; contentHash: string; authority: string };
export type SourceReadinessLatestRun = { runId: string | null; status: SourceReadinessObservationStatus; scheduledFor: string | null; startedAt: string | null; finishedAt: string | null; rowsWritten: number | null; errorCode: string | null };
export type SourceReadinessCounts = { sourceTotal: number | null; sourceActive: number | null; sourceDeleted: number | null; projectionTotal: number | null; unexplainedDelta: number | null };
export type SourceReadinessPolicyObservation = { status: SourceReadinessPolicyStatus; ruleRef: SourceReadinessExactRef | null; summary: string | null };
export type SourceReadinessItem = {
  schemaVersion: typeof SOURCE_READINESS_SCHEMA_VERSION;
  tenant: WorkshopTenant;
  sourceId: string;
  pipelineId: string;
  objectType: string;
  status: SourceReadinessStatus;
  checkedAt: string;
  observedAt: string | null;
  sourceEventAt: string | null;
  projectedAt: string | null;
  dataCutoff: string | null;
  freshnessExpiresAt: string | null;
  sourceConfigRef: SourceReadinessExactRef | null;
  mappingRef: SourceReadinessExactRef | null;
  schemaRef: SourceReadinessExactRef | null;
  maskingPolicyRef: SourceReadinessExactRef | null;
  freshnessPolicyRef: SourceReadinessExactRef | null;
  qualityPolicyRef: SourceReadinessExactRef | null;
  reconciliationPolicyRef: SourceReadinessExactRef | null;
  queryCapabilityRef: SourceReadinessExactRef | null;
  latestRun: SourceReadinessLatestRun;
  counts: SourceReadinessCounts;
  quality: SourceReadinessPolicyObservation;
  reconciliation: SourceReadinessPolicyObservation;
  reasons: string[];
  blockers: string[];
};
export type SourceReadinessEnvelope = {
  schemaVersion: typeof SOURCE_READINESS_SCHEMA_VERSION;
  tenant: WorkshopTenant;
  checkedAt: string;
  cutoffAt: string;
  status: SourceReadinessStatus;
  sources: SourceReadinessItem[];
  receiptRef: SourceReadinessExactRef | null;
};

export const TASK_COCKPIT_SCHEMA_VERSION = "aos.ecommerce-workshop.task-cockpit/v1" as const;
export type TaskCockpitTaskStatus = "pending" | "planning" | "awaiting_approval" | "approved" | "executing" | "paused" | "completed" | "failed" | "cancelled" | "rolled_back";
export type TaskCockpitRunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled" | "unknown";
export type TaskCockpitStepStatus = "queued" | "running" | "succeeded" | "failed" | "skipped" | "unknown";
export type TaskCockpitPage = { limit: number; count: number; hasMore: boolean; nextCursor: string | null };
export type TaskCockpitBlocker = { code: string; severity: "warning" | "blocking"; dependency: string; requiredAction: string };
export type TaskCockpitRun = { runId: string; planRevisionId: string; status: TaskCockpitRunStatus; version: number; startedAt: string | null; finishedAt: string | null; createdAt: string; updatedAt: string };
export type TaskCockpitTask = { taskId: string; taskType: string; title: string; status: TaskCockpitTaskStatus; priority: number; version: number; currentPlanRevisionId: string | null; createdAt: string; updatedAt: string; run: TaskCockpitRun | null };
export type TaskCockpitStep = { stepRunId: string; stepKey: string; attempt: number; status: TaskCockpitStepStatus; tokenCount: number; costAmount: string; hasInputRefs: boolean; hasOutputRefs: boolean; hasError: boolean; createdAt: string; updatedAt: string };
export type TaskCockpitCheckpoint = { checkpointId: string; sequence: number; schemaVersion: number; stepKey: string | null; stateHash: string; artifactCount: number; createdAt: string };
export type TaskCockpitCoreResponse = { schemaVersion: typeof TASK_COCKPIT_SCHEMA_VERSION; tenant: WorkshopTenant; evaluatedAt: string; taskCutoff: string; stateConsistency: "current_state_per_page"; readiness: "degraded"; blockers: TaskCockpitBlocker[]; items: TaskCockpitTask[]; page: TaskCockpitPage };
export type TaskCockpitStepPageResponse = { schemaVersion: typeof TASK_COCKPIT_SCHEMA_VERSION; tenant: WorkshopTenant; runId: string; evaluatedAt: string; membershipCutoff: string; stateConsistency: "current_state_per_page"; items: TaskCockpitStep[]; page: TaskCockpitPage };
export type TaskCockpitCheckpointPageResponse = { schemaVersion: typeof TASK_COCKPIT_SCHEMA_VERSION; tenant: WorkshopTenant; runId: string; evaluatedAt: string; membershipCutoff: string; stateConsistency: "current_state_per_page"; items: TaskCockpitCheckpoint[]; page: TaskCockpitPage };
export type TaskCockpitCoreQuery = { status?: TaskCockpitTaskStatus; limit?: number; cursor?: string };
export type TaskCockpitRunDetailQuery = { limit?: number; cursor?: string };

export const OPERATIONS_SCHEMA_VERSION = "aos.ecommerce-workshop.operations-view/v1" as const;
export type OperationsSliceId = "orders" | "orderLines" | "inventory" | "shipments" | "payments" | "aftersaleEvents" | "operationCases";
export type OperationsSliceStatus = "ready" | "blocked";
export type OperationsAuthorityRef = { resourceType: string; resourceId: string; revision: number; contentHash: string; receiptId: string };
export type OperationsBlocker = { code: string; dependency: string; requiredAction: string };
export type OperationsCountLedger = { sourceTotal: number; attached: number; unmatched: number; conflicted: number };
export type OperationsSlice = { sliceId: OperationsSliceId; status: OperationsSliceStatus; dataCutoff: string; authorityRefs: OperationsAuthorityRef[]; blockers: OperationsBlocker[]; countLedger: OperationsCountLedger };
export type OperationsPage = { limit: number; count: number; hasMore: boolean; nextCursor: string | null };
export type OperationsViewResponse = { schemaVersion: typeof OPERATIONS_SCHEMA_VERSION; tenant: WorkshopTenant; evaluatedAt: string; dataCutoff: string; readiness: "degraded"; slices: OperationsSlice[]; page: OperationsPage };

export const OPERATION_COMMAND_READINESS_SCHEMA_VERSION = "aos.ecommerce-workshop.operation-command-readiness/v1" as const;
export type OperationCommandId = "classify" | "createCase" | "changeMembership" | "manageSla" | "automationKill" | "refund";
export type OperationCommandBlocker = { code: string; dependency: string; requiredAction: string };
export type OperationCommandDescriptor = { commandId: OperationCommandId; label: string; status: "ready" | "blocked"; risk: "controlled" | "high"; sideEffect: "internalAuthority" | "external"; blockers: OperationCommandBlocker[] };
export type OperationCommandReadinessResponse = { schemaVersion: typeof OPERATION_COMMAND_READINESS_SCHEMA_VERSION; tenant: WorkshopTenant; evaluatedAt: string; commands: OperationCommandDescriptor[] };
