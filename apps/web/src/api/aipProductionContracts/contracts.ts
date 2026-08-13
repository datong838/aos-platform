export type Tenant = { orgId: string; projectId: string };
export type ResourceRef = { resourceType: string; resourceId: string; revision: string | null; authority: string };
export type ExactRevisionRef = { resourceType: string; resourceId: string; revision: number; contentHash: string };

export type TaskBriefRevision = {
  tenant: Tenant;
  briefId: string;
  taskId: string;
  revision: number;
  version: number;
  briefType: string;
  schemaRef: ResourceRef;
  spec: Record<string, unknown>;
  contentHash: string;
  lifecycle: "draft" | "frozen" | "withdrawn" | "superseded";
  createdBy: string;
  createdAt: string;
};

export type EvidenceBundleRevision = {
  tenant: Tenant;
  bundleId: string;
  revision: number;
  briefRef: ExactRevisionRef;
  subjectRefs: ResourceRef[];
  cutoffAt: string;
  itemRefs: ExactRevisionRef[];
  coverage: "complete" | "partial" | "blocked" | "unknown";
  missing: Record<string, unknown>[];
  conflicts: Record<string, unknown>[];
  uncertainties: Record<string, unknown>[];
  freshness: "fresh" | "stale" | "blocked" | "unknown";
  marking: string[];
  licenseSummary: Record<string, unknown>;
  contentHash: string;
  lifecycle: "frozen";
  createdBy: string;
  createdAt: string;
};

export type TaskBriefListResponse = { tenant: Tenant; items: TaskBriefRevision[]; count: number };
export type EvidenceBundleListResponse = { tenant: Tenant; items: EvidenceBundleRevision[]; count: number };

export type CreateTaskBriefInput = {
  taskId: string;
  briefType: string;
  schemaRef: ResourceRef;
  spec: Record<string, unknown>;
};

export type ContractLifecycle = "draft" | "frozen" | "withdrawn" | "superseded";
export type ContractReadiness = "ready" | "blocked" | "stale" | "unknown";
export type ContractCoverage = "complete" | "partial" | "blocked" | "unknown";
export type AssigneeKind = "agent_instance" | "human_principal" | "tool_binding" | "provider_capability_binding";

export type ContractBlocker = {
  code: string;
  message: string;
  resourceRef: ExactRevisionRef | null;
};

export type CreateEvalContractInput = {
  suiteRef: ExactRevisionRef;
  publicationRef: ExactRevisionRef | null;
  releaseGateRef: ExactRevisionRef | null;
  artifactSchemaRef: ResourceRef;
  severityThresholds: Record<string, number>;
  gatePolicy: Record<string, unknown>;
  returnMapping: Record<string, string>;
  overridePolicy: Record<string, unknown>;
};

export type ReviseEvalContractInput = CreateEvalContractInput & { expectedVersion: number };

export type EvalContractRevision = CreateEvalContractInput & {
  tenant: Tenant;
  contractId: string;
  revision: number;
  version: number;
  contentHash: string;
  lifecycle: ContractLifecycle;
  readiness: ContractReadiness;
  blockers: ContractBlocker[];
  createdBy: string;
  createdAt: string;
};

export type EvalContractListResponse = { tenant: Tenant; items: EvalContractRevision[]; count: number };

export type AssigneeRef = { kind: AssigneeKind; resourceId: string; version: number };
export type ResponsibilitySlot = {
  slotId: string;
  responsibilityType: string;
  requiredCapabilityIds: string[];
  inputSchemaRef: ResourceRef;
  outputSchemaRef: ResourceRef;
  gateRefs: ExactRevisionRef[];
  returnStage: string;
  assignee: AssigneeRef;
};
export type MergeDecision = {
  sourceSlotIds: string[];
  targetSlotId: string;
  reason: string;
  mergedResponsibilityTypes: string[];
};
export type CreateResponsibilityPlanInput = {
  profile: string;
  templateRef: ExactRevisionRef;
  slots: ResponsibilitySlot[];
  mergeDecisions: MergeDecision[];
};
export type ReviseResponsibilityPlanInput = CreateResponsibilityPlanInput & { expectedVersion: number };
export type ResponsibilityPlanRevision = CreateResponsibilityPlanInput & {
  tenant: Tenant;
  planId: string;
  revision: number;
  version: number;
  coverage: ContractCoverage;
  uncoveredSlots: string[];
  contentHash: string;
  lifecycle: ContractLifecycle;
  readiness: ContractReadiness;
  blockers: ContractBlocker[];
  createdBy: string;
  createdAt: string;
};
export type ResponsibilityPlanListResponse = { tenant: Tenant; items: ResponsibilityPlanRevision[]; count: number };
