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
export type TaskCockpitExactRevisionRef = { resourceType: string; resourceId: string; revision: number; contentHash: string };
export type TaskCockpitStageCompilation = { stageId: string; title: string; dependsOn: string[]; requiredSlotIds: string[]; applicabilityResult: "applicable" | "not_applicable"; evaluatedProfile: string };
export type TaskCockpitCoreResponse = { schemaVersion: typeof TASK_COCKPIT_SCHEMA_VERSION; tenant: WorkshopTenant; evaluatedAt: string; taskCutoff: string; stateConsistency: "current_state_per_page"; readiness: "degraded"; blockers: TaskCockpitBlocker[]; items: TaskCockpitTask[]; page: TaskCockpitPage };
export type TaskCockpitStepPageResponse = { schemaVersion: typeof TASK_COCKPIT_SCHEMA_VERSION; tenant: WorkshopTenant; runId: string; evaluatedAt: string; membershipCutoff: string; stateConsistency: "current_state_per_page"; items: TaskCockpitStep[]; page: TaskCockpitPage };
export type TaskCockpitCheckpointPageResponse = { schemaVersion: typeof TASK_COCKPIT_SCHEMA_VERSION; tenant: WorkshopTenant; runId: string; evaluatedAt: string; membershipCutoff: string; stateConsistency: "current_state_per_page"; items: TaskCockpitCheckpoint[]; page: TaskCockpitPage };
export type TaskCockpitProductionContextResponse = { schemaVersion: typeof TASK_COCKPIT_SCHEMA_VERSION; tenant: WorkshopTenant; runId: string; taskId: string; evaluatedAt: string; planRef: TaskCockpitExactRevisionRef; stageTemplateRef: TaskCockpitExactRevisionRef; responsibilityPlanRef: TaskCockpitExactRevisionRef; compilerVersion: "w2c.v1"; stages: TaskCockpitStageCompilation[]; applicableStageIds: string[]; notApplicableStageIds: string[] };
export type TaskCockpitStructuralAssignee = { kind: "agent_instance" | "human_principal" | "tool_binding" | "provider_capability_binding"; resourceId: string; version: number; operationalReadiness: "unverified" };
export type TaskCockpitResponsibilitySlot = { slotId: string; responsibilityType: string; requiredCapabilityIds: string[]; returnStage: string; assignee: TaskCockpitStructuralAssignee };
export type TaskCockpitHandoffDecision = { decisionId: string; revision: number; decision: "accepted" | "rejected" | "request_more" | "returned"; reasonCode: string | null; gapCodes: string[]; contentHash: string; createdAt: string };
export type TaskCockpitHandoff = { handoffId: string; status: "issued" | "consumed" | "expired" | "revoked"; version: number; senderInstanceRef: TaskCockpitExactRevisionRef; receiverInstanceRef: TaskCockpitExactRevisionRef; expiresAt: string; consumedAt: string | null; createdAt: string; decisions: TaskCockpitHandoffDecision[] };
export type TaskCockpitResponsibilityHandoffResponse = { schemaVersion: typeof TASK_COCKPIT_SCHEMA_VERSION; tenant: WorkshopTenant; runId: string; taskId: string; evaluatedAt: string; responsibilityPlanRef: TaskCockpitExactRevisionRef; profile: string; lifecycle: "draft" | "frozen" | "withdrawn" | "superseded"; compilationReadiness: "ready_at_compile"; compiledRequiredSlotIds: string[]; slots: TaskCockpitResponsibilitySlot[]; handoffs: TaskCockpitHandoff[] };
export type TaskCockpitApprovalNavigation = { routeIdentity: "aip.task-plan" | "aip.action-drafts"; routePath: string; targetRef: TaskCockpitExactRevisionRef; commandReadiness: "read_only_fact" | "destination_reauthorization_required"; requiredPermission: string; blockerCodes: string[]; returnFocusToken: string };
export type TaskCockpitPlanApproval = { planRef: TaskCockpitExactRevisionRef; approvalStatus: "draft" | "approved" | "superseded" | "rejected"; approvedBy: string | null; approvedAt: string | null; navigation: TaskCockpitApprovalNavigation };
export type TaskCockpitApprovalDecision = { approvalEventId: string; proposalVersion: number; proposalHash: string; decision: "approved" | "rejected"; actorId: string; expiresAt: string | null; createdAt: string };
export type TaskCockpitActionApproval = { proposalRef: TaskCockpitExactRevisionRef; actionTypeId: string; status: "proposed" | "drafted" | "approved" | "rejected" | "expired" | "leased" | "executing" | "applied" | "failed" | "unknown" | "reconciled" | "compensated"; expiresAt: string; decisions: TaskCockpitApprovalDecision[]; navigation: TaskCockpitApprovalNavigation };
export type TaskCockpitReviewIssueEvent = { eventId: string; sequence: number; eventType: "opened" | "resolved" | "returned" | "superseded"; issueVersion: number; payloadHash: string; actor: string; createdAt: string };
export type TaskCockpitReviewReturnLineage = { decisionId: string; issueVersion: number; runId: string; stepKey: string; stepRunId: string; attempt: number; decisionHash: string; createdAt: string };
export type TaskCockpitReviewIssue = { issueId: string; version: number; status: "open" | "resolved" | "returned" | "superseded"; severity: "info" | "warning" | "error" | "critical"; ruleRef: TaskCockpitExactRevisionRef; artifactId: string; artifactHash: string; evalReportRef: TaskCockpitExactRevisionRef; returnStage: string; evidenceCount: number; lineageReadiness: "attempt_exact" | "attempt_unresolved"; returnLineage: TaskCockpitReviewReturnLineage | null; events: TaskCockpitReviewIssueEvent[] };
export type TaskCockpitApprovalReviewResponse = { schemaVersion: typeof TASK_COCKPIT_SCHEMA_VERSION; tenant: WorkshopTenant; runId: string; taskId: string; evaluatedAt: string; planApproval: TaskCockpitPlanApproval; actionApprovals: TaskCockpitActionApproval[]; reviewIssues: TaskCockpitReviewIssue[]; actionApprovalCount: number; reviewIssueCount: number; unresolvedAttemptCount: number };
export type TaskCockpitActionReceipt = { receiptId: string; receiptKind: "initial" | "reconcile"; status: "accepted" | "applied" | "failed" | "unknown" | "reconciled"; leaseId: string; requestFingerprint: string; providerRequestPresent: boolean; evidenceCount: number; supersedesReceiptId: string | null; resolvedStatus: "applied" | "failed" | null; createdAt: string };
export type TaskCockpitActionExecution = { proposalRef: TaskCockpitExactRevisionRef; actionTypeId: string; proposalStatus: "proposed" | "drafted" | "approved" | "rejected" | "expired" | "leased" | "executing" | "applied" | "failed" | "unknown" | "reconciled" | "compensated"; leaseId: string | null; attempt: number | null; receipts: TaskCockpitActionReceipt[]; reconciliationState: "not_started" | "not_required" | "required" | "resolved" };
export type TaskCockpitActionReceiptResponse = { schemaVersion: typeof TASK_COCKPIT_SCHEMA_VERSION; tenant: WorkshopTenant; runId: string; taskId: string; evaluatedAt: string; executions: TaskCockpitActionExecution[]; proposalCount: number; receiptCount: number; unknownReceiptCount: number; reconcileRequiredCount: number; reconciledReceiptCount: number };
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

export const OPERATION_COMMAND_OBSERVATION_SCHEMA_VERSION = "aos.ecommerce-workshop.operation-command-observation/v1" as const;
export type ObservableOperationCommandId = Exclude<OperationCommandId, "refund">;
export type OperationCommandObservationStatus = "notStarted" | "accepted" | "applied" | "failed" | "unknown" | "reconciled";
export type OperationCommandObservationResponse = {
  schemaVersion: typeof OPERATION_COMMAND_OBSERVATION_SCHEMA_VERSION;
  tenant: WorkshopTenant;
  proposalId: string;
  leaseId: string;
  commandId: ObservableOperationCommandId;
  status: OperationCommandObservationStatus;
  proposalHash: string;
  receiptId: string | null;
  requestFingerprint: string | null;
  operationReceiptId: string | null;
  replayAllowed: false;
};
