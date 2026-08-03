export const INTEGRATION_CASE_SCOPES = ["current", "reference"] as const;
export type IntegrationCaseScope = (typeof INTEGRATION_CASE_SCOPES)[number];

export const INTEGRATION_CASE_STAGES = [
  "planned",
  "connection_verified",
  "data_verified",
  "ontology_verified",
  "logic_verified",
  "workshop_verified",
  "production_ready",
  "production_active",
] as const;
export type IntegrationCaseStage = (typeof INTEGRATION_CASE_STAGES)[number];

export type StageGateStatus = "satisfied" | "blocked" | "not_evaluated";
export type EvidenceOutcome = "valid" | "invalid" | "revoked";
export const INTEGRATION_EVIDENCE_TYPES = [
  "source_connection",
  "tenant_isolation",
  "pipeline_run",
  "dataset_revision",
  "data_quality",
  "ontology_revision",
  "mapping_validation",
  "logic_publication",
  "logic_eval",
  "workshop_validation",
  "action_safety",
  "operations_readiness",
  "security_validation",
  "runtime_health",
] as const;
export type IntegrationEvidenceType = (typeof INTEGRATION_EVIDENCE_TYPES)[number];
export type BlockerSeverity = "critical" | "high" | "medium" | "low";
export type BlockerStatus = "open" | "resolved";
export type TimelineCause =
  | "created"
  | "evidence_added"
  | "negative_observed"
  | "evidence_expired"
  | "evidence_revoked"
  | "projection_rebuilt";
export type MetricAggregation = "count" | "distinct_count" | "sum" | "max";

export interface IntegrationMetric {
  value: number | null;
  aggregation: MetricAggregation;
  measuredCaseCount: number;
  eligibleCaseCount: number;
  cutoffAt: string;
}

export interface IntegrationCaseStats {
  caseCount: IntegrationMetric;
  productionActiveCount: IntegrationMetric;
  connectorCount: IntegrationMetric;
  pipelineCount: IntegrationMetric;
  datasetRowCount: IntegrationMetric;
  latencyMs: IntegrationMetric;
}

export type IntegrationCaseMetrics = Pick<
  IntegrationCaseStats,
  "connectorCount" | "pipelineCount" | "datasetRowCount" | "latencyMs"
>;

interface IntegrationCaseListItemBase {
  caseId: string;
  displayName: string;
  computedStage: IntegrationCaseStage;
  snapshotRevision: number | null;
  cutoffAt: string | null;
  blockerCount: number;
  etagVersion: number;
  createdAt: string;
  updatedAt: string;
}

export interface CurrentIntegrationCaseListItem extends IntegrationCaseListItemBase {
  scope: "current";
  owner: string;
  installationId: string;
  overlayRevision: string;
}

/** Reference copies deliberately cannot disclose tenant installation or owner identity. */
export interface ReferenceIntegrationCaseListItem extends IntegrationCaseListItemBase {
  scope: "reference";
  owner: null;
  installationId: null;
  overlayRevision: null;
}

export type IntegrationCaseListItem =
  | CurrentIntegrationCaseListItem
  | ReferenceIntegrationCaseListItem;

export interface IntegrationCaseListResponse {
  scope: IntegrationCaseScope;
  items: IntegrationCaseListItem[];
  total: number;
  limit: number;
  offset: number;
  /** Reference results always return null so they cannot contaminate tenant statistics. */
  stats: IntegrationCaseStats | null;
}

export interface IntegrationStageGate {
  stage: IntegrationCaseStage;
  status: StageGateStatus;
  evidenceRefs: string[];
  reasonRefs: string[];
}

export interface IntegrationEvidenceSummary {
  evidenceId: string;
  revision: number;
  evidenceType: IntegrationEvidenceType;
  subjectRef: string;
  artifactHash: string;
  outcome: EvidenceOutcome;
  observedAt: string;
  expiresAt: string | null;
  revokedAt: string | null;
  evidenceHash: string;
  recordedAt: string;
}

export interface IntegrationBlocker {
  blockerId: string;
  code: string;
  severity: BlockerSeverity;
  status: BlockerStatus;
  gate: IntegrationCaseStage;
  reasonRefs: string[];
  evidenceRefs: string[];
  owner: string | null;
  firstObservedAt: string;
  updatedAt: string;
}

interface IntegrationCaseDetailBase extends IntegrationCaseListItemBase {
  stageGates: IntegrationStageGate[];
  latestEvidence: IntegrationEvidenceSummary[];
  blockers: IntegrationBlocker[];
  nextProjectionAt: string | null;
  metrics: IntegrationCaseMetrics | null;
}

export interface CurrentIntegrationCaseDetail extends IntegrationCaseDetailBase {
  scope: "current";
  owner: string;
  installationId: string;
  installationRevision: number;
  overlayRevision: string;
  compositionId: string;
  lockRevision: number;
  lockHash: string;
}

export interface ReferenceIntegrationCaseDetail extends IntegrationCaseDetailBase {
  scope: "reference";
  owner: null;
  installationId: null;
  installationRevision: null;
  overlayRevision: null;
  compositionId: null;
  lockRevision: null;
  lockHash: null;
}

export type IntegrationCaseDetail =
  | CurrentIntegrationCaseDetail
  | ReferenceIntegrationCaseDetail;

export interface IntegrationStageEvent {
  sequence: number;
  snapshotRevision: number;
  oldStage: IntegrationCaseStage | null;
  newStage: IntegrationCaseStage;
  cause: TimelineCause;
  reasonRefs: string[];
  createdAt: string;
}

export interface IntegrationCaseTimelineResponse {
  caseId: string;
  scope: IntegrationCaseScope;
  items: IntegrationStageEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface IntegrationEvidenceSnapshotResponse {
  caseId: string;
  instanceRevision: number;
  snapshotRevision: number;
  snapshotHash: string;
  stagePolicyVersion: "aos.integration-stage/v1";
  computedStage: IntegrationCaseStage;
  stageGates: IntegrationStageGate[];
  blockerRefs: string[];
  cutoffAt: string;
  nextProjectionAt: string | null;
  evidenceCount: number;
  etagVersion: number;
  createdAt: string;
}

export interface CreateIntegrationCaseRequest {
  installationId: string;
  overlayRevision: string;
  displayName: string;
}

export type CreateIntegrationEvidenceSnapshotRequest = Record<string, never>;
