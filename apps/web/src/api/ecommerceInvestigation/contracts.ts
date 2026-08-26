export type InvestigationTenant = { orgId: string; projectId: string };

export type InvestigationExactRef = {
  resourceType: string;
  resourceId: string;
  revision: number | string;
  contentHash: string;
  receiptId?: string;
};

export type InvestigationAnalysisType =
  | "initial_store_analysis"
  | "weekly_business_review"
  | "experience_growth"
  | "creator_sales"
  | "product_structure";

export type InvestigationCaseLifecycle = "DRAFT" | "ACTIVE" | "ARCHIVED" | "CLOSED";

export type InvestigationCaseRevision = {
  schemaVersion: "aos.ecommerce.business-investigation-case/v1";
  tenant: InvestigationTenant;
  caseId: string;
  revision: number;
  version: number;
  priorRef: InvestigationExactRef | null;
  contentHash: string;
  lifecycle: InvestigationCaseLifecycle;
  analysisType: InvestigationAnalysisType;
  title: string;
  purposeCode: string;
  channelRef: InvestigationExactRef;
  businessEntityRef: InvestigationExactRef;
  entityChannelBindingRef: InvestigationExactRef;
  investigationProfileRef: InvestigationExactRef;
  scopeRef: InvestigationExactRef;
  schedulePolicyRef: InvestigationExactRef | null;
  createdBy: string;
  createdAt: string;
};

export type InvestigationRunLifecycle =
  | "PREPARING"
  | "WAITING_DATA"
  | "PORTRAIT"
  | "DIAGNOSIS"
  | "SOLUTION_DESIGN"
  | "REVIEW"
  | "COMPLETED"
  | "FAILED";
export type InvestigationRunControl =
  | "RUNNING"
  | "PAUSED"
  | "BLOCKED"
  | "STALE"
  | "UNKNOWN"
  | "RECONCILING"
  | "CANCELLED";

export type InvestigationRunRecord = {
  schemaVersion: "aos.ecommerce.business-investigation-run/v1";
  tenant: InvestigationTenant;
  runId: string;
  version: 1;
  contentHash: string;
  caseRef: InvestigationExactRef;
  analysisType: InvestigationAnalysisType;
  triggerKind: "manual" | "scheduled" | "topic" | "recovery";
  triggerKey: string;
  lifecycle: "PREPARING";
  control: "RUNNING";
  createdBy: string;
  createdAt: string;
};

export type InvestigationRunState = {
  schemaVersion: "aos.ecommerce.business-investigation-run-state/v1";
  tenant: InvestigationTenant;
  runId: string;
  version: number;
  priorRef: InvestigationExactRef | null;
  lifecycle: InvestigationRunLifecycle;
  control: InvestigationRunControl;
  eventSequence: number;
  contentHash: string;
  pendingRequirementRef: InvestigationExactRef | null;
  uncertainCommand: { commandId: string; operation: string; requestHash: string } | null;
  createdBy: string;
  createdAt: string;
};

export type InvestigationRunView = { authority: InvestigationRunRecord; state: InvestigationRunState };
export type InvestigationStageStatus = "not_started" | "running" | "waiting_data" | "waiting_human" | "blocked" | "review" | "accepted" | "returned" | "completed";
export type InvestigationStageRailItem = { stageId: "portrait" | "diagnosis" | "solution-design"; title: string; status: InvestigationStageStatus; stepRunId: string | null; attempt: number | null };
export type InvestigationRuntimeProjection = {
  bindingStatus: "unbound" | "task_pending" | "bound";
  taskId: string | null;
  planRef: InvestigationExactRef | null;
  taskRunRef: { resourceType: "TaskRun"; resourceId: string; version: number } | null;
  taskRunStatus: "queued" | "running" | "pausing" | "paused" | "succeeded" | "failed" | "cancelled" | "unknown" | null;
  checkpoint: { checkpointId: string; sequence: number; stepKey: string | null; stateHash: string; createdAt: string } | null;
  stages: InvestigationStageRailItem[];
  completed: number;
  total: 3;
  currentStageId: "portrait" | "diagnosis" | "solution-design" | null;
};
export type InvestigationWorkbenchView = {
  schemaVersion: "aos.ecommerce.business-investigation-workbench-view/v2";
  tenant: InvestigationTenant;
  projectionHash: string;
  sourceWatermark: { caseRevision: number; runVersion: number; stateVersion: number; bindingHashes: string[]; runtimeHash: string | null; contentHash: string };
  observedAt: string;
  caseRef: InvestigationExactRef;
  runRef: InvestigationExactRef;
  stateRef: InvestigationExactRef;
  caseEnvelope: { title: string; analysisType: InvestigationAnalysisType; lifecycle: InvestigationCaseLifecycle; channelRef: InvestigationExactRef; businessEntityRef: InvestigationExactRef; investigationProfileRef: InvestigationExactRef; scopeRef: InvestigationExactRef; schedulePolicyRef: InvestigationExactRef | null; createdBy: string; createdAt: string };
  lifecycle: InvestigationRunLifecycle;
  control: InvestigationRunControl;
  pendingRequirementRef: InvestigationExactRef | null;
  uncertainCommand: { commandId: string; operation: string; requestHash: string } | null;
  runtime: InvestigationRuntimeProjection;
  artifacts: Array<{ artifactType: "BusinessDossierRevision" | "ProblemMapRevision" | "SolutionSetRevision" | "DecisionReportRevision"; status: "bound" | "missing"; artifactRef: InvestigationExactRef | null; bindingId: string | null; bindingHash: string | null; selectionRevision: number | null; dataCutoff: string | null; lineageRef: InvestigationExactRef | null }>;
};
export type InvestigationCaseListResponse = { tenant: InvestigationTenant; items: InvestigationCaseRevision[]; count: number };
export type InvestigationRunListResponse = { tenant: InvestigationTenant; items: InvestigationRunView[]; count: number };
export type InvestigationReadClient = {
  listCases(signal?: AbortSignal): Promise<InvestigationCaseListResponse>;
  listRuns(caseId: string, signal?: AbortSignal): Promise<InvestigationRunListResponse>;
  getRunView?(runId: string, signal?: AbortSignal): Promise<InvestigationWorkbenchView>;
};
