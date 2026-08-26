import {
  ADAPTIVE_PROFILE_SCHEMA_VERSION,
  BUSINESS_INVESTIGATION_SHARED_SCHEMA_VERSION,
  DATA_FULFILLMENT_SCHEMA_VERSION,
  DATA_REQUIREMENT_SCHEMA_VERSION,
  PLATFORM_OBSERVATION_SCHEMA_VERSION,
  SEMANTIC_HYDRATION_SCHEMA_VERSION,
  SOURCE_MAPPING_SCHEMA_VERSION,
  type AdaptiveProfileContract,
  type BusinessInvestigationSharedEnvelope,
  type DataFulfillmentReceiptContract,
  type DataFulfillmentStatus,
  type DataRequirementContract,
  type DataRequirementStatus,
  type InvestigationBlocker,
  type InvestigationBusinessEntity,
  type InvestigationChannel,
  type InvestigationCoverage,
  type InvestigationExactRef,
  type InvestigationFreshness,
  type InvestigationPlatform,
  type InvestigationReadiness,
  type InvestigationTenant,
  type ObservationLifecycle,
  type PlatformObservationContract,
  type SemanticHydrationReceiptContract,
  type SemanticHydrationStatus,
  type SourceMappingContract,
} from "./contracts";

const HASH = /^sha256:[0-9a-f]{64}$/;
const BLOCKER_CODE = /^[A-Z][A-Z0-9_]{1,119}$/;
const ARTIFACT_TYPES = new Set([
  "BusinessDossierRevision", "ProblemMapRevision", "OpportunityMapRevision", "SolutionPortfolioRevision",
  "InsightRevision", "DecisionSummaryRevision", "GrowthPlanRevision", "TaskGraphRevision", "EcommerceEffectReviewRevision",
]);

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new TypeError(`${label} 必须是对象`);
  return value as Record<string, unknown>;
}

function exactKeys(raw: Record<string, unknown>, allowed: readonly string[], label: string): void {
  const unexpected = Object.keys(raw).filter((key) => !allowed.includes(key));
  if (unexpected.length) throw new TypeError(`${label} 包含未知字段: ${unexpected.join(",")}`);
}

function text(value: unknown, label: string, max = 240): string {
  if (typeof value !== "string" || !value.trim() || value.length > max) throw new TypeError(`${label} 必须是非空有界字符串`);
  return value.trim();
}

function nonNegativeInteger(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) throw new TypeError(`${label} 必须是非负整数`);
  return value;
}

function timestamp(value: unknown, label: string): string {
  const parsed = text(value, label, 80);
  if (!/(?:Z|[+-][0-9]{2}:[0-9]{2})$/.test(parsed) || Number.isNaN(Date.parse(parsed))) throw new TypeError(`${label} 必须包含时区`);
  return parsed;
}

function enumValue<T extends string>(value: unknown, choices: readonly T[], label: string): T {
  if (typeof value !== "string" || !choices.includes(value as T)) throw new TypeError(`${label} 枚举无效`);
  return value as T;
}

function array(value: unknown, label: string, max = 200): unknown[] {
  if (!Array.isArray(value) || value.length > max) throw new TypeError(`${label} 必须是有界数组`);
  return value;
}

function unique(values: string[], label: string): void {
  if (new Set(values).size !== values.length) throw new TypeError(`${label} 必须唯一`);
}

function parseTenant(value: unknown): InvestigationTenant {
  const raw = record(value, "tenant"); exactKeys(raw, ["orgId", "projectId"], "tenant");
  return { orgId: text(raw.orgId, "tenant.orgId", 200), projectId: text(raw.projectId, "tenant.projectId", 200) };
}

function parseExactRef(value: unknown, label: string, expectedType?: string, requireReceipt = false): InvestigationExactRef {
  const raw = record(value, label); exactKeys(raw, ["resourceType", "resourceId", "revision", "contentHash", "receiptId"], label);
  const resourceType = text(raw.resourceType, `${label}.resourceType`, 120);
  if (expectedType && resourceType !== expectedType) throw new TypeError(`${label} 必须引用 ${expectedType}`);
  const resourceId = text(raw.resourceId, `${label}.resourceId`, 240);
  let revision: number | string;
  if (typeof raw.revision === "number" && Number.isInteger(raw.revision) && raw.revision >= 1) revision = raw.revision;
  else revision = text(raw.revision, `${label}.revision`, 160);
  const contentHash = text(raw.contentHash, `${label}.contentHash`, 71);
  if (!HASH.test(contentHash)) throw new TypeError(`${label}.contentHash 不是 SHA-256`);
  const receiptId = raw.receiptId === undefined ? undefined : text(raw.receiptId, `${label}.receiptId`, 240);
  if (requireReceipt && !receiptId) throw new TypeError(`${label} 缺 receiptId`);
  return { resourceType, resourceId, revision, contentHash, ...(receiptId ? { receiptId } : {}) };
}

function parseBlocker(value: unknown, label: string): InvestigationBlocker {
  const raw = record(value, label); exactKeys(raw, ["code", "severity", "dependency", "requiredAction"], label);
  const code = text(raw.code, `${label}.code`, 120);
  if (!BLOCKER_CODE.test(code)) throw new TypeError(`${label}.code 无效`);
  return { code, severity: enumValue(raw.severity, ["warning", "blocking"] as const, `${label}.severity`), dependency: text(raw.dependency, `${label}.dependency`, 160), requiredAction: text(raw.requiredAction, `${label}.requiredAction`, 500) };
}

function parseBlockers(value: unknown, label: string): InvestigationBlocker[] {
  return array(value, label, 50).map((item, index) => parseBlocker(item, `${label}[${index}]`));
}

function parseRefs(value: unknown, label: string, expectedType?: string): InvestigationExactRef[] {
  const refs = array(value, label).map((item, index) => parseExactRef(item, `${label}[${index}]`, expectedType));
  unique(refs.map((ref) => `${ref.resourceType}:${ref.resourceId}:${ref.revision}:${ref.contentHash}`), label);
  return refs;
}

function parseCoverage(value: unknown, label: string): InvestigationCoverage {
  const raw = record(value, label); exactKeys(raw, ["required", "fulfilled", "unknown"], label);
  const coverage = { required: nonNegativeInteger(raw.required, `${label}.required`), fulfilled: nonNegativeInteger(raw.fulfilled, `${label}.fulfilled`), unknown: nonNegativeInteger(raw.unknown, `${label}.unknown`) };
  if (coverage.fulfilled + coverage.unknown > coverage.required) throw new TypeError(`${label} 计数不守恒`);
  return coverage;
}

function parseFreshness(value: unknown): InvestigationFreshness {
  const raw = record(value, "readiness.freshness"); exactKeys(raw, ["status", "dataCutoff", "expiresAt"], "readiness.freshness");
  const status = enumValue(raw.status, ["fresh", "stale", "unknown"] as const, "readiness.freshness.status");
  const dataCutoff = raw.dataCutoff === null ? null : timestamp(raw.dataCutoff, "readiness.freshness.dataCutoff");
  const expiresAt = raw.expiresAt === null ? null : timestamp(raw.expiresAt, "readiness.freshness.expiresAt");
  if (status === "fresh" && (!dataCutoff || !expiresAt || Date.parse(expiresAt) <= Date.parse(dataCutoff))) throw new TypeError("fresh readiness 必须有有效截止和过期时间");
  return { status, dataCutoff, expiresAt };
}

function parseReadiness(value: unknown): InvestigationReadiness {
  const raw = record(value, "readiness"); exactKeys(raw, ["status", "sourceReadinessRef", "coverage", "freshness", "blockers"], "readiness");
  const status = enumValue(raw.status, ["ready", "blocked", "stale", "unknown"] as const, "readiness.status");
  const sourceReadinessRef = raw.sourceReadinessRef === null ? null : parseExactRef(raw.sourceReadinessRef, "readiness.sourceReadinessRef", "SourceReadinessEnvelope", true);
  const coverage = parseCoverage(raw.coverage, "readiness.coverage");
  const freshness = parseFreshness(raw.freshness);
  const blockers = parseBlockers(raw.blockers, "readiness.blockers");
  if (status === "ready" && (!sourceReadinessRef || coverage.fulfilled !== coverage.required || coverage.unknown !== 0 || freshness.status !== "fresh" || blockers.length)) throw new TypeError("伪 ready：缺 exact、新鲜、完整证据或仍有 blocker");
  if (status !== "ready" && !blockers.length) throw new TypeError("非 ready 必须携带 blocker");
  return { status, sourceReadinessRef, coverage, freshness, blockers };
}

function sameRef(left: InvestigationExactRef, right: InvestigationExactRef): boolean {
  return left.resourceType === right.resourceType && left.resourceId === right.resourceId && left.revision === right.revision && left.contentHash === right.contentHash && left.receiptId === right.receiptId;
}

function parseChannel(value: unknown): InvestigationChannel {
  const raw = record(value, "channel"); exactKeys(raw, ["channelId", "platform", "displayName", "channelRef"], "channel");
  const channelId = text(raw.channelId, "channel.channelId", 200);
  const channelRef = parseExactRef(raw.channelRef, "channel.channelRef", "ChannelRevision");
  if (channelRef.resourceId !== channelId) throw new TypeError("channelRef 与 channelId 漂移");
  return { channelId, platform: enumValue<InvestigationPlatform>(raw.platform, ["niushop", "wechat_store", "douyin_store"], "channel.platform"), displayName: text(raw.displayName, "channel.displayName"), channelRef };
}

function parseBusinessEntity(value: unknown): InvestigationBusinessEntity {
  const raw = record(value, "businessEntity"); exactKeys(raw, ["businessEntityId", "entityType", "displayName", "channelRef"], "businessEntity");
  return { businessEntityId: text(raw.businessEntityId, "businessEntity.businessEntityId", 200), entityType: text(raw.entityType, "businessEntity.entityType", 120), displayName: text(raw.displayName, "businessEntity.displayName"), channelRef: parseExactRef(raw.channelRef, "businessEntity.channelRef", "ChannelRevision") };
}

export function parseBusinessInvestigationSharedEnvelope(value: unknown): BusinessInvestigationSharedEnvelope {
  const raw = record(value, "businessInvestigation"); exactKeys(raw, ["schemaVersion", "tenant", "channel", "businessEntity", "caseRef", "runRef", "readiness", "artifactRefs"], "businessInvestigation");
  if (raw.schemaVersion !== BUSINESS_INVESTIGATION_SHARED_SCHEMA_VERSION) throw new TypeError("businessInvestigation.schemaVersion 无效");
  const channel = parseChannel(raw.channel); const businessEntity = parseBusinessEntity(raw.businessEntity);
  if (!sameRef(channel.channelRef, businessEntity.channelRef)) throw new TypeError("businessEntity channelRef 与 channel 漂移");
  const artifactRefs = parseRefs(raw.artifactRefs, "businessInvestigation.artifactRefs");
  if (artifactRefs.some((ref) => !ARTIFACT_TYPES.has(ref.resourceType))) throw new TypeError("artifactRefs 包含非 canonical Analyst/Case 制品");
  return { schemaVersion: BUSINESS_INVESTIGATION_SHARED_SCHEMA_VERSION, tenant: parseTenant(raw.tenant), channel, businessEntity, caseRef: parseExactRef(raw.caseRef, "businessInvestigation.caseRef", "BusinessInvestigationCaseRevision"), runRef: parseExactRef(raw.runRef, "businessInvestigation.runRef", "BusinessInvestigationRun"), readiness: parseReadiness(raw.readiness), artifactRefs };
}

export function parseDataRequirement(value: unknown): DataRequirementContract {
  const raw = record(value, "dataRequirement"); exactKeys(raw, ["schemaVersion", "tenant", "requirementId", "caseRef", "runRef", "purpose", "factTypes", "status", "requestedAt", "blockers"], "dataRequirement");
  if (raw.schemaVersion !== DATA_REQUIREMENT_SCHEMA_VERSION) throw new TypeError("dataRequirement.schemaVersion 无效");
  const factTypes = array(raw.factTypes, "dataRequirement.factTypes", 100).map((item, index) => text(item, `dataRequirement.factTypes[${index}]`, 160)); unique(factTypes, "dataRequirement.factTypes");
  const status = enumValue<DataRequirementStatus>(raw.status, ["requested", "accepted", "planned", "fulfilled", "rejected", "cancelled", "unknown"], "dataRequirement.status");
  const blockers = parseBlockers(raw.blockers, "dataRequirement.blockers");
  if ((status === "rejected" || status === "unknown") && !blockers.length) throw new TypeError("rejected/unknown requirement 必须有 blocker");
  return { schemaVersion: DATA_REQUIREMENT_SCHEMA_VERSION, tenant: parseTenant(raw.tenant), requirementId: text(raw.requirementId, "dataRequirement.requirementId", 200), caseRef: parseExactRef(raw.caseRef, "dataRequirement.caseRef", "BusinessInvestigationCaseRevision"), runRef: parseExactRef(raw.runRef, "dataRequirement.runRef", "BusinessInvestigationRun"), purpose: text(raw.purpose, "dataRequirement.purpose", 1000), factTypes, status, requestedAt: timestamp(raw.requestedAt, "dataRequirement.requestedAt"), blockers };
}

export function parseDataFulfillmentReceipt(value: unknown): DataFulfillmentReceiptContract {
  const raw = record(value, "dataFulfillment"); exactKeys(raw, ["schemaVersion", "tenant", "fulfillmentId", "requirementRef", "status", "artifactRefs", "fulfilledAt", "blockers"], "dataFulfillment");
  if (raw.schemaVersion !== DATA_FULFILLMENT_SCHEMA_VERSION) throw new TypeError("dataFulfillment.schemaVersion 无效");
  const status = enumValue<DataFulfillmentStatus>(raw.status, ["fulfilled", "partial", "rejected", "unknown"], "dataFulfillment.status");
  const artifactRefs = parseRefs(raw.artifactRefs, "dataFulfillment.artifactRefs"); const blockers = parseBlockers(raw.blockers, "dataFulfillment.blockers");
  if (status === "fulfilled" ? (!artifactRefs.length || blockers.length > 0) : blockers.length === 0) throw new TypeError("dataFulfillment 状态与 artifact/blocker 不一致");
  return { schemaVersion: DATA_FULFILLMENT_SCHEMA_VERSION, tenant: parseTenant(raw.tenant), fulfillmentId: text(raw.fulfillmentId, "dataFulfillment.fulfillmentId", 200), requirementRef: parseExactRef(raw.requirementRef, "dataFulfillment.requirementRef", "DataRequirementRevision"), status, artifactRefs, fulfilledAt: timestamp(raw.fulfilledAt, "dataFulfillment.fulfilledAt"), blockers };
}

export function parsePlatformObservation(value: unknown): PlatformObservationContract {
  const raw = record(value, "platformObservation"); exactKeys(raw, ["schemaVersion", "tenant", "observationId", "status", "observedAt", "sourceRef", "evidenceRefs", "blockers"], "platformObservation");
  if (raw.schemaVersion !== PLATFORM_OBSERVATION_SCHEMA_VERSION) throw new TypeError("platformObservation.schemaVersion 无效");
  const status = enumValue<ObservationLifecycle>(raw.status, ["draft", "ready", "running", "paused", "blocked", "unknown", "reconciling", "completed", "cancelled"], "platformObservation.status");
  const evidenceRefs = parseRefs(raw.evidenceRefs, "platformObservation.evidenceRefs"); const blockers = parseBlockers(raw.blockers, "platformObservation.blockers");
  if (status === "completed" && !evidenceRefs.length) throw new TypeError("completed observation 缺 evidenceRefs");
  if ((status === "blocked" || status === "unknown") && !blockers.length) throw new TypeError("blocked/unknown observation 缺 blocker");
  return { schemaVersion: PLATFORM_OBSERVATION_SCHEMA_VERSION, tenant: parseTenant(raw.tenant), observationId: text(raw.observationId, "platformObservation.observationId", 200), status, observedAt: timestamp(raw.observedAt, "platformObservation.observedAt"), sourceRef: parseExactRef(raw.sourceRef, "platformObservation.sourceRef", "PlatformSourceRevision"), evidenceRefs, blockers };
}

export function parseSourceMapping(value: unknown): SourceMappingContract {
  const raw = record(value, "sourceMapping"); exactKeys(raw, ["schemaVersion", "tenant", "mappingId", "observationRef", "sourceField", "canonicalField", "confidence", "confirmedBy", "blockers"], "sourceMapping");
  if (raw.schemaVersion !== SOURCE_MAPPING_SCHEMA_VERSION) throw new TypeError("sourceMapping.schemaVersion 无效");
  if (typeof raw.confidence !== "number" || raw.confidence < 0 || raw.confidence > 1) throw new TypeError("sourceMapping.confidence 无效");
  return { schemaVersion: SOURCE_MAPPING_SCHEMA_VERSION, tenant: parseTenant(raw.tenant), mappingId: text(raw.mappingId, "sourceMapping.mappingId", 200), observationRef: parseExactRef(raw.observationRef, "sourceMapping.observationRef", "PlatformObservation"), sourceField: text(raw.sourceField, "sourceMapping.sourceField", 500), canonicalField: text(raw.canonicalField, "sourceMapping.canonicalField", 500), confidence: raw.confidence, confirmedBy: raw.confirmedBy === null ? null : text(raw.confirmedBy, "sourceMapping.confirmedBy", 200), blockers: parseBlockers(raw.blockers, "sourceMapping.blockers") };
}

export function parseAdaptiveProfile(value: unknown): AdaptiveProfileContract {
  const raw = record(value, "adaptiveProfile"); exactKeys(raw, ["schemaVersion", "tenant", "profileId", "sourceRef", "hypothesisRefs", "coverage", "blockers"], "adaptiveProfile");
  if (raw.schemaVersion !== ADAPTIVE_PROFILE_SCHEMA_VERSION) throw new TypeError("adaptiveProfile.schemaVersion 无效");
  return { schemaVersion: ADAPTIVE_PROFILE_SCHEMA_VERSION, tenant: parseTenant(raw.tenant), profileId: text(raw.profileId, "adaptiveProfile.profileId", 200), sourceRef: parseExactRef(raw.sourceRef, "adaptiveProfile.sourceRef", "PlatformSourceRevision"), hypothesisRefs: parseRefs(raw.hypothesisRefs, "adaptiveProfile.hypothesisRefs", "SemanticHypothesisRevision"), coverage: parseCoverage(raw.coverage, "adaptiveProfile.coverage"), blockers: parseBlockers(raw.blockers, "adaptiveProfile.blockers") };
}

export function parseSemanticHydrationReceipt(value: unknown): SemanticHydrationReceiptContract {
  const raw = record(value, "semanticHydration"); exactKeys(raw, ["schemaVersion", "tenant", "hydrationId", "status", "observationRef", "mappingRef", "outputRefs", "hydratedAt", "blockers"], "semanticHydration");
  if (raw.schemaVersion !== SEMANTIC_HYDRATION_SCHEMA_VERSION) throw new TypeError("semanticHydration.schemaVersion 无效");
  const status = enumValue<SemanticHydrationStatus>(raw.status, ["succeeded", "partial", "blocked", "unknown"], "semanticHydration.status");
  const outputRefs = parseRefs(raw.outputRefs, "semanticHydration.outputRefs"); const blockers = parseBlockers(raw.blockers, "semanticHydration.blockers");
  if (status === "succeeded" ? (!outputRefs.length || blockers.length > 0) : blockers.length === 0) throw new TypeError("semanticHydration 状态与 output/blocker 不一致");
  return { schemaVersion: SEMANTIC_HYDRATION_SCHEMA_VERSION, tenant: parseTenant(raw.tenant), hydrationId: text(raw.hydrationId, "semanticHydration.hydrationId", 200), status, observationRef: parseExactRef(raw.observationRef, "semanticHydration.observationRef", "PlatformObservation"), mappingRef: parseExactRef(raw.mappingRef, "semanticHydration.mappingRef", "SourceMappingRevision"), outputRefs, hydratedAt: timestamp(raw.hydratedAt, "semanticHydration.hydratedAt"), blockers };
}
