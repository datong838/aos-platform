export const MEMORY_CANDIDATE_STATUSES = ["pending", "quarantined", "rejected", "approved", "promoted"] as const;
export const MEMORY_ITEM_STATUSES = ["active", "stale", "revoked", "expired"] as const;
export const MEMORY_SCOPES = ["workspace", "organization", "public_package"] as const;
export const MEMORY_LAYERS = ["episodic", "semantic"] as const;
export const PIPELINE_KINDS = ["seed_import", "operational_learning", "network_learning", "competitor_analysis", "professional_database", "customer_feedback", "human_experience"] as const;
export const PIPELINE_TRIGGERS = ["manual", "task_event", "scheduled", "version_event", "domain_event"] as const;
export const PIPELINE_SCHEDULE_STATUSES = ["active", "paused", "disabled"] as const;
export const PIPELINE_RUN_STATUSES = ["queued", "running", "paused", "succeeded", "partial", "failed", "cancelled", "unknown"] as const;
export const PIPELINE_ALERT_SEVERITIES = ["warning", "error", "critical"] as const;
export const PIPELINE_OPERATIONAL_STATUSES = ["ready", "blocked", "paused", "disabled", "unconfigured"] as const;

export type MemoryCandidateStatus = typeof MEMORY_CANDIDATE_STATUSES[number];
export type MemoryItemStatus = typeof MEMORY_ITEM_STATUSES[number];
export type MemoryScope = typeof MEMORY_SCOPES[number];
export type MemoryLayer = typeof MEMORY_LAYERS[number];
export type KnowledgePipelineKind = typeof PIPELINE_KINDS[number];
export type KnowledgePipelineTrigger = typeof PIPELINE_TRIGGERS[number];
export type KnowledgePipelineScheduleStatus = typeof PIPELINE_SCHEDULE_STATUSES[number];
export type KnowledgePipelineRunStatus = typeof PIPELINE_RUN_STATUSES[number];
export type TenantContext = { orgId: string; projectId: string };
export type ResourceRef = { resourceType: string; resourceId: string; revision?: string; authority: string };
export type ArtifactRef = { artifactType: string; artifactId: string; revision: string; contentHash: string };
export type KnowledgeSourceRef = {
  sourceKind: string;
  sourceUri?: string;
  sourceRef?: ResourceRef;
  observedAt: string;
  freshnessExpiresAt: string;
  licenseId: string;
  usagePolicy: string;
  contentHash: string;
  provider: string;
  providerVersion: string;
  applicability: string[];
};
export type GovernanceApprovalRef = {
  evalReport: ArtifactRef;
  draft: ResourceRef;
  approvalEvent: ResourceRef;
};
export type SubmitMemoryCandidateRequest = {
  candidateLayer: MemoryLayer;
  taskId: string;
  runId: string;
  subject: ResourceRef;
  payload: ArtifactRef;
  source: KnowledgeSourceRef;
  confidence: number;
  marking: string[];
};
export type MemoryCandidate = {
  tenant: TenantContext;
  candidateId: string;
  status: MemoryCandidateStatus;
  scope: MemoryScope;
  version: number;
  createdAt: string;
  updatedAt: string;
  request: SubmitMemoryCandidateRequest;
  quarantineReasons: string[];
  governance?: GovernanceApprovalRef;
};
export type MemoryCandidateEvent = {
  tenant: TenantContext;
  eventId: string;
  candidateId: string;
  sequence: number;
  eventType: "submitted" | "quarantined" | "rejected" | "approved" | "promoted";
  fromStatus?: MemoryCandidateStatus;
  toStatus: MemoryCandidateStatus;
  reasonCodes: string[];
  evidenceRef?: ResourceRef;
  eventHash: string;
  actor: string;
  occurredAt: string;
};
export type MemoryAuthorityItem = {
  item: {
    tenant: TenantContext;
    memoryItemId: string;
    memoryLayer: MemoryLayer;
    status: MemoryItemStatus;
    scope: MemoryScope;
    currentRevision: number;
    version: number;
    subject: ResourceRef;
    createdAt: string;
    updatedAt: string;
  };
  revision: {
    tenant: TenantContext;
    memoryItemId: string;
    revision: number;
    candidateId: string;
    contentHash: string;
    sourceId: string;
    sourceRevision: number;
    payload: ArtifactRef;
    confidence: number;
    applicability: string[];
    markings: string[];
    effectiveAt: string;
    expiresAt?: string;
    createdBy: string;
    createdAt: string;
  };
};
export type KnowledgeCitation = {
  memoryItemId: string;
  revision: number;
  scope: MemoryScope;
  subject: ResourceRef;
  payload: ArtifactRef;
  contentHash: string;
  source: KnowledgeSourceRef;
  freshness: MemoryItemStatus;
  confidence: number;
  applicability: string[];
  markings: string[];
};
export type KnowledgeQueryResult = {
  status: "complete" | "degraded" | "blocked";
  citations: KnowledgeCitation[];
  chunks: { content: string; tokenCount: number; citation: KnowledgeCitation }[];
  blockedReasons: string[];
  assembledTokens: number;
};
export type KnowledgePipelinePolicy = {
  pipelineKind: KnowledgePipelineKind;
  allowedTriggers: KnowledgePipelineTrigger[];
  defaultStatus: KnowledgePipelineScheduleStatus;
  requiredDependencies: string[];
  allowedReceiptTypes: string[];
  allowedSourceKinds: string[];
};
export type KnowledgePipelineSchedule = {
  tenant: TenantContext;
  scheduleId: string;
  pipelineKind: KnowledgePipelineKind;
  trigger: KnowledgePipelineTrigger;
  config: ArtifactRef;
  status: KnowledgePipelineScheduleStatus;
  scheduleSpec?: string;
  checkpointVersion: number;
  version: number;
  nextRunAt?: string;
  createdAt: string;
  updatedAt: string;
};
export type KnowledgePipelineRun = {
  tenant: TenantContext;
  pipelineRunId: string;
  scheduleId: string;
  taskId: string;
  runId: string;
  trigger: KnowledgePipelineTrigger;
  status: KnowledgePipelineRunStatus;
  attempt: number;
  retryOfRunId?: string;
  expectedCheckpointVersion: number;
  idempotencyKey: string;
  requestHash: string;
  version: number;
  scheduledFor: string;
  leaseOwner?: string;
  leaseExpiresAt?: string;
  startedAt?: string;
  finishedAt?: string;
  createdAt: string;
  updatedAt: string;
};
export type KnowledgePipelineReceipt = {
  tenant: TenantContext;
  receiptId: string;
  pipelineRunId: string;
  status: KnowledgePipelineRunStatus;
  inputHash: string;
  outputHash: string;
  candidateRefs: ResourceRef[];
  checkpointBeforeVersion: number;
  checkpointAfterVersion: number;
  producedCount: number;
  failedCount: number;
  errorCodes: string[];
  receiptHash: string;
  createdAt: string;
};
export type KnowledgePipelineCheckpoint = {
  tenant: TenantContext;
  scheduleId: string;
  revision: number;
  pipelineRunId: string;
  receiptId: string;
  checkpoint: ArtifactRef;
  checkpointHash: string;
  createdAt: string;
};
export type KnowledgePipelineAlert = {
  tenant: TenantContext;
  alertId: string;
  pipelineRunId: string;
  code: string;
  severity: typeof PIPELINE_ALERT_SEVERITIES[number];
  evidenceRef: ResourceRef;
  alertHash: string;
  createdAt: string;
};
export type KnowledgePipelineOperationalReadiness = {
  tenant: TenantContext;
  pipelineKind: KnowledgePipelineKind;
  defaultStatus: KnowledgePipelineScheduleStatus;
  dependencyAllowed: boolean;
  dependencyReasonCodes: string[];
  adapterRequired: boolean;
  adapterRegistered: boolean;
  scheduleCounts: { status: string; count: number }[];
  runCounts: { status: string; count: number }[];
  lastRun?: KnowledgePipelineRun;
  lastReceipt?: KnowledgePipelineReceipt;
  lastCheckpoint?: KnowledgePipelineCheckpoint;
  alertCount: number;
  operationalStatus: typeof PIPELINE_OPERATIONAL_STATUSES[number];
  blockerCodes: string[];
  observedAt: string;
};
export type KnowledgePipelineOperationalReadinessEnvelope = {
  tenant: TenantContext;
  pipelines: KnowledgePipelineOperationalReadiness[];
  observedAt: string;
};
export type KnowledgeReadiness = {
  tenant: TenantContext;
  package: { status: "available" | "authority_unavailable"; count?: number; blocker?: string };
  sources: { provider: string; providerVersion: string; licenseId: string; usagePolicy: string; revisionCount: number; staleCount: number }[];
  sourceBlockers: string[];
  search: {
    referenceCount: number;
    providerConfigured: boolean;
    capabilities: { lane: "fulltext" | "vector" | "rerank"; status: "unbuilt" | "ready" | "degraded" | "blocked"; provider?: string; providerRevision?: string; reasonCode?: string; version: number; observedAt: string }[];
    blockers: string[];
  };
  eval: { status: "available" | "authority_unavailable"; count?: number; blocker?: string };
  observedAt: string;
};

export const MEMORY_PROJECTION_STATUSES = ["active", "suspended", "revoked", "expired", "stale"] as const;
export type VersionedAssetRef = { assetType: string; assetId: string; revision: number; contentHash: string };
export type MemoryAgentInstance = {
  tenant: TenantContext; instanceId: string; instanceRef: VersionedAssetRef; template: VersionedAssetRef;
  status: "provisioning" | "active" | "suspended" | "deleted";
  overlay: { displayName?: string; allowedCapabilityIds: string[] };
  version: number; createdBy: string; createdAt: string; updatedAt: string;
};
export type MemoryRevisionExactRef = { memoryItemId: string; revision: number; contentHash: string };
export type MemoryProjectionExactRef = { projectionId: string; version: number; contentHash: string };
export type MemoryAgentProjection = {
  tenant: TenantContext; projectionRef: MemoryProjectionExactRef; kind: "personal" | "shared";
  ownerInstanceRef: VersionedAssetRef; memoryRef: MemoryRevisionExactRef; recipientInstanceRefs: VersionedAssetRef[];
  allowedPurposes: string[]; allowedMarkings: string[]; disclosure: "citation_only" | "governed_summary";
  status: typeof MEMORY_PROJECTION_STATUSES[number]; effectiveAt: string; expiresAt: string;
  createdBy: string; createdAt: string; updatedAt: string;
};
export type CreateMemoryAgentProjectionRequest = Omit<MemoryAgentProjection, "tenant" | "projectionRef" | "status" | "createdBy" | "createdAt" | "updatedAt"> & { projectionId: string };
export type MemoryExposure = {
  tenant: TenantContext; exposureId: string; agentRunRef: ResourceRef; taskRunRef: ResourceRef;
  agentInstanceRef: VersionedAssetRef; skillRef: VersionedAssetRef; logicRef: VersionedAssetRef;
  projectionRef: MemoryProjectionExactRef; memoryRef: MemoryRevisionExactRef; evalContractRef: VersionedAssetRef;
  timeCutoff: string; acceptedAt: string; exposureHash: string;
};
export type ImprovementMetric = {
  metricName: "human_edit_rate" | "task_success_rate" | "citation_acceptance_rate";
  baselineValue: number; treatmentValue: number; baselineSampleSize: number; treatmentSampleSize: number;
  confidenceIntervalLower?: number; confidenceIntervalUpper?: number;
};
export type MemoryImprovementObservation = {
  tenant: TenantContext; observationId: string; agentInstanceRef: VersionedAssetRef;
  metricDefinitionRef: VersionedAssetRef; evalContractRef: VersionedAssetRef;
  evalReportRef?: VersionedAssetRef; baselineCohortRef?: VersionedAssetRef; treatmentCohortRef?: VersionedAssetRef;
  exposureRefs: VersionedAssetRef[]; metrics: ImprovementMetric[]; quality: "measured" | "estimated" | "unknown";
  sourceRefs: VersionedAssetRef[]; cutoffAt: string; observedAt: string;
  conclusion: "improved" | "unchanged" | "regressed" | "insufficient_evidence";
  limitations: string[]; observationHash: string;
};
export type MemoryRevocationImpact = {
  tenant: TenantContext; projectionRef: MemoryProjectionExactRef; projectionStatus: string;
  recipientCount: number; exposureCount: number; affectedAgentRunCount: number;
  affectedAgentRunRefs: ResourceRef[]; reEvaluationStatus: "not_required" | "required" | "blocked"; blockerCodes: string[];
};

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError(`${label} 响应格式无效`);
  return value as Record<string, unknown>;
}
function text(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new TypeError(`${label} 缺失`);
  return value;
}
function optionalText(value: unknown, label: string): string | undefined {
  return value == null ? undefined : text(value, label);
}
function integer(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 1) throw new TypeError(`${label} 无效`);
  return value as number;
}
function nonNegativeInteger(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 0) throw new TypeError(`${label} 无效`);
  return value as number;
}
function numberInRange(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) throw new TypeError(`${label} 无效`);
  return value;
}
function booleanValue(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") throw new TypeError(`${label} 无效`);
  return value;
}
function strings(value: unknown, label: string, requireValue = false): string[] {
  if (!Array.isArray(value) || (requireValue && !value.length) || value.some(v => typeof v !== "string" || !v.trim())) throw new TypeError(`${label} 无效`);
  return value as string[];
}
function enumValue<T extends readonly string[]>(value: unknown, allowed: T, label: string): T[number] {
  const result = text(value, label);
  if (!allowed.includes(result)) throw new TypeError(`${label} 未知`);
  return result as T[number];
}
function sha(value: unknown, label: string): string {
  const result = text(value, label);
  if (!/^[0-9a-f]{64}$/.test(result)) throw new TypeError(`${label} 不是 sha256`);
  return result;
}
function parseTenant(value: unknown, label: string): TenantContext {
  const v = record(value, label);
  return { orgId: text(v.orgId, `${label}.orgId`), projectId: text(v.projectId, `${label}.projectId`) };
}
function sameTenant(left: TenantContext, right: TenantContext): boolean {
  return left.orgId === right.orgId && left.projectId === right.projectId;
}
function parseResourceRef(value: unknown, label: string): ResourceRef {
  const v = record(value, label);
  return {
    resourceType: text(v.resourceType, `${label}.resourceType`),
    resourceId: text(v.resourceId, `${label}.resourceId`),
    revision: optionalText(v.revision, `${label}.revision`),
    authority: text(v.authority, `${label}.authority`),
  };
}
function parseArtifactRef(value: unknown, label: string): ArtifactRef {
  const v = record(value, label);
  return {
    artifactType: text(v.artifactType, `${label}.artifactType`),
    artifactId: text(v.artifactId, `${label}.artifactId`),
    revision: text(v.revision, `${label}.revision`),
    contentHash: sha(v.contentHash, `${label}.contentHash`),
  };
}
function parseSource(value: unknown, label: string): KnowledgeSourceRef {
  const v = record(value, label);
  const sourceUri = optionalText(v.sourceUri, `${label}.sourceUri`);
  const sourceRef = v.sourceRef == null ? undefined : parseResourceRef(v.sourceRef, `${label}.sourceRef`);
  if ((sourceUri ? 1 : 0) + (sourceRef ? 1 : 0) !== 1) throw new TypeError(`${label} 必须且只能包含一个 sourceUri/sourceRef`);
  return {
    sourceKind: text(v.sourceKind, `${label}.sourceKind`), sourceUri, sourceRef,
    observedAt: text(v.observedAt, `${label}.observedAt`), freshnessExpiresAt: text(v.freshnessExpiresAt, `${label}.freshnessExpiresAt`),
    licenseId: text(v.licenseId, `${label}.licenseId`), usagePolicy: text(v.usagePolicy, `${label}.usagePolicy`),
    contentHash: sha(v.contentHash, `${label}.contentHash`), provider: text(v.provider, `${label}.provider`),
    providerVersion: text(v.providerVersion, `${label}.providerVersion`), applicability: strings(v.applicability, `${label}.applicability`, true),
  };
}
function parseGovernance(value: unknown, label: string): GovernanceApprovalRef {
  const v = record(value, label);
  return { evalReport: parseArtifactRef(v.evalReport, `${label}.evalReport`), draft: parseResourceRef(v.draft, `${label}.draft`), approvalEvent: parseResourceRef(v.approvalEvent, `${label}.approvalEvent`) };
}
function parseCandidateRequest(value: unknown): SubmitMemoryCandidateRequest {
  const v = record(value, "request");
  return {
    candidateLayer: enumValue(v.candidateLayer, MEMORY_LAYERS, "candidateLayer"), taskId: text(v.taskId, "taskId"), runId: text(v.runId, "runId"),
    subject: parseResourceRef(v.subject, "subject"), payload: parseArtifactRef(v.payload, "payload"), source: parseSource(v.source, "source"),
    confidence: numberInRange(v.confidence, "confidence"), marking: strings(v.marking, "marking", true),
  };
}
function parseCitation(value: unknown, label: string): KnowledgeCitation {
  const v = record(value, label);
  const payload = parseArtifactRef(v.payload, `${label}.payload`);
  const contentHash = sha(v.contentHash, `${label}.contentHash`);
  if (payload.contentHash !== contentHash) throw new TypeError(`${label} payload/contentHash 不一致`);
  return {
    memoryItemId: text(v.memoryItemId, `${label}.memoryItemId`), revision: integer(v.revision, `${label}.revision`),
    scope: enumValue(v.scope, MEMORY_SCOPES, `${label}.scope`), subject: parseResourceRef(v.subject, `${label}.subject`), payload, contentHash,
    source: parseSource(v.source, `${label}.source`), freshness: enumValue(v.freshness, MEMORY_ITEM_STATUSES, `${label}.freshness`),
    confidence: numberInRange(v.confidence, `${label}.confidence`), applicability: strings(v.applicability, `${label}.applicability`, true), markings: strings(v.markings, `${label}.markings`, true),
  };
}

export function parseMemoryCandidate(value: unknown): MemoryCandidate {
  const v = record(value, "Candidate");
  const status = enumValue(v.status, MEMORY_CANDIDATE_STATUSES, "status");
  const governance = v.governance == null ? undefined : parseGovernance(v.governance, "governance");
  const quarantineReasons = strings(v.quarantineReasons, "quarantineReasons");
  if ((status === "approved" || status === "promoted") && !governance) throw new TypeError("approved/promoted Candidate 缺治理证据");
  if (status === "quarantined" && !quarantineReasons.length) throw new TypeError("quarantined Candidate 缺原因");
  return {
    tenant: parseTenant(v.tenant, "tenant"), candidateId: text(v.candidateId, "candidateId"), status,
    scope: enumValue(v.scope, MEMORY_SCOPES, "scope"), version: integer(v.version, "version"),
    createdAt: text(v.createdAt, "createdAt"), updatedAt: text(v.updatedAt, "updatedAt"), request: parseCandidateRequest(v.request), quarantineReasons, governance,
  };
}
export function parseMemoryCandidates(value: unknown): MemoryCandidate[] {
  if (!Array.isArray(value)) throw new TypeError("Candidate 列表响应格式无效");
  return value.map(parseMemoryCandidate);
}
export function parseMemoryCandidateEvent(value: unknown): MemoryCandidateEvent {
  const v = record(value, "CandidateEvent");
  const sequence = integer(v.sequence, "event.sequence");
  const fromStatus = v.fromStatus == null ? undefined : enumValue(v.fromStatus, MEMORY_CANDIDATE_STATUSES, "event.fromStatus");
  const toStatus = enumValue(v.toStatus, MEMORY_CANDIDATE_STATUSES, "event.toStatus");
  const eventType = enumValue(v.eventType, ["submitted", "quarantined", "rejected", "approved", "promoted"] as const, "event.eventType");
  if (sequence === 1 && fromStatus) throw new TypeError("首个 CandidateEvent 不得有 fromStatus");
  if (eventType !== (toStatus === "pending" ? "submitted" : toStatus)) throw new TypeError("CandidateEvent 类型与目标状态不一致");
  return {
    tenant: parseTenant(v.tenant, "event.tenant"), eventId: text(v.eventId, "event.eventId"), candidateId: text(v.candidateId, "event.candidateId"), sequence,
    eventType, fromStatus, toStatus, reasonCodes: strings(v.reasonCodes, "event.reasonCodes"),
    evidenceRef: v.evidenceRef == null ? undefined : parseResourceRef(v.evidenceRef, "event.evidenceRef"), eventHash: sha(v.eventHash, "event.eventHash"),
    actor: text(v.actor, "event.actor"), occurredAt: text(v.occurredAt, "event.occurredAt"),
  };
}
export function parseMemoryCandidateEvents(value: unknown): MemoryCandidateEvent[] {
  if (!Array.isArray(value)) throw new TypeError("CandidateEvent 列表响应格式无效");
  const result = value.map(parseMemoryCandidateEvent);
  result.forEach((event, index) => { if (event.sequence !== index + 1) throw new TypeError("CandidateEvent sequence 不连续"); });
  return result;
}
export function parseMemoryAuthorityItem(value: unknown): MemoryAuthorityItem {
  const v = record(value, "Memory"); const item = record(v.item, "item"); const revision = record(v.revision, "revision");
  const itemTenant = parseTenant(item.tenant, "item.tenant"); const revisionTenant = parseTenant(revision.tenant, "revision.tenant");
  if (!sameTenant(itemTenant, revisionTenant)) throw new TypeError("Memory tenant 不一致");
  const memoryItemId = text(item.memoryItemId, "memoryItemId"); const revisionItemId = text(revision.memoryItemId, "revision.memoryItemId");
  const currentRevision = integer(item.currentRevision, "currentRevision"); const exactRevision = integer(revision.revision, "revision");
  if (currentRevision !== exactRevision || memoryItemId !== revisionItemId) throw new TypeError("Memory current revision 不一致");
  const payload = parseArtifactRef(revision.payload, "revision.payload"); const contentHash = sha(revision.contentHash, "contentHash");
  if (payload.contentHash !== contentHash) throw new TypeError("Memory payload/contentHash 不一致");
  return {
    item: {
      tenant: itemTenant, memoryItemId, memoryLayer: enumValue(item.memoryLayer, MEMORY_LAYERS, "memoryLayer"), status: enumValue(item.status, MEMORY_ITEM_STATUSES, "memory status"),
      scope: enumValue(item.scope, MEMORY_SCOPES, "memory scope"), currentRevision, version: integer(item.version, "item.version"), subject: parseResourceRef(item.subject, "item.subject"),
      createdAt: text(item.createdAt, "item.createdAt"), updatedAt: text(item.updatedAt, "item.updatedAt"),
    },
    revision: {
      tenant: revisionTenant, memoryItemId, revision: exactRevision, candidateId: text(revision.candidateId, "candidateId"), contentHash,
      sourceId: text(revision.sourceId, "sourceId"), sourceRevision: integer(revision.sourceRevision, "sourceRevision"), payload,
      confidence: numberInRange(revision.confidence, "revision.confidence"), applicability: strings(revision.applicability, "applicability", true), markings: strings(revision.markings, "markings", true),
      effectiveAt: text(revision.effectiveAt, "effectiveAt"), expiresAt: optionalText(revision.expiresAt, "expiresAt"),
      createdBy: text(revision.createdBy, "createdBy"), createdAt: text(revision.createdAt, "revision.createdAt"),
    },
  };
}
export function parseMemoryAuthorityItems(value: unknown): MemoryAuthorityItem[] {
  if (!Array.isArray(value)) throw new TypeError("Memory 列表响应格式无效");
  return value.map(parseMemoryAuthorityItem);
}
export function parseKnowledgeQueryResult(value: unknown): KnowledgeQueryResult {
  const v = record(value, "KnowledgeQuery"); const status = enumValue(v.status, ["complete", "degraded", "blocked"] as const, "query status");
  if (!Array.isArray(v.citations) || !Array.isArray(v.chunks)) throw new TypeError("citation/chunk 无效");
  const reasons = strings(v.blockedReasons, "blockedReasons");
  const tokens = typeof v.assembledTokens === "number" && Number.isSafeInteger(v.assembledTokens) && v.assembledTokens >= 0 ? v.assembledTokens : (() => { throw new TypeError("assembledTokens 无效"); })();
  const citations = v.citations.map((raw, index) => parseCitation(raw, `citation[${index}]`));
  const chunks = v.chunks.map((raw, index) => { const chunk = record(raw, `chunk[${index}]`); return { content: text(chunk.content, `chunk[${index}].content`), tokenCount: integer(chunk.tokenCount, `chunk[${index}].tokenCount`), citation: parseCitation(chunk.citation, `chunk[${index}].citation`) }; });
  if (citations.length !== chunks.length || tokens !== chunks.reduce((sum, chunk) => sum + chunk.tokenCount, 0)) throw new TypeError("citation/chunk/token 不一致");
  citations.forEach((citation, index) => { if (JSON.stringify(citation) !== JSON.stringify(chunks[index].citation)) throw new TypeError("citation/chunk 引用不一致"); });
  if (status === "blocked" && (chunks.length || !reasons.length)) throw new TypeError("blocked 结果无效");
  return { status, citations, chunks, blockedReasons: reasons, assembledTokens: tokens };
}

export function parseKnowledgeReadiness(value: unknown): KnowledgeReadiness {
  const v = record(value, "KnowledgeReadiness");
  const parseAvailability = (raw: unknown, label: string) => {
    const item = record(raw, label);
    const status = enumValue(item.status, ["available", "authority_unavailable"] as const, `${label}.status`);
    const count = item.count == null ? undefined : nonNegativeInteger(item.count, `${label}.count`);
    const blocker = optionalText(item.blocker, `${label}.blocker`);
    if (status === "authority_unavailable" && (count !== undefined || !blocker)) throw new TypeError(`${label} authority_unavailable 结构无效`);
    if (status === "available" && count === undefined) throw new TypeError(`${label} available 缺 count`);
    return { status, count, blocker };
  };
  if (!Array.isArray(v.sources)) throw new TypeError("sources 无效");
  const search = record(v.search, "search");
  if (!Array.isArray(search.capabilities)) throw new TypeError("search.capabilities 无效");
  const capabilities = search.capabilities.map((raw, index) => {
    const item = record(raw, `capability[${index}]`);
    const status = enumValue(item.status, ["unbuilt", "ready", "degraded", "blocked"] as const, `capability[${index}].status`);
    const provider = optionalText(item.provider, `capability[${index}].provider`);
    const providerRevision = optionalText(item.providerRevision, `capability[${index}].providerRevision`);
    const reasonCode = optionalText(item.reasonCode, `capability[${index}].reasonCode`);
    if (status === "ready" && (!provider || !providerRevision || reasonCode)) throw new TypeError("ready capability 结构无效");
    if (status !== "ready" && !reasonCode) throw new TypeError("non-ready capability 缺 reasonCode");
    return { lane: enumValue(item.lane, ["fulltext", "vector", "rerank"] as const, `capability[${index}].lane`), status, provider, providerRevision, reasonCode, version: integer(item.version, `capability[${index}].version`), observedAt: text(item.observedAt, `capability[${index}].observedAt`) };
  });
  if (capabilities.length !== 3 || new Set(capabilities.map((item) => item.lane)).size !== 3) throw new TypeError("检索 capability 必须包含唯一三 lane");
  return {
    tenant: parseTenant(v.tenant, "readiness.tenant"),
    package: parseAvailability(v.package, "package"),
    sources: v.sources.map((raw, index) => { const item = record(raw, `source[${index}]`); return { provider: text(item.provider, `source[${index}].provider`), providerVersion: text(item.providerVersion, `source[${index}].providerVersion`), licenseId: text(item.licenseId, `source[${index}].licenseId`), usagePolicy: text(item.usagePolicy, `source[${index}].usagePolicy`), revisionCount: integer(item.revisionCount, `source[${index}].revisionCount`), staleCount: nonNegativeInteger(item.staleCount, `source[${index}].staleCount`) }; }),
    sourceBlockers: strings(v.sourceBlockers, "sourceBlockers"),
    search: { referenceCount: nonNegativeInteger(search.referenceCount, "search.referenceCount"), providerConfigured: booleanValue(search.providerConfigured, "search.providerConfigured"), capabilities, blockers: strings(search.blockers, "search.blockers") },
    eval: parseAvailability(v.eval, "eval"),
    observedAt: text(v.observedAt, "observedAt"),
  };
}

export function parseKnowledgePipelinePolicy(value: unknown): KnowledgePipelinePolicy {
  const v = record(value, "PipelinePolicy");
  return {
    pipelineKind: enumValue(v.pipelineKind, PIPELINE_KINDS, "pipelineKind"),
    allowedTriggers: parseEnumList(v.allowedTriggers, PIPELINE_TRIGGERS, "allowedTriggers"),
    defaultStatus: enumValue(v.defaultStatus, PIPELINE_SCHEDULE_STATUSES, "defaultStatus"),
    requiredDependencies: strings(v.requiredDependencies, "requiredDependencies", true),
    allowedReceiptTypes: strings(v.allowedReceiptTypes, "allowedReceiptTypes", true),
    allowedSourceKinds: strings(v.allowedSourceKinds, "allowedSourceKinds", true),
  };
}
export function parseKnowledgePipelinePolicies(value: unknown): KnowledgePipelinePolicy[] {
  if (!Array.isArray(value)) throw new TypeError("PipelinePolicy 列表响应格式无效");
  const result = value.map(parseKnowledgePipelinePolicy);
  if (new Set(result.map(item => item.pipelineKind)).size !== result.length) throw new TypeError("PipelinePolicy kind 重复");
  return result;
}
export function parseKnowledgePipelineOperationalReadiness(value: unknown): KnowledgePipelineOperationalReadinessEnvelope {
  const v = record(value, "PipelineOperationalReadiness");
  const tenant = parseTenant(v.tenant, "pipelineReadiness.tenant");
  const observedAt = text(v.observedAt, "pipelineReadiness.observedAt");
  if (!Array.isArray(v.pipelines)) throw new TypeError("pipelineReadiness.pipelines 无效");
  const pipelines = v.pipelines.map((raw, index) => {
    const item = record(raw, `pipelineReadiness[${index}]`);
    const itemTenant = parseTenant(item.tenant, `pipelineReadiness[${index}].tenant`);
    if (itemTenant.orgId !== tenant.orgId || itemTenant.projectId !== tenant.projectId) throw new TypeError("pipelineReadiness tenant 漂移");
    const operationalStatus = enumValue(item.operationalStatus, PIPELINE_OPERATIONAL_STATUSES, `pipelineReadiness[${index}].operationalStatus`);
    const blockerCodes = strings(item.blockerCodes, `pipelineReadiness[${index}].blockerCodes`);
    const dependencyAllowed = booleanValue(item.dependencyAllowed, `pipelineReadiness[${index}].dependencyAllowed`);
    if (operationalStatus === "ready" && (blockerCodes.length || !dependencyAllowed)) throw new TypeError("ready pipeline 不能携带 blocker");
    if (operationalStatus !== "ready" && !blockerCodes.length) throw new TypeError("non-ready pipeline 必须携带 blocker");
    const parseCounts = (counts: unknown, label: string) => {
      if (!Array.isArray(counts)) throw new TypeError(`${label} 无效`);
      const parsed = counts.map((entry, countIndex) => { const count = record(entry, `${label}[${countIndex}]`); return { status: text(count.status, `${label}.status`), count: nonNegativeInteger(count.count, `${label}.count`) }; });
      if (new Set(parsed.map(entry => entry.status)).size !== parsed.length) throw new TypeError(`${label} 状态重复`);
      return parsed;
    };
    const adapterRequired = booleanValue(item.adapterRequired, `pipelineReadiness[${index}].adapterRequired`);
    const adapterRegistered = booleanValue(item.adapterRegistered, `pipelineReadiness[${index}].adapterRegistered`);
    if (!adapterRequired && !adapterRegistered) throw new TypeError("无需 Adapter 的管道必须视为 Adapter ready");
    return {
      tenant: itemTenant,
      pipelineKind: enumValue(item.pipelineKind, PIPELINE_KINDS, `pipelineReadiness[${index}].pipelineKind`),
      defaultStatus: enumValue(item.defaultStatus, PIPELINE_SCHEDULE_STATUSES, `pipelineReadiness[${index}].defaultStatus`),
      dependencyAllowed,
      dependencyReasonCodes: strings(item.dependencyReasonCodes, `pipelineReadiness[${index}].dependencyReasonCodes`),
      adapterRequired,
      adapterRegistered,
      scheduleCounts: parseCounts(item.scheduleCounts, `pipelineReadiness[${index}].scheduleCounts`),
      runCounts: parseCounts(item.runCounts, `pipelineReadiness[${index}].runCounts`),
      lastRun: item.lastRun == null ? undefined : parseKnowledgePipelineRun(item.lastRun),
      lastReceipt: item.lastReceipt == null ? undefined : parseKnowledgePipelineReceipt(item.lastReceipt),
      lastCheckpoint: item.lastCheckpoint == null ? undefined : parseKnowledgePipelineCheckpoint(item.lastCheckpoint),
      alertCount: nonNegativeInteger(item.alertCount, `pipelineReadiness[${index}].alertCount`),
      operationalStatus,
      blockerCodes,
      observedAt: text(item.observedAt, `pipelineReadiness[${index}].observedAt`),
    };
  });
  if (pipelines.length !== PIPELINE_KINDS.length || new Set(pipelines.map(item => item.pipelineKind)).size !== PIPELINE_KINDS.length || PIPELINE_KINDS.some(kind => !pipelines.some(item => item.pipelineKind === kind))) throw new TypeError("pipelineReadiness 必须包含唯一七管道");
  return { tenant, pipelines, observedAt };
}
function parseEnumList<T extends readonly string[]>(value: unknown, allowed: T, label: string): T[number][] {
  if (!Array.isArray(value) || !value.length) throw new TypeError(`${label} 无效`);
  const parsed = value.map(item => enumValue(item, allowed, label));
  if (new Set(parsed).size !== parsed.length) throw new TypeError(`${label} 重复`);
  return parsed;
}
export function parseKnowledgePipelineSchedule(value: unknown): KnowledgePipelineSchedule {
  const v = record(value, "PipelineSchedule");
  return {
    tenant: parseTenant(v.tenant, "schedule.tenant"), scheduleId: text(v.scheduleId, "scheduleId"),
    pipelineKind: enumValue(v.pipelineKind, PIPELINE_KINDS, "pipelineKind"), trigger: enumValue(v.trigger, PIPELINE_TRIGGERS, "trigger"),
    config: parseArtifactRef(v.config, "config"), status: enumValue(v.status, PIPELINE_SCHEDULE_STATUSES, "schedule status"),
    scheduleSpec: optionalText(v.scheduleSpec, "scheduleSpec"), checkpointVersion: nonNegativeInteger(v.checkpointVersion, "checkpointVersion"),
    version: integer(v.version, "schedule.version"), nextRunAt: optionalText(v.nextRunAt, "nextRunAt"),
    createdAt: text(v.createdAt, "schedule.createdAt"), updatedAt: text(v.updatedAt, "schedule.updatedAt"),
  };
}
export function parseKnowledgePipelineSchedules(value: unknown): KnowledgePipelineSchedule[] {
  if (!Array.isArray(value)) throw new TypeError("PipelineSchedule 列表响应格式无效");
  return value.map(parseKnowledgePipelineSchedule);
}
export function parseKnowledgePipelineRun(value: unknown): KnowledgePipelineRun {
  const v = record(value, "PipelineRun");
  const tenant = parseTenant(v.tenant, "run.tenant");
  const leaseOwner = optionalText(v.leaseOwner, "leaseOwner"); const leaseExpiresAt = optionalText(v.leaseExpiresAt, "leaseExpiresAt");
  if ((leaseOwner ? 1 : 0) !== (leaseExpiresAt ? 1 : 0)) throw new TypeError("PipelineRun lease 不完整");
  return {
    tenant, pipelineRunId: text(v.pipelineRunId, "pipelineRunId"), scheduleId: text(v.scheduleId, "run.scheduleId"), taskId: text(v.taskId, "run.taskId"), runId: text(v.runId, "run.runId"),
    trigger: enumValue(v.trigger, PIPELINE_TRIGGERS, "run.trigger"), status: enumValue(v.status, PIPELINE_RUN_STATUSES, "run.status"), attempt: integer(v.attempt, "attempt"),
    retryOfRunId: optionalText(v.retryOfRunId, "retryOfRunId"), expectedCheckpointVersion: nonNegativeInteger(v.expectedCheckpointVersion, "expectedCheckpointVersion"),
    idempotencyKey: text(v.idempotencyKey, "idempotencyKey"), requestHash: sha(v.requestHash, "requestHash"), version: integer(v.version, "run.version"),
    scheduledFor: text(v.scheduledFor, "scheduledFor"), leaseOwner, leaseExpiresAt, startedAt: optionalText(v.startedAt, "startedAt"), finishedAt: optionalText(v.finishedAt, "finishedAt"),
    createdAt: text(v.createdAt, "run.createdAt"), updatedAt: text(v.updatedAt, "run.updatedAt"),
  };
}
export function parseKnowledgePipelineRuns(value: unknown): KnowledgePipelineRun[] {
  if (!Array.isArray(value)) throw new TypeError("PipelineRun 列表响应格式无效");
  return value.map(parseKnowledgePipelineRun);
}
export function parseKnowledgePipelineReceipt(value: unknown): KnowledgePipelineReceipt {
  const v = record(value, "PipelineReceipt");
  const refs = Array.isArray(v.candidateRefs) ? v.candidateRefs.map((ref, index) => parseResourceRef(ref, `candidateRefs[${index}]`)) : (() => { throw new TypeError("candidateRefs 无效"); })();
  const producedCount = nonNegativeInteger(v.producedCount, "producedCount");
  if (producedCount !== refs.length) throw new TypeError("producedCount 与 Candidate refs 不一致");
  const before = nonNegativeInteger(v.checkpointBeforeVersion, "checkpointBeforeVersion"); const after = nonNegativeInteger(v.checkpointAfterVersion, "checkpointAfterVersion");
  if (after < before) throw new TypeError("checkpoint 版本回退");
  return {
    tenant: parseTenant(v.tenant, "receipt.tenant"), receiptId: text(v.receiptId, "receiptId"), pipelineRunId: text(v.pipelineRunId, "receipt.pipelineRunId"),
    status: enumValue(v.status, PIPELINE_RUN_STATUSES, "receipt.status"), inputHash: sha(v.inputHash, "inputHash"), outputHash: sha(v.outputHash, "outputHash"), candidateRefs: refs,
    checkpointBeforeVersion: before, checkpointAfterVersion: after, producedCount, failedCount: nonNegativeInteger(v.failedCount, "failedCount"), errorCodes: strings(v.errorCodes, "errorCodes"),
    receiptHash: sha(v.receiptHash, "receiptHash"), createdAt: text(v.createdAt, "receipt.createdAt"),
  };
}
export function parseKnowledgePipelineReceiptView(value: unknown): KnowledgePipelineReceipt | null {
  const v = record(value, "PipelineReceiptView");
  return v.receipt == null ? null : parseKnowledgePipelineReceipt(v.receipt);
}
export function parseKnowledgePipelineCheckpoint(value: unknown): KnowledgePipelineCheckpoint {
  const v = record(value, "PipelineCheckpoint"); const checkpoint = parseArtifactRef(v.checkpoint, "checkpoint"); const checkpointHash = sha(v.checkpointHash, "checkpointHash");
  if (checkpoint.contentHash !== checkpointHash) throw new TypeError("checkpoint hash 不一致");
  return { tenant: parseTenant(v.tenant, "checkpoint.tenant"), scheduleId: text(v.scheduleId, "checkpoint.scheduleId"), revision: integer(v.revision, "checkpoint.revision"), pipelineRunId: text(v.pipelineRunId, "checkpoint.pipelineRunId"), receiptId: text(v.receiptId, "checkpoint.receiptId"), checkpoint, checkpointHash, createdAt: text(v.createdAt, "checkpoint.createdAt") };
}
export function parseKnowledgePipelineCheckpointView(value: unknown): KnowledgePipelineCheckpoint | null {
  const v = record(value, "PipelineCheckpointView");
  return v.checkpoint == null ? null : parseKnowledgePipelineCheckpoint(v.checkpoint);
}
export function parseKnowledgePipelineAlert(value: unknown): KnowledgePipelineAlert {
  const v = record(value, "PipelineAlert");
  return { tenant: parseTenant(v.tenant, "alert.tenant"), alertId: text(v.alertId, "alertId"), pipelineRunId: text(v.pipelineRunId, "alert.pipelineRunId"), code: text(v.code, "alert.code"), severity: enumValue(v.severity, PIPELINE_ALERT_SEVERITIES, "alert.severity"), evidenceRef: parseResourceRef(v.evidenceRef, "alert.evidenceRef"), alertHash: sha(v.alertHash, "alertHash"), createdAt: text(v.createdAt, "alert.createdAt") };
}
export function parseKnowledgePipelineAlerts(value: unknown): KnowledgePipelineAlert[] { if (!Array.isArray(value)) throw new TypeError("PipelineAlert 列表响应格式无效"); return value.map(parseKnowledgePipelineAlert); }

function parseVersionedAssetRef(value: unknown, label: string, expectedType?: string): VersionedAssetRef {
  const v = record(value, label);
  const result = { assetType: text(v.assetType, `${label}.assetType`), assetId: text(v.assetId, `${label}.assetId`), revision: integer(v.revision, `${label}.revision`), contentHash: sha(v.contentHash, `${label}.contentHash`) };
  if (expectedType && result.assetType !== expectedType) throw new TypeError(`${label} 必须引用 ${expectedType}`);
  return result;
}
function parseMemoryRevisionRef(value: unknown, label: string): MemoryRevisionExactRef {
  const v = record(value, label);
  return { memoryItemId: text(v.memoryItemId, `${label}.memoryItemId`), revision: integer(v.revision, `${label}.revision`), contentHash: sha(v.contentHash, `${label}.contentHash`) };
}
function parseProjectionRef(value: unknown, label: string): MemoryProjectionExactRef {
  const v = record(value, label);
  return { projectionId: text(v.projectionId, `${label}.projectionId`), version: integer(v.version, `${label}.version`), contentHash: sha(v.contentHash, `${label}.contentHash`) };
}
function uniqueAssetRefs(value: unknown, label: string, expectedType?: string): VersionedAssetRef[] {
  if (!Array.isArray(value)) throw new TypeError(`${label} 无效`);
  const refs = value.map((item, index) => parseVersionedAssetRef(item, `${label}[${index}]`, expectedType));
  if (new Set(refs.map((ref) => `${ref.assetType}:${ref.assetId}:${ref.revision}:${ref.contentHash}`)).size !== refs.length) throw new TypeError(`${label} 重复`);
  return refs;
}
function fraction(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) throw new TypeError(`${label} 无效`);
  return value;
}
function signedFraction(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < -1 || value > 1) throw new TypeError(`${label} 无效`);
  return value;
}

export function parseMemoryAgentInstances(value: unknown): MemoryAgentInstance[] {
  const wrapper = record(value, "AgentInstanceList"); const tenant = parseTenant(wrapper.tenant, "AgentInstanceList.tenant");
  if (!Array.isArray(wrapper.items)) throw new TypeError("AgentInstanceList.items 无效");
  const items = wrapper.items.map((raw, index) => {
    const v = record(raw, `AgentInstance[${index}]`); const instanceTenant = parseTenant(v.tenant, `AgentInstance[${index}].tenant`);
    if (!sameTenant(tenant, instanceTenant)) throw new TypeError("AgentInstance tenant 不一致");
    const instanceRef = parseVersionedAssetRef(v.instanceRef, `AgentInstance[${index}].instanceRef`, "AgentInstance");
    const instanceId = text(v.instanceId, `AgentInstance[${index}].instanceId`); const version = integer(v.version, `AgentInstance[${index}].version`);
    if (instanceRef.assetId !== instanceId || instanceRef.revision !== version) throw new TypeError("AgentInstance exact ref/version 不一致");
    const overlay = record(v.overlay, `AgentInstance[${index}].overlay`);
    return { tenant: instanceTenant, instanceId, instanceRef, template: parseVersionedAssetRef(v.template, `AgentInstance[${index}].template`, "AgentTemplate"), status: enumValue(v.status, ["provisioning", "active", "suspended", "deleted"] as const, `AgentInstance[${index}].status`), overlay: { displayName: optionalText(overlay.displayName, `AgentInstance[${index}].overlay.displayName`), allowedCapabilityIds: strings(overlay.allowedCapabilityIds, `AgentInstance[${index}].overlay.allowedCapabilityIds`) }, version, createdBy: text(v.createdBy, `AgentInstance[${index}].createdBy`), createdAt: text(v.createdAt, `AgentInstance[${index}].createdAt`), updatedAt: text(v.updatedAt, `AgentInstance[${index}].updatedAt`) };
  });
  if (nonNegativeInteger(wrapper.count, "AgentInstanceList.count") !== items.length) throw new TypeError("AgentInstanceList count 不一致");
  return items;
}

export function parseMemoryAgentProjection(value: unknown): MemoryAgentProjection {
  const v = record(value, "MemoryProjection"); const kind = enumValue(v.kind, ["personal", "shared"] as const, "projection.kind");
  const owner = parseVersionedAssetRef(v.ownerInstanceRef, "projection.ownerInstanceRef", "AgentInstance");
  const recipients = uniqueAssetRefs(v.recipientInstanceRefs, "projection.recipientInstanceRefs", "AgentInstance");
  if ((kind === "personal" && recipients.length) || (kind === "shared" && !recipients.length)) throw new TypeError("projection personal/shared recipient 不变量失败");
  if (recipients.some((item) => item.assetId === owner.assetId)) throw new TypeError("projection owner 不得成为 recipient");
  const effectiveAt = text(v.effectiveAt, "projection.effectiveAt"); const expiresAt = text(v.expiresAt, "projection.expiresAt");
  if (!(Date.parse(expiresAt) > Date.parse(effectiveAt))) throw new TypeError("projection 有效期无效");
  return { tenant: parseTenant(v.tenant, "projection.tenant"), projectionRef: parseProjectionRef(v.projectionRef, "projection.projectionRef"), kind, ownerInstanceRef: owner, memoryRef: parseMemoryRevisionRef(v.memoryRef, "projection.memoryRef"), recipientInstanceRefs: recipients, allowedPurposes: strings(v.allowedPurposes, "projection.allowedPurposes", true), allowedMarkings: strings(v.allowedMarkings, "projection.allowedMarkings", true), disclosure: enumValue(v.disclosure, ["citation_only", "governed_summary"] as const, "projection.disclosure"), status: enumValue(v.status, MEMORY_PROJECTION_STATUSES, "projection.status"), effectiveAt, expiresAt, createdBy: text(v.createdBy, "projection.createdBy"), createdAt: text(v.createdAt, "projection.createdAt"), updatedAt: text(v.updatedAt, "projection.updatedAt") };
}
export function parseMemoryAgentProjections(value: unknown): MemoryAgentProjection[] { if (!Array.isArray(value)) throw new TypeError("MemoryProjection 列表响应格式无效"); return value.map(parseMemoryAgentProjection); }

export function parseMemoryExposures(value: unknown): MemoryExposure[] {
  if (!Array.isArray(value)) throw new TypeError("MemoryExposure 列表响应格式无效");
  return value.map((raw, index) => {
    const v = record(raw, `MemoryExposure[${index}]`); if ("payload" in v || "chunks" in v || "content" in v) throw new TypeError("MemoryExposure 不得包含正文");
    const agentRunRef = parseResourceRef(v.agentRunRef, `MemoryExposure[${index}].agentRunRef`); const taskRunRef = parseResourceRef(v.taskRunRef, `MemoryExposure[${index}].taskRunRef`);
    if (agentRunRef.resourceType !== "AgentRun" || !agentRunRef.revision || taskRunRef.resourceType !== "TaskRun" || !taskRunRef.revision) throw new TypeError("MemoryExposure Run ref 非 exact");
    const timeCutoff = text(v.timeCutoff, `MemoryExposure[${index}].timeCutoff`); const acceptedAt = text(v.acceptedAt, `MemoryExposure[${index}].acceptedAt`);
    if (!(Date.parse(acceptedAt) >= Date.parse(timeCutoff))) throw new TypeError("MemoryExposure acceptedAt 早于 timeCutoff");
    return { tenant: parseTenant(v.tenant, `MemoryExposure[${index}].tenant`), exposureId: text(v.exposureId, `MemoryExposure[${index}].exposureId`), agentRunRef, taskRunRef, agentInstanceRef: parseVersionedAssetRef(v.agentInstanceRef, `MemoryExposure[${index}].agentInstanceRef`, "AgentInstance"), skillRef: parseVersionedAssetRef(v.skillRef, `MemoryExposure[${index}].skillRef`, "SkillTemplate"), logicRef: parseVersionedAssetRef(v.logicRef, `MemoryExposure[${index}].logicRef`, "LogicRevision"), projectionRef: parseProjectionRef(v.projectionRef, `MemoryExposure[${index}].projectionRef`), memoryRef: parseMemoryRevisionRef(v.memoryRef, `MemoryExposure[${index}].memoryRef`), evalContractRef: parseVersionedAssetRef(v.evalContractRef, `MemoryExposure[${index}].evalContractRef`, "EvalContract"), timeCutoff, acceptedAt, exposureHash: sha(v.exposureHash, `MemoryExposure[${index}].exposureHash`) };
  });
}

export function parseMemoryImprovementObservations(value: unknown): MemoryImprovementObservation[] {
  if (!Array.isArray(value)) throw new TypeError("ImprovementObservation 列表响应格式无效");
  return value.map((raw, index) => {
    const v = record(raw, `Observation[${index}]`); const quality = enumValue(v.quality, ["measured", "estimated", "unknown"] as const, `Observation[${index}].quality`); const conclusion = enumValue(v.conclusion, ["improved", "unchanged", "regressed", "insufficient_evidence"] as const, `Observation[${index}].conclusion`);
    if (!Array.isArray(v.metrics)) throw new TypeError(`Observation[${index}].metrics 无效`);
    const metrics = v.metrics.map((rawMetric, metricIndex) => { const metric = record(rawMetric, `Observation[${index}].metrics[${metricIndex}]`); const lower = metric.confidenceIntervalLower == null ? undefined : signedFraction(metric.confidenceIntervalLower, "confidenceIntervalLower"); const upper = metric.confidenceIntervalUpper == null ? undefined : signedFraction(metric.confidenceIntervalUpper, "confidenceIntervalUpper"); if ((lower === undefined) !== (upper === undefined) || (lower !== undefined && upper !== undefined && lower > upper)) throw new TypeError("Observation confidence interval 无效"); return { metricName: enumValue(metric.metricName, ["human_edit_rate", "task_success_rate", "citation_acceptance_rate"] as const, "metricName"), baselineValue: fraction(metric.baselineValue, "baselineValue"), treatmentValue: fraction(metric.treatmentValue, "treatmentValue"), baselineSampleSize: integer(metric.baselineSampleSize, "baselineSampleSize"), treatmentSampleSize: integer(metric.treatmentSampleSize, "treatmentSampleSize"), confidenceIntervalLower: lower, confidenceIntervalUpper: upper }; });
    if (new Set(metrics.map((item) => item.metricName)).size !== metrics.length) throw new TypeError("Observation metricName 重复");
    const sourceRefs = uniqueAssetRefs(v.sourceRefs, `Observation[${index}].sourceRefs`); const exposureRefs = uniqueAssetRefs(v.exposureRefs, `Observation[${index}].exposureRefs`, "MemoryExposure");
    if (sourceRefs.some((ref) => !["EvalReport", "EvidenceSnapshot", "MetricSnapshot"].includes(ref.assetType))) throw new TypeError("Observation sourceRef 不是受治理证据");
    const optionalRef = (rawRef: unknown, label: string, expected: string) => rawRef == null ? undefined : parseVersionedAssetRef(rawRef, label, expected);
    const comparable = { evalReportRef: optionalRef(v.evalReportRef, "evalReportRef", "EvalReport"), baselineCohortRef: optionalRef(v.baselineCohortRef, "baselineCohortRef", "CohortSnapshot"), treatmentCohortRef: optionalRef(v.treatmentCohortRef, "treatmentCohortRef", "CohortSnapshot") };
    if (quality === "unknown" && (metrics.length || sourceRefs.length || comparable.evalReportRef || comparable.baselineCohortRef || comparable.treatmentCohortRef || conclusion !== "insufficient_evidence")) throw new TypeError("unknown improvement 不得伪造指标或提升结论");
    if (quality !== "unknown" && (!metrics.length || !sourceRefs.length || !exposureRefs.length || !comparable.evalReportRef || !comparable.baselineCohortRef || !comparable.treatmentCohortRef)) throw new TypeError("measured/estimated improvement 缺 exact 证据");
    const cutoffAt = text(v.cutoffAt, `Observation[${index}].cutoffAt`); const observedAt = text(v.observedAt, `Observation[${index}].observedAt`);
    if (!(Date.parse(observedAt) >= Date.parse(cutoffAt))) throw new TypeError("Observation observedAt 早于 cutoffAt");
    return { tenant: parseTenant(v.tenant, `Observation[${index}].tenant`), observationId: text(v.observationId, `Observation[${index}].observationId`), agentInstanceRef: parseVersionedAssetRef(v.agentInstanceRef, `Observation[${index}].agentInstanceRef`, "AgentInstance"), metricDefinitionRef: parseVersionedAssetRef(v.metricDefinitionRef, `Observation[${index}].metricDefinitionRef`, "MetricDefinition"), evalContractRef: parseVersionedAssetRef(v.evalContractRef, `Observation[${index}].evalContractRef`, "EvalContract"), ...comparable, exposureRefs, metrics, quality, sourceRefs, cutoffAt, observedAt, conclusion, limitations: strings(v.limitations, `Observation[${index}].limitations`), observationHash: sha(v.observationHash, `Observation[${index}].observationHash`) };
  });
}

export function parseMemoryRevocationImpact(value: unknown): MemoryRevocationImpact {
  const v = record(value, "MemoryRevocationImpact"); if ("payload" in v || "chunks" in v || "content" in v) throw new TypeError("MemoryRevocationImpact 不得包含正文");
  if (!Array.isArray(v.affectedAgentRunRefs)) throw new TypeError("affectedAgentRunRefs 无效");
  const refs = v.affectedAgentRunRefs.map((raw, index) => { const ref = parseResourceRef(raw, `affectedAgentRunRefs[${index}]`); if (ref.resourceType !== "AgentRun" || !ref.revision) throw new TypeError("affectedAgentRunRef 非 exact"); return ref; });
  const affectedAgentRunCount = nonNegativeInteger(v.affectedAgentRunCount, "affectedAgentRunCount"); if (refs.length !== affectedAgentRunCount) throw new TypeError("affectedAgentRunCount 不一致");
  return { tenant: parseTenant(v.tenant, "impact.tenant"), projectionRef: parseProjectionRef(v.projectionRef, "impact.projectionRef"), projectionStatus: text(v.projectionStatus, "impact.projectionStatus"), recipientCount: nonNegativeInteger(v.recipientCount, "recipientCount"), exposureCount: nonNegativeInteger(v.exposureCount, "exposureCount"), affectedAgentRunCount, affectedAgentRunRefs: refs, reEvaluationStatus: enumValue(v.reEvaluationStatus, ["not_required", "required", "blocked"] as const, "reEvaluationStatus"), blockerCodes: strings(v.blockerCodes, "blockerCodes") };
}
