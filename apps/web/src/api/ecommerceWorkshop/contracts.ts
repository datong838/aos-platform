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
