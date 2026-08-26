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
export type InvestigationCaseListResponse = { tenant: InvestigationTenant; items: InvestigationCaseRevision[]; count: number };
export type InvestigationRunListResponse = { tenant: InvestigationTenant; items: InvestigationRunView[]; count: number };
export type InvestigationReadClient = {
  listCases(signal?: AbortSignal): Promise<InvestigationCaseListResponse>;
  listRuns(caseId: string, signal?: AbortSignal): Promise<InvestigationRunListResponse>;
};
