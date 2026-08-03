import {
  INTEGRATION_CASE_SCOPES,
  INTEGRATION_CASE_STAGES,
  INTEGRATION_EVIDENCE_TYPES,
  type BlockerSeverity,
  type BlockerStatus,
  type CreateIntegrationCaseRequest,
  type EvidenceOutcome,
  type IntegrationCaseDetail,
  type IntegrationCaseListItem,
  type IntegrationCaseListResponse,
  type IntegrationCaseScope,
  type IntegrationCaseStage,
  type IntegrationCaseStats,
  type IntegrationEvidenceSnapshotResponse,
  type IntegrationEvidenceType,
  type IntegrationCaseTimelineResponse,
  type MetricAggregation,
  type StageGateStatus,
  type TimelineCause,
} from "./types";

const SCOPES = new Set<IntegrationCaseScope>(INTEGRATION_CASE_SCOPES);
const STAGES = new Set<IntegrationCaseStage>(INTEGRATION_CASE_STAGES);
const GATE_STATUSES = new Set<StageGateStatus>(["satisfied", "blocked", "not_evaluated"]);
const OUTCOMES = new Set<EvidenceOutcome>(["valid", "invalid", "revoked"]);
const EVIDENCE_TYPES = new Set<IntegrationEvidenceType>(INTEGRATION_EVIDENCE_TYPES);
const SEVERITIES = new Set<BlockerSeverity>(["critical", "high", "medium", "low"]);
const BLOCKER_STATUSES = new Set<BlockerStatus>(["open", "resolved"]);
const CAUSES = new Set<TimelineCause>([
  "evidence_recorded", "evidence_invalidated", "evidence_expired",
  "evidence_revoked", "evidence_renewed", "projection_rebuilt",
]);
const AGGREGATIONS = new Set<MetricAggregation>(["count", "distinct_count", "sum", "max"]);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const SHA256 = /^sha256:[0-9a-f]{64}$/;
const TIMEZONE_SUFFIX = /(?:Z|[+-][0-9]{2}:[0-9]{2})$/;

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

function exactKeys(value: Record<string, unknown>, keys: readonly string[], label: string): void {
  const allowed = new Set(keys);
  const missing = keys.filter((key) => !(key in value));
  const extra = Object.keys(value).filter((key) => !allowed.has(key));
  if (missing.length || extra.length) {
    throw new Error(`${label} keys mismatch; missing=${missing.join(",")}; extra=${extra.join(",")}`);
  }
}

function normalizedString(value: unknown, label: string): asserts value is string {
  if (typeof value !== "string" || value.length === 0 || value !== value.trim() || value.includes("\0")) {
    throw new Error(`${label} must be a non-empty normalized string`);
  }
}

function uuid(value: unknown, label: string): asserts value is string {
  normalizedString(value, label);
  if (!UUID.test(value)) throw new Error(`${label} must be a canonical lowercase UUID`);
}

function sha256(value: unknown, label: string): asserts value is string {
  normalizedString(value, label);
  if (!SHA256.test(value)) throw new Error(`${label} must be a sha256 digest`);
}

function timestamp(value: unknown, label: string): asserts value is string {
  normalizedString(value, label);
  if (!value.includes("T") || !TIMEZONE_SUFFIX.test(value) || Number.isNaN(Date.parse(value))) {
    throw new Error(`${label} must be an ISO timestamp with timezone`);
  }
}

function nullableTimestamp(value: unknown, label: string): void {
  if (value !== null) timestamp(value, label);
}

function positiveInteger(value: unknown, label: string): asserts value is number {
  if (!Number.isSafeInteger(value) || (value as number) < 1) throw new Error(`${label} must be a positive safe integer`);
}

function nonNegativeInteger(value: unknown, label: string): asserts value is number {
  if (!Number.isSafeInteger(value) || (value as number) < 0) throw new Error(`${label} must be a non-negative safe integer`);
}

function scope(value: unknown, label: string): asserts value is IntegrationCaseScope {
  if (!SCOPES.has(value as IntegrationCaseScope)) throw new Error(`${label} is invalid`);
}

function stage(value: unknown, label: string): asserts value is IntegrationCaseStage {
  if (!STAGES.has(value as IntegrationCaseStage)) throw new Error(`${label} is invalid`);
}

function stringArray(value: unknown, label: string): asserts value is string[] {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
  value.forEach((entry, index) => normalizedString(entry, `${label}[${index}]`));
  if (new Set(value).size !== value.length) throw new Error(`${label} must not contain duplicates`);
}

const METRIC_KEYS = ["value", "aggregation", "measuredCaseCount", "eligibleCaseCount", "cutoffAt"] as const;
function metric(value: unknown, label: string): void {
  const item = record(value, label);
  exactKeys(item, METRIC_KEYS, label);
  if (item.value !== null && (typeof item.value !== "number" || !Number.isFinite(item.value) || item.value < 0)) {
    throw new Error(`${label}.value must be null or a non-negative finite number`);
  }
  if (!AGGREGATIONS.has(item.aggregation as MetricAggregation)) throw new Error(`${label}.aggregation is invalid`);
  nonNegativeInteger(item.measuredCaseCount, `${label}.measuredCaseCount`);
  nonNegativeInteger(item.eligibleCaseCount, `${label}.eligibleCaseCount`);
  if (item.measuredCaseCount > item.eligibleCaseCount) throw new Error(`${label}.measuredCaseCount exceeds eligibleCaseCount`);
  if (item.value === null && item.measuredCaseCount !== 0) throw new Error(`${label}.null value requires zero measured cases`);
  timestamp(item.cutoffAt, `${label}.cutoffAt`);
}

const STATS_KEYS = ["caseCount", "productionActiveCount", "connectorCount", "pipelineCount", "datasetRowCount", "latencyMs"] as const;
function stats(value: unknown, label: string): asserts value is IntegrationCaseStats {
  const item = record(value, label);
  exactKeys(item, STATS_KEYS, label);
  STATS_KEYS.forEach((key) => metric(item[key], `${label}.${key}`));
}

const LIST_ITEM_KEYS = [
  "caseId", "scope", "displayName", "owner", "installationId", "overlayRevision",
  "computedStage", "snapshotRevision", "cutoffAt", "blockerCount", "etagVersion", "createdAt", "updatedAt",
] as const;

function listItem(value: unknown, label: string): IntegrationCaseListItem {
  const item = record(value, label);
  exactKeys(item, LIST_ITEM_KEYS, label);
  uuid(item.caseId, `${label}.caseId`);
  scope(item.scope, `${label}.scope`);
  normalizedString(item.displayName, `${label}.displayName`);
  if (item.scope === "current") {
    normalizedString(item.owner, `${label}.owner`);
    uuid(item.installationId, `${label}.installationId`);
    normalizedString(item.overlayRevision, `${label}.overlayRevision`);
  } else if (item.owner !== null || item.installationId !== null || item.overlayRevision !== null) {
    throw new Error(`${label} reference identity fields must be null`);
  }
  stage(item.computedStage, `${label}.computedStage`);
  if (item.snapshotRevision !== null) positiveInteger(item.snapshotRevision, `${label}.snapshotRevision`);
  nullableTimestamp(item.cutoffAt, `${label}.cutoffAt`);
  if ((item.snapshotRevision === null) !== (item.cutoffAt === null)) throw new Error(`${label} snapshotRevision and cutoffAt must be jointly null or present`);
  nonNegativeInteger(item.blockerCount, `${label}.blockerCount`);
  positiveInteger(item.etagVersion, `${label}.etagVersion`);
  timestamp(item.createdAt, `${label}.createdAt`);
  timestamp(item.updatedAt, `${label}.updatedAt`);
  if (Date.parse(item.updatedAt) < Date.parse(item.createdAt)) throw new Error(`${label}.updatedAt precedes createdAt`);
  return value as IntegrationCaseListItem;
}

function stageGate(value: unknown, label: string): void {
  const item = record(value, label);
  exactKeys(item, ["stage", "status", "evidenceRefs", "reasonRefs"], label);
  stage(item.stage, `${label}.stage`);
  if (!GATE_STATUSES.has(item.status as StageGateStatus)) throw new Error(`${label}.status is invalid`);
  stringArray(item.evidenceRefs, `${label}.evidenceRefs`);
  stringArray(item.reasonRefs, `${label}.reasonRefs`);
}

function evidence(value: unknown, label: string): void {
  const item = record(value, label);
  exactKeys(item, ["evidenceId", "revision", "evidenceType", "subjectRef", "artifactHash", "outcome", "observedAt", "expiresAt", "revokedAt", "evidenceHash", "recordedAt"], label);
  uuid(item.evidenceId, `${label}.evidenceId`);
  positiveInteger(item.revision, `${label}.revision`);
  if (!EVIDENCE_TYPES.has(item.evidenceType as IntegrationEvidenceType)) throw new Error(`${label}.evidenceType is invalid`);
  normalizedString(item.subjectRef, `${label}.subjectRef`);
  sha256(item.artifactHash, `${label}.artifactHash`);
  if (!OUTCOMES.has(item.outcome as EvidenceOutcome)) throw new Error(`${label}.outcome is invalid`);
  timestamp(item.observedAt, `${label}.observedAt`);
  nullableTimestamp(item.expiresAt, `${label}.expiresAt`);
  nullableTimestamp(item.revokedAt, `${label}.revokedAt`);
  sha256(item.evidenceHash, `${label}.evidenceHash`);
  timestamp(item.recordedAt, `${label}.recordedAt`);
  if ((item.outcome === "revoked") !== (item.revokedAt !== null)) throw new Error(`${label}.revokedAt is inconsistent with outcome`);
}

function blocker(value: unknown, label: string): void {
  const item = record(value, label);
  exactKeys(item, ["blockerId", "code", "severity", "status", "gate", "reasonRefs", "evidenceRefs", "owner", "firstObservedAt", "updatedAt"], label);
  uuid(item.blockerId, `${label}.blockerId`);
  normalizedString(item.code, `${label}.code`);
  if (!SEVERITIES.has(item.severity as BlockerSeverity)) throw new Error(`${label}.severity is invalid`);
  if (!BLOCKER_STATUSES.has(item.status as BlockerStatus)) throw new Error(`${label}.status is invalid`);
  stage(item.gate, `${label}.gate`);
  stringArray(item.reasonRefs, `${label}.reasonRefs`);
  stringArray(item.evidenceRefs, `${label}.evidenceRefs`);
  if (item.owner !== null) normalizedString(item.owner, `${label}.owner`);
  timestamp(item.firstObservedAt, `${label}.firstObservedAt`);
  timestamp(item.updatedAt, `${label}.updatedAt`);
}

export function parseIntegrationCaseList(value: unknown): IntegrationCaseListResponse {
  const response = record(value, "Integration case list");
  exactKeys(response, ["scope", "items", "total", "limit", "offset", "stats"], "Integration case list");
  scope(response.scope, "Integration case list.scope");
  if (!Array.isArray(response.items)) throw new Error("Integration case list.items must be an array");
  const items = response.items.map((entry, index) => listItem(entry, `Integration case list.items[${index}]`));
  if (items.some((entry) => entry.scope !== response.scope)) throw new Error("Integration case list cannot mix current and reference items");
  nonNegativeInteger(response.total, "Integration case list.total");
  positiveInteger(response.limit, "Integration case list.limit");
  nonNegativeInteger(response.offset, "Integration case list.offset");
  if (items.length > response.limit || response.total < items.length) throw new Error("Integration case list pagination is inconsistent");
  if (response.scope === "current") stats(response.stats, "Integration case list.stats");
  else if (response.stats !== null) throw new Error("Reference case list stats must be null");
  return value as IntegrationCaseListResponse;
}

const DETAIL_KEYS = [
  ...LIST_ITEM_KEYS, "installationRevision", "compositionId", "lockRevision", "lockHash",
  "stageGates", "latestEvidence", "blockers", "nextProjectionAt", "metrics",
] as const;

export function parseIntegrationCaseDetail(value: unknown): IntegrationCaseDetail {
  const item = record(value, "Integration case detail");
  exactKeys(item, DETAIL_KEYS, "Integration case detail");
  listItem(Object.fromEntries(LIST_ITEM_KEYS.map((key) => [key, item[key]])), "Integration case detail");
  if (item.scope === "current") {
    positiveInteger(item.installationRevision, "Integration case detail.installationRevision");
    uuid(item.compositionId, "Integration case detail.compositionId");
    positiveInteger(item.lockRevision, "Integration case detail.lockRevision");
    sha256(item.lockHash, "Integration case detail.lockHash");
  } else if (item.installationRevision !== null || item.compositionId !== null || item.lockRevision !== null || item.lockHash !== null) {
    throw new Error("Integration case detail reference binding fields must be null");
  }
  if (!Array.isArray(item.stageGates)) throw new Error("Integration case detail.stageGates must be an array");
  item.stageGates.forEach((entry, index) => stageGate(entry, `Integration case detail.stageGates[${index}]`));
  const gateStages = item.stageGates.map((entry) => (entry as { stage: string }).stage);
  if (new Set(gateStages).size !== gateStages.length) throw new Error("Integration case detail.stageGates contains duplicate stages");
  if (!Array.isArray(item.latestEvidence)) throw new Error("Integration case detail.latestEvidence must be an array");
  item.latestEvidence.forEach((entry, index) => evidence(entry, `Integration case detail.latestEvidence[${index}]`));
  if (!Array.isArray(item.blockers)) throw new Error("Integration case detail.blockers must be an array");
  item.blockers.forEach((entry, index) => blocker(entry, `Integration case detail.blockers[${index}]`));
  if (item.blockers.filter((entry) => (entry as { status: string }).status === "open").length !== item.blockerCount) throw new Error("Integration case detail.blockerCount does not match open blockers");
  nullableTimestamp(item.nextProjectionAt, "Integration case detail.nextProjectionAt");
  if (item.scope === "current") stats(item.metrics, "Integration case detail.metrics");
  else if (item.metrics !== null) throw new Error("Reference case metrics must be null");
  return value as IntegrationCaseDetail;
}

export function parseIntegrationCaseTimeline(value: unknown): IntegrationCaseTimelineResponse {
  const response = record(value, "Integration case timeline");
  exactKeys(response, ["caseId", "scope", "items", "total", "limit", "offset"], "Integration case timeline");
  uuid(response.caseId, "Integration case timeline.caseId");
  scope(response.scope, "Integration case timeline.scope");
  if (!Array.isArray(response.items)) throw new Error("Integration case timeline.items must be an array");
  let previousSequence = 0;
  response.items.forEach((entry, index) => {
    const item = record(entry, `Integration case timeline.items[${index}]`);
    exactKeys(item, ["sequence", "snapshotRevision", "oldStage", "newStage", "cause", "reasonRefs", "createdAt"], `Integration case timeline.items[${index}]`);
    positiveInteger(item.sequence, `Timeline event[${index}].sequence`);
    positiveInteger(item.snapshotRevision, `Timeline event[${index}].snapshotRevision`);
    stage(item.oldStage, `Timeline event[${index}].oldStage`);
    stage(item.newStage, `Timeline event[${index}].newStage`);
    if (item.oldStage === item.newStage) throw new Error(`Timeline event[${index}] must change stage`);
    if (!CAUSES.has(item.cause as TimelineCause)) throw new Error(`Timeline event[${index}].cause is invalid`);
    stringArray(item.reasonRefs, `Timeline event[${index}].reasonRefs`);
    timestamp(item.createdAt, `Timeline event[${index}].createdAt`);
    if (item.sequence <= previousSequence) throw new Error("Integration case timeline sequence must increase");
    previousSequence = item.sequence;
  });
  nonNegativeInteger(response.total, "Integration case timeline.total");
  positiveInteger(response.limit, "Integration case timeline.limit");
  nonNegativeInteger(response.offset, "Integration case timeline.offset");
  if (response.items.length > response.limit || response.total < response.items.length) throw new Error("Integration case timeline pagination is inconsistent");
  return value as IntegrationCaseTimelineResponse;
}

export function parseIntegrationEvidenceSnapshot(value: unknown): IntegrationEvidenceSnapshotResponse {
  const item = record(value, "Integration evidence snapshot");
  exactKeys(item, ["caseId", "snapshotRevision", "snapshotHash", "computedStage", "cutoffAt", "nextProjectionAt", "evidenceCount", "createdAt"], "Integration evidence snapshot");
  uuid(item.caseId, "Integration evidence snapshot.caseId");
  positiveInteger(item.snapshotRevision, "Integration evidence snapshot.snapshotRevision");
  sha256(item.snapshotHash, "Integration evidence snapshot.snapshotHash");
  stage(item.computedStage, "Integration evidence snapshot.computedStage");
  timestamp(item.cutoffAt, "Integration evidence snapshot.cutoffAt");
  nullableTimestamp(item.nextProjectionAt, "Integration evidence snapshot.nextProjectionAt");
  nonNegativeInteger(item.evidenceCount, "Integration evidence snapshot.evidenceCount");
  timestamp(item.createdAt, "Integration evidence snapshot.createdAt");
  return value as IntegrationEvidenceSnapshotResponse;
}

/** Strict boundary parser: stage, scope, evidence and cutoff injection are rejected. */
export function parseCreateIntegrationCaseRequest(value: unknown): CreateIntegrationCaseRequest {
  const item = record(value, "Create integration case request");
  exactKeys(item, ["installationId", "overlayRevision", "displayName"], "Create integration case request");
  uuid(item.installationId, "Create integration case request.installationId");
  normalizedString(item.overlayRevision, "Create integration case request.overlayRevision");
  normalizedString(item.displayName, "Create integration case request.displayName");
  return value as CreateIntegrationCaseRequest;
}

export function parseCreateIntegrationEvidenceSnapshotRequest(value: unknown): Record<string, never> {
  const item = record(value, "Create integration evidence snapshot request");
  exactKeys(item, [], "Create integration evidence snapshot request");
  return item as Record<string, never>;
}
