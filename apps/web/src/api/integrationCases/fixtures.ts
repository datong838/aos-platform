import type {
  CurrentIntegrationCaseDetail,
  IntegrationCaseListResponse,
  IntegrationCaseTimelineResponse,
  IntegrationEvidenceSnapshotResponse,
  IntegrationStageGate,
  ReferenceIntegrationCaseDetail,
} from "./types";

export const CASE_ID = "00000000-0000-4000-8000-000000000101";
export const REFERENCE_CASE_ID = "00000000-0000-4000-8000-000000000102";
export const INSTALLATION_ID = "00000000-0000-4000-8000-000000000103";
export const COMPOSITION_ID = "00000000-0000-4000-8000-000000000104";
export const EVIDENCE_ID = "00000000-0000-4000-8000-000000000105";
export const BLOCKER_ID = "00000000-0000-4000-8000-000000000106";
export const HASH_A = `sha256:${"a".repeat(64)}`;
export const HASH_B = `sha256:${"b".repeat(64)}`;
const CUTOFF = "2026-08-03T09:00:00+00:00";
const OWNER_REF = "subject:case-owner-001";

const CURRENT_STAGE_GATES = [
  { stage: "planned", status: "satisfied", evidenceRefs: [HASH_A], reasonRefs: [] },
  { stage: "connection_verified", status: "satisfied", evidenceRefs: [HASH_B], reasonRefs: [] },
  { stage: "data_verified", status: "blocked", evidenceRefs: [], reasonRefs: ["missing:pipeline_run"] },
  { stage: "ontology_verified", status: "not_evaluated", evidenceRefs: [], reasonRefs: [] },
  { stage: "logic_verified", status: "not_evaluated", evidenceRefs: [], reasonRefs: [] },
  { stage: "workshop_verified", status: "not_evaluated", evidenceRefs: [], reasonRefs: [] },
  { stage: "production_ready", status: "not_evaluated", evidenceRefs: [], reasonRefs: [] },
  { stage: "production_active", status: "not_evaluated", evidenceRefs: [], reasonRefs: [] },
] satisfies IntegrationStageGate[];

const REFERENCE_STAGE_GATES = [
  { stage: "planned", status: "satisfied", evidenceRefs: [HASH_A], reasonRefs: [] },
  { stage: "connection_verified", status: "satisfied", evidenceRefs: [HASH_B], reasonRefs: [] },
  { stage: "data_verified", status: "satisfied", evidenceRefs: [HASH_A], reasonRefs: [] },
  { stage: "ontology_verified", status: "satisfied", evidenceRefs: [HASH_B], reasonRefs: [] },
  { stage: "logic_verified", status: "satisfied", evidenceRefs: [HASH_A], reasonRefs: [] },
  { stage: "workshop_verified", status: "satisfied", evidenceRefs: [HASH_B], reasonRefs: [] },
  { stage: "production_ready", status: "not_evaluated", evidenceRefs: [], reasonRefs: [] },
  { stage: "production_active", status: "not_evaluated", evidenceRefs: [], reasonRefs: [] },
] satisfies IntegrationStageGate[];

const countMetric = (value: number, eligibleCaseCount = 1) => ({
  value,
  aggregation: "count" as const,
  measuredCaseCount: eligibleCaseCount,
  eligibleCaseCount,
  cutoffAt: CUTOFF,
});

export const CURRENT_STATS = {
  caseCount: countMetric(1),
  productionActiveCount: countMetric(0),
  connectorCount: { ...countMetric(1), aggregation: "distinct_count" as const },
  pipelineCount: { value: null, aggregation: "distinct_count" as const, measuredCaseCount: 0, eligibleCaseCount: 1, cutoffAt: CUTOFF },
  datasetRowCount: { value: 0, aggregation: "sum" as const, measuredCaseCount: 1, eligibleCaseCount: 1, cutoffAt: CUTOFF },
  latencyMs: { value: null, aggregation: "max" as const, measuredCaseCount: 0, eligibleCaseCount: 1, cutoffAt: CUTOFF },
};

const CURRENT_METRICS = {
  connectorCount: CURRENT_STATS.connectorCount,
  pipelineCount: CURRENT_STATS.pipelineCount,
  datasetRowCount: CURRENT_STATS.datasetRowCount,
  latencyMs: CURRENT_STATS.latencyMs,
};

export const CURRENT_CASE_LIST_FIXTURE: IntegrationCaseListResponse = {
  scope: "current",
  items: [{
    caseId: CASE_ID,
    scope: "current",
    displayName: "Current commerce case",
    owner: OWNER_REF,
    installationId: INSTALLATION_ID,
    overlayRevision: "overlay-7",
    computedStage: "connection_verified",
    snapshotRevision: 2,
    cutoffAt: CUTOFF,
    blockerCount: 1,
    etagVersion: 3,
    createdAt: "2026-08-03T08:00:00+00:00",
    updatedAt: CUTOFF,
  }],
  total: 1,
  limit: 50,
  offset: 0,
  stats: CURRENT_STATS,
};

export const REFERENCE_CASE_LIST_FIXTURE: IntegrationCaseListResponse = {
  scope: "reference",
  items: [{
    caseId: REFERENCE_CASE_ID,
    scope: "reference",
    displayName: "Anonymized reference",
    owner: null,
    installationId: null,
    overlayRevision: null,
    computedStage: "workshop_verified",
    snapshotRevision: 5,
    cutoffAt: CUTOFF,
    blockerCount: 0,
    etagVersion: 1,
    createdAt: "2026-08-01T08:00:00+00:00",
    updatedAt: CUTOFF,
  }],
  total: 1,
  limit: 50,
  offset: 0,
  stats: null,
};

export const CURRENT_CASE_DETAIL_FIXTURE: CurrentIntegrationCaseDetail = {
  ...CURRENT_CASE_LIST_FIXTURE.items[0] as CurrentIntegrationCaseDetail,
  installationRevision: 5,
  compositionId: COMPOSITION_ID,
  lockRevision: 2,
  lockHash: HASH_A,
  stageGates: [...CURRENT_STAGE_GATES],
  latestEvidence: [{
    evidenceId: EVIDENCE_ID,
    revision: 2,
    evidenceType: "source_connection",
    subjectRef: "connector:commerce-primary",
    artifactHash: HASH_A,
    outcome: "valid",
    observedAt: "2026-08-03T08:55:00+00:00",
    expiresAt: "2026-08-03T10:00:00+00:00",
    revokedAt: null,
    evidenceHash: HASH_B,
    recordedAt: "2026-08-03T08:56:00+00:00",
  }],
  blockers: [{
    blockerId: BLOCKER_ID,
    code: "MISSING_PIPELINE_RUN",
    severity: "high",
    status: "open",
    gate: "data_verified",
    reasonRefs: ["missing:pipeline_run"],
    evidenceRefs: [],
    owner: OWNER_REF,
    firstObservedAt: "2026-08-03T08:57:00+00:00",
    updatedAt: CUTOFF,
  }],
  nextProjectionAt: "2026-08-03T10:00:00+00:00",
  metrics: CURRENT_METRICS,
};

export const REFERENCE_CASE_DETAIL_FIXTURE: ReferenceIntegrationCaseDetail = {
  ...REFERENCE_CASE_LIST_FIXTURE.items[0] as ReferenceIntegrationCaseDetail,
  installationRevision: null,
  compositionId: null,
  lockRevision: null,
  lockHash: null,
  stageGates: [...REFERENCE_STAGE_GATES],
  latestEvidence: [],
  blockers: [],
  nextProjectionAt: null,
  metrics: null,
};

export const TIMELINE_FIXTURE: IntegrationCaseTimelineResponse = {
  caseId: CASE_ID,
  scope: "current",
  items: [{
    sequence: 1,
    snapshotRevision: 1,
    oldStage: null,
    newStage: "planned",
    cause: "created",
    reasonRefs: [HASH_A],
    createdAt: "2026-08-03T08:00:00+00:00",
  }, {
    sequence: 2,
    snapshotRevision: 2,
    oldStage: "planned",
    newStage: "connection_verified",
    cause: "evidence_added",
    reasonRefs: [HASH_B],
    createdAt: CUTOFF,
  }],
  total: 2,
  limit: 50,
  offset: 0,
};

export const SNAPSHOT_FIXTURE: IntegrationEvidenceSnapshotResponse = {
  caseId: CASE_ID,
  instanceRevision: 5,
  snapshotRevision: 2,
  snapshotHash: HASH_A,
  stagePolicyVersion: "aos.integration-stage/v1",
  computedStage: "connection_verified",
  stageGates: [...CURRENT_STAGE_GATES],
  blockerRefs: [BLOCKER_ID],
  cutoffAt: CUTOFF,
  nextProjectionAt: "2026-08-03T10:00:00+00:00",
  evidenceCount: 2,
  etagVersion: 3,
  createdAt: CUTOFF,
};
