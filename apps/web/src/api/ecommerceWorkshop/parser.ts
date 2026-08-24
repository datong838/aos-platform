import {
  ECOMMERCE_WORKSHOP_SCHEMA_VERSION,
  SOURCE_READINESS_SCHEMA_VERSION,
  TASK_COCKPIT_SCHEMA_VERSION,
  OPERATIONS_SCHEMA_VERSION,
  OPERATION_COMMAND_READINESS_SCHEMA_VERSION,
  OPERATION_COMMAND_OBSERVATION_SCHEMA_VERSION,
  type EcommerceWorkshopApiErrorBody,
  type EcommerceWorkshopModule,
  type EcommerceWorkshopModuleListResponse,
  type EcommerceWorkshopModuleReadinessResponse,
  type WorkshopDependencyRef,
  type WorkshopDependencyState,
  type WorkshopDependencyType,
  type WorkshopInstallationRef,
  type WorkshopModuleRef,
  type WorkshopPermissions,
  type WorkshopReadiness,
  type WorkshopReadinessBlocker,
  type WorkshopTenant,
  type SourceReadinessCounts,
  type SourceReadinessEnvelope,
  type SourceReadinessExactRef,
  type SourceReadinessItem,
  type SourceReadinessLatestRun,
  type SourceReadinessPolicyObservation,
  type SourceReadinessPolicyStatus,
  type SourceReadinessStatus,
  type TaskCockpitBlocker,
  type TaskCockpitCheckpoint,
  type TaskCockpitCheckpointPageResponse,
  type TaskCockpitCoreResponse,
  type TaskCockpitPage,
  type TaskCockpitProductionContextResponse,
  type TaskCockpitRun,
  type TaskCockpitExactRevisionRef,
  type TaskCockpitStageCompilation,
  type TaskCockpitStep,
  type TaskCockpitStepPageResponse,
  type TaskCockpitTask,
  type OperationsAuthorityRef,
  type OperationsBlocker,
  type OperationsCountLedger,
  type OperationsPage,
  type OperationsSlice,
  type OperationsSliceId,
  type OperationsViewResponse,
  type OperationCommandBlocker,
  type OperationCommandDescriptor,
  type OperationCommandId,
  type OperationCommandReadinessResponse,
  type ObservableOperationCommandId,
  type OperationCommandObservationResponse,
  type OperationCommandObservationStatus,
} from "./contracts";

const SHA256 = /^sha256:[0-9a-f]{64}$/;
const RAW_SHA256 = /^[0-9a-f]{64}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const MODULE_ID = /^ecommerce\.[a-z0-9]+(?:[.-][a-z0-9]+)*$/;
const ID = /^[a-z0-9]+(?:[.-][a-z0-9]+)*$/;
const REASON = /^[A-Z][A-Z0-9_]{1,119}$/;
const SEMVER = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$/;

function record(value: unknown, label: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new TypeError(`${label} 必须是对象`);
  return value as Record<string, unknown>;
}
function exact(raw: Record<string, unknown>, keys: readonly string[], label: string): void {
  const actual = Object.keys(raw).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    throw new TypeError(`${label} 字段漂移`);
  }
}
function text(value: unknown, label: string): string {
  if (typeof value !== "string" || !value || value !== value.trim() || value.includes("\u0000")) throw new TypeError(`${label} 必须是规范非空字符串`);
  return value;
}
function integer(value: unknown, label: string, minimum = 0): number {
  if (!Number.isSafeInteger(value) || (value as number) < minimum) throw new TypeError(`${label} 必须是安全整数`);
  return value as number;
}
function signedInteger(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value)) throw new TypeError(`${label} 必须是安全整数`);
  return value as number;
}
function bool(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") throw new TypeError(`${label} 必须是布尔值`);
  return value;
}
function boundedText(value: unknown, label: string, maximum: number): string {
  const result = text(value, label);
  if (result.length > maximum) throw new TypeError(`${label} 长度超限`);
  return result;
}
function nullable<T>(value: unknown, parse: (value: unknown) => T): T | null {
  return value === null ? null : parse(value);
}
function strings(value: unknown, label: string): string[] {
  if (!Array.isArray(value)) throw new TypeError(`${label} 必须是数组`);
  const result = value.map((item, index) => text(item, `${label}[${index}]`));
  if (new Set(result).size !== result.length || [...result].sort().some((item, index) => item !== result[index])) throw new TypeError(`${label} 必须唯一且排序`);
  return result;
}
function timestamp(value: unknown, label: string): string {
  const result = text(value, label);
  const date = new Date(result);
  if (Number.isNaN(date.valueOf()) || !/(Z|[+-]\d{2}:\d{2})$/.test(result)) throw new TypeError(`${label} 必须带时区`);
  return result;
}
function hash(value: unknown, label: string): string {
  const result = text(value, label);
  if (!SHA256.test(result)) throw new TypeError(`${label} 不是 SHA-256`);
  return result;
}
function enumValue<T extends string>(value: unknown, allowed: readonly T[], label: string): T {
  const result = text(value, label);
  if (!allowed.includes(result as T)) throw new TypeError(`${label} 未知枚举`);
  return result as T;
}

function parseTenant(value: unknown): WorkshopTenant {
  const raw = record(value, "tenant"); exact(raw, ["orgId", "projectId"], "tenant");
  return { orgId: text(raw.orgId, "tenant.orgId"), projectId: text(raw.projectId, "tenant.projectId") };
}
function parseInstallationRef(value: unknown): WorkshopInstallationRef {
  const raw = record(value, "installationRef");
  exact(raw, ["installationId", "revision", "compositionId", "lockRevision", "lockHash", "overlayRevision"], "installationRef");
  const installationId = text(raw.installationId, "installationRef.installationId");
  const compositionId = text(raw.compositionId, "installationRef.compositionId");
  if (!UUID.test(installationId) || !UUID.test(compositionId)) throw new TypeError("installationRef UUID 漂移");
  return { installationId, revision: integer(raw.revision, "installationRef.revision", 1), compositionId, lockRevision: integer(raw.lockRevision, "installationRef.lockRevision", 1), lockHash: hash(raw.lockHash, "installationRef.lockHash"), overlayRevision: text(raw.overlayRevision, "installationRef.overlayRevision") };
}
function parseModuleRef(value: unknown): WorkshopModuleRef {
  const raw = record(value, "moduleRef");
  exact(raw, ["publisher", "bundleId", "version", "bundleContentHash", "moduleArtifactRef", "moduleArtifactHash"], "moduleRef");
  const publisher = text(raw.publisher, "moduleRef.publisher"); const bundleId = text(raw.bundleId, "moduleRef.bundleId");
  if (!ID.test(publisher) || !ID.test(bundleId)) throw new TypeError("moduleRef identity 漂移");
  const moduleArtifactRef = text(raw.moduleArtifactRef, "moduleRef.moduleArtifactRef");
  if (!moduleArtifactRef.startsWith("bundle://") || /[\\?#]|(^|\/)\.\.(\/|$)/.test(moduleArtifactRef)) throw new TypeError("moduleArtifactRef 非法");
  const version = text(raw.version, "moduleRef.version"); if (!SEMVER.test(version)) throw new TypeError("moduleRef.version 非规范 SemVer");
  return { publisher, bundleId, version, bundleContentHash: hash(raw.bundleContentHash, "moduleRef.bundleContentHash"), moduleArtifactRef, moduleArtifactHash: hash(raw.moduleArtifactHash, "moduleRef.moduleArtifactHash") };
}
function parseDependencyRef(value: unknown): WorkshopDependencyRef {
  const raw = record(value, "dependencyRef"); exact(raw, ["resourceType", "resourceId", "revision", "contentHash", "authority"], "dependencyRef");
  return { resourceType: text(raw.resourceType, "dependencyRef.resourceType"), resourceId: text(raw.resourceId, "dependencyRef.resourceId"), revision: raw.revision === null ? null : text(raw.revision, "dependencyRef.revision"), contentHash: raw.contentHash === null ? null : hash(raw.contentHash, "dependencyRef.contentHash"), authority: text(raw.authority, "dependencyRef.authority") };
}
function parseBlocker(value: unknown): WorkshopReadinessBlocker {
  const raw = record(value, "blocker"); exact(raw, ["dependencyType", "dependencyId", "state", "reasonCode", "recoverable", "requiredAction", "ref"], "blocker");
  const reasonCode = text(raw.reasonCode, "blocker.reasonCode"); if (!REASON.test(reasonCode)) throw new TypeError("blocker.reasonCode 非法");
  return { dependencyType: enumValue<WorkshopDependencyType>(raw.dependencyType, ["object", "capability", "aip_feature", "data_scope", "permission", "registry", "installation"], "blocker.dependencyType"), dependencyId: text(raw.dependencyId, "blocker.dependencyId"), state: enumValue<WorkshopDependencyState>(raw.state, ["available", "degraded", "disabled", "blocked", "unknown"], "blocker.state"), reasonCode, recoverable: bool(raw.recoverable, "blocker.recoverable"), requiredAction: text(raw.requiredAction, "blocker.requiredAction"), ref: nullable(raw.ref, parseDependencyRef) };
}
function parsePermissions(value: unknown): WorkshopPermissions {
  const raw = record(value, "permissions"); exact(raw, ["roles", "markings", "dataScopes", "actionTypes"], "permissions");
  return { roles: strings(raw.roles, "permissions.roles"), markings: strings(raw.markings, "permissions.markings"), dataScopes: strings(raw.dataScopes, "permissions.dataScopes"), actionTypes: strings(raw.actionTypes, "permissions.actionTypes") };
}
export function parseEcommerceWorkshopModule(value: unknown): EcommerceWorkshopModule {
  const raw = record(value, "module");
  exact(raw, ["moduleId", "displayName", "menuLabel", "route", "slot", "order", "installationRef", "moduleRef", "readiness", "blockers", "permissions", "requiredObjects", "requiredCapabilities", "requiredAipFeatures", "viewRefs", "evalPackRefs", "productionContractRefs", "responsibilityTemplateRefs", "impactCalculatorRefs", "legacyAssetRefs", "legacyRoutes", "minimumRuntimeVersion", "lastReceiptRef"], "module");
  const moduleId = text(raw.moduleId, "module.moduleId"); if (!MODULE_ID.test(moduleId)) throw new TypeError("moduleId 非法");
  const route = text(raw.route, "module.route"); if (!route.startsWith("/workshop/") || route.endsWith("/")) throw new TypeError("route 非规范");
  const slot = enumValue(raw.slot, ["workshop.primary.ecommerce"] as const, "module.slot");
  const readiness = enumValue<WorkshopReadiness>(raw.readiness, ["available", "degraded", "disabled", "blocked", "unknown"], "module.readiness");
  if (!Array.isArray(raw.blockers)) throw new TypeError("module.blockers 必须是数组"); const blockers = raw.blockers.map(parseBlocker);
  if ((readiness === "available") !== (blockers.length === 0)) throw new TypeError("module readiness/blockers 不一致");
  const blockerKeys = blockers.map((item) => `${item.dependencyType}:${item.dependencyId}`); if (new Set(blockerKeys).size !== blockerKeys.length || [...blockerKeys].sort().some((item, index) => item !== blockerKeys[index])) throw new TypeError("module.blockers 必须唯一且排序");
  const minimumRuntimeVersion = text(raw.minimumRuntimeVersion, "module.minimumRuntimeVersion"); if (!SEMVER.test(minimumRuntimeVersion)) throw new TypeError("module.minimumRuntimeVersion 非规范 SemVer");
  return { moduleId, displayName: text(raw.displayName, "module.displayName"), menuLabel: text(raw.menuLabel, "module.menuLabel"), route, slot, order: integer(raw.order, "module.order"), installationRef: parseInstallationRef(raw.installationRef), moduleRef: parseModuleRef(raw.moduleRef), readiness, blockers, permissions: parsePermissions(raw.permissions), requiredObjects: strings(raw.requiredObjects, "module.requiredObjects"), requiredCapabilities: strings(raw.requiredCapabilities, "module.requiredCapabilities"), requiredAipFeatures: strings(raw.requiredAipFeatures, "module.requiredAipFeatures"), viewRefs: strings(raw.viewRefs, "module.viewRefs"), evalPackRefs: strings(raw.evalPackRefs, "module.evalPackRefs"), productionContractRefs: strings(raw.productionContractRefs, "module.productionContractRefs"), responsibilityTemplateRefs: strings(raw.responsibilityTemplateRefs, "module.responsibilityTemplateRefs"), impactCalculatorRefs: strings(raw.impactCalculatorRefs, "module.impactCalculatorRefs"), legacyAssetRefs: strings(raw.legacyAssetRefs, "module.legacyAssetRefs"), legacyRoutes: strings(raw.legacyRoutes, "module.legacyRoutes"), minimumRuntimeVersion, lastReceiptRef: nullable(raw.lastReceiptRef, parseDependencyRef) };
}
export function parseEcommerceWorkshopModuleList(value: unknown): EcommerceWorkshopModuleListResponse {
  const raw = record(value, "moduleList"); exact(raw, ["schemaVersion", "tenant", "evaluatedAt", "dataCutoff", "items", "count"], "moduleList");
  if (raw.schemaVersion !== ECOMMERCE_WORKSHOP_SCHEMA_VERSION) throw new TypeError("moduleList.schemaVersion 漂移");
  if (!Array.isArray(raw.items)) throw new TypeError("moduleList.items 必须是数组"); const items = raw.items.map(parseEcommerceWorkshopModule); const count = integer(raw.count, "moduleList.count");
  if (count !== items.length) throw new TypeError("moduleList.count 不一致");
  const ids = items.map((item) => item.moduleId), routes = items.map((item) => item.route), orders = items.map((item) => item.order); if (new Set(ids).size !== items.length || new Set(routes).size !== items.length || new Set(orders).size !== items.length || [...orders].sort((a, b) => a - b).some((item, index) => item !== orders[index])) throw new TypeError("moduleList identity/order 漂移");
  return { schemaVersion: ECOMMERCE_WORKSHOP_SCHEMA_VERSION, tenant: parseTenant(raw.tenant), evaluatedAt: timestamp(raw.evaluatedAt, "moduleList.evaluatedAt"), dataCutoff: raw.dataCutoff === null ? null : timestamp(raw.dataCutoff, "moduleList.dataCutoff"), items, count };
}
export function parseEcommerceWorkshopModuleReadiness(value: unknown): EcommerceWorkshopModuleReadinessResponse {
  const raw = record(value, "moduleReadiness"); exact(raw, ["schemaVersion", "tenant", "evaluatedAt", "dataCutoff", "item"], "moduleReadiness");
  if (raw.schemaVersion !== ECOMMERCE_WORKSHOP_SCHEMA_VERSION) throw new TypeError("moduleReadiness.schemaVersion 漂移");
  return { schemaVersion: ECOMMERCE_WORKSHOP_SCHEMA_VERSION, tenant: parseTenant(raw.tenant), evaluatedAt: timestamp(raw.evaluatedAt, "moduleReadiness.evaluatedAt"), dataCutoff: raw.dataCutoff === null ? null : timestamp(raw.dataCutoff, "moduleReadiness.dataCutoff"), item: parseEcommerceWorkshopModule(raw.item) };
}
export function parseEcommerceWorkshopApiError(value: unknown, fallback: string): EcommerceWorkshopApiErrorBody {
  try { const raw = record(value, "apiError"); exact(raw, ["code", "message", "details", "traceId"], "apiError"); return { code: text(raw.code, "apiError.code"), message: text(raw.message, "apiError.message"), details: raw.details === null ? null : record(raw.details, "apiError.details"), traceId: text(raw.traceId, "apiError.traceId") }; } catch { return { code: "INVALID_ERROR_RESPONSE", message: fallback, details: null, traceId: "" }; }
}

const SOURCE_STATUSES = ["ready", "empty", "degraded", "unknown", "stale", "failed", "blocked", "forbidden"] as const;
const SOURCE_STATUS_PRECEDENCE: Record<SourceReadinessStatus, number> = { ready: 0, empty: 1, degraded: 2, unknown: 3, stale: 4, failed: 5, blocked: 6, forbidden: 7 };
const SOURCE_PIPELINES = ["P01-shop-qyh", "P02-product-qyh", "P03-product-sku-qyh", "P04-category-qyh", "P05-order-qyh", "P06-order-line-qyh", "P07-shipment-qyh", "P08-customer-lite-qyh", "P09-weapp-qyh", "P10-system-config-qyh", "P11-product-review-qyh", "P12-payment-qyh"] as const;

function reasonCodes(value: unknown, label: string): string[] {
  const result = strings(value, label);
  if (result.some((item) => !REASON.test(item))) throw new TypeError(`${label} reason code 非法`);
  return result;
}
function parseSourceReadinessExactRef(value: unknown): SourceReadinessExactRef {
  const raw = record(value, "sourceReadiness.exactRef");
  exact(raw, ["resourceType", "resourceId", "revision", "contentHash", "authority"], "sourceReadiness.exactRef");
  const contentHash = text(raw.contentHash, "sourceReadiness.exactRef.contentHash");
  if (!RAW_SHA256.test(contentHash)) throw new TypeError("sourceReadiness.exactRef.contentHash 不是 SHA-256");
  return { resourceType: text(raw.resourceType, "sourceReadiness.exactRef.resourceType"), resourceId: text(raw.resourceId, "sourceReadiness.exactRef.resourceId"), revision: text(raw.revision, "sourceReadiness.exactRef.revision"), contentHash, authority: text(raw.authority, "sourceReadiness.exactRef.authority") };
}
function parseSourceReadinessLatestRun(value: unknown): SourceReadinessLatestRun {
  const raw = record(value, "sourceReadiness.latestRun");
  exact(raw, ["runId", "status", "scheduledFor", "startedAt", "finishedAt", "rowsWritten", "errorCode"], "sourceReadiness.latestRun");
  return { runId: nullable(raw.runId, (item) => boundedText(item, "sourceReadiness.latestRun.runId", 200)), status: enumValue(raw.status, ["succeeded", "failed", "running", "unknown"] as const, "sourceReadiness.latestRun.status"), scheduledFor: nullable(raw.scheduledFor, (item) => timestamp(item, "sourceReadiness.latestRun.scheduledFor")), startedAt: nullable(raw.startedAt, (item) => timestamp(item, "sourceReadiness.latestRun.startedAt")), finishedAt: nullable(raw.finishedAt, (item) => timestamp(item, "sourceReadiness.latestRun.finishedAt")), rowsWritten: nullable(raw.rowsWritten, (item) => integer(item, "sourceReadiness.latestRun.rowsWritten")), errorCode: nullable(raw.errorCode, (item) => boundedText(item, "sourceReadiness.latestRun.errorCode", 200)) };
}
function parseSourceReadinessCounts(value: unknown): SourceReadinessCounts {
  const raw = record(value, "sourceReadiness.counts");
  exact(raw, ["sourceTotal", "sourceActive", "sourceDeleted", "projectionTotal", "unexplainedDelta"], "sourceReadiness.counts");
  return { sourceTotal: nullable(raw.sourceTotal, (item) => integer(item, "sourceReadiness.counts.sourceTotal")), sourceActive: nullable(raw.sourceActive, (item) => integer(item, "sourceReadiness.counts.sourceActive")), sourceDeleted: nullable(raw.sourceDeleted, (item) => integer(item, "sourceReadiness.counts.sourceDeleted")), projectionTotal: nullable(raw.projectionTotal, (item) => integer(item, "sourceReadiness.counts.projectionTotal")), unexplainedDelta: nullable(raw.unexplainedDelta, (item) => signedInteger(item, "sourceReadiness.counts.unexplainedDelta")) };
}
function parseSourceReadinessPolicy(value: unknown): SourceReadinessPolicyObservation {
  const raw = record(value, "sourceReadiness.policy");
  exact(raw, ["status", "ruleRef", "summary"], "sourceReadiness.policy");
  return { status: enumValue<SourceReadinessPolicyStatus>(raw.status, ["pass", "fail", "unknown"], "sourceReadiness.policy.status"), ruleRef: nullable(raw.ruleRef, parseSourceReadinessExactRef), summary: nullable(raw.summary, (item) => boundedText(item, "sourceReadiness.policy.summary", 1000)) };
}
function parseSourceReadinessItem(value: unknown): SourceReadinessItem {
  const raw = record(value, "sourceReadiness.item");
  exact(raw, ["schemaVersion", "tenant", "sourceId", "pipelineId", "objectType", "status", "checkedAt", "observedAt", "sourceEventAt", "projectedAt", "dataCutoff", "freshnessExpiresAt", "sourceConfigRef", "mappingRef", "schemaRef", "maskingPolicyRef", "freshnessPolicyRef", "qualityPolicyRef", "reconciliationPolicyRef", "queryCapabilityRef", "latestRun", "counts", "quality", "reconciliation", "reasons", "blockers"], "sourceReadiness.item");
  if (raw.schemaVersion !== SOURCE_READINESS_SCHEMA_VERSION) throw new TypeError("sourceReadiness.item.schemaVersion 漂移");
  const item: SourceReadinessItem = { schemaVersion: SOURCE_READINESS_SCHEMA_VERSION, tenant: parseTenant(raw.tenant), sourceId: boundedText(raw.sourceId, "sourceReadiness.item.sourceId", 200), pipelineId: boundedText(raw.pipelineId, "sourceReadiness.item.pipelineId", 200), objectType: boundedText(raw.objectType, "sourceReadiness.item.objectType", 200), status: enumValue(raw.status, SOURCE_STATUSES, "sourceReadiness.item.status"), checkedAt: timestamp(raw.checkedAt, "sourceReadiness.item.checkedAt"), observedAt: nullable(raw.observedAt, (entry) => timestamp(entry, "sourceReadiness.item.observedAt")), sourceEventAt: nullable(raw.sourceEventAt, (entry) => timestamp(entry, "sourceReadiness.item.sourceEventAt")), projectedAt: nullable(raw.projectedAt, (entry) => timestamp(entry, "sourceReadiness.item.projectedAt")), dataCutoff: nullable(raw.dataCutoff, (entry) => timestamp(entry, "sourceReadiness.item.dataCutoff")), freshnessExpiresAt: nullable(raw.freshnessExpiresAt, (entry) => timestamp(entry, "sourceReadiness.item.freshnessExpiresAt")), sourceConfigRef: nullable(raw.sourceConfigRef, parseSourceReadinessExactRef), mappingRef: nullable(raw.mappingRef, parseSourceReadinessExactRef), schemaRef: nullable(raw.schemaRef, parseSourceReadinessExactRef), maskingPolicyRef: nullable(raw.maskingPolicyRef, parseSourceReadinessExactRef), freshnessPolicyRef: nullable(raw.freshnessPolicyRef, parseSourceReadinessExactRef), qualityPolicyRef: nullable(raw.qualityPolicyRef, parseSourceReadinessExactRef), reconciliationPolicyRef: nullable(raw.reconciliationPolicyRef, parseSourceReadinessExactRef), queryCapabilityRef: nullable(raw.queryCapabilityRef, parseSourceReadinessExactRef), latestRun: parseSourceReadinessLatestRun(raw.latestRun), counts: parseSourceReadinessCounts(raw.counts), quality: parseSourceReadinessPolicy(raw.quality), reconciliation: parseSourceReadinessPolicy(raw.reconciliation), reasons: reasonCodes(raw.reasons, "sourceReadiness.item.reasons"), blockers: reasonCodes(raw.blockers, "sourceReadiness.item.blockers") };
  if (item.status === "ready" && ([item.sourceConfigRef, item.mappingRef, item.schemaRef, item.maskingPolicyRef, item.freshnessPolicyRef, item.qualityPolicyRef, item.reconciliationPolicyRef, item.queryCapabilityRef].some((entry) => entry === null) || item.latestRun.status !== "succeeded" || item.quality.status !== "pass" || item.reconciliation.status !== "pass" || item.dataCutoff === null || item.freshnessExpiresAt === null || item.blockers.length > 0)) throw new TypeError("sourceReadiness.item 伪 ready");
  return item;
}
export function parseSourceReadinessEnvelope(value: unknown): SourceReadinessEnvelope {
  const raw = record(value, "sourceReadiness");
  exact(raw, ["schemaVersion", "tenant", "checkedAt", "cutoffAt", "status", "sources", "receiptRef"], "sourceReadiness");
  if (raw.schemaVersion !== SOURCE_READINESS_SCHEMA_VERSION) throw new TypeError("sourceReadiness.schemaVersion 漂移");
  if (!Array.isArray(raw.sources)) throw new TypeError("sourceReadiness.sources 必须是数组");
  const tenant = parseTenant(raw.tenant); const checkedAt = timestamp(raw.checkedAt, "sourceReadiness.checkedAt"); const sources = raw.sources.map(parseSourceReadinessItem);
  if (sources.length !== SOURCE_PIPELINES.length || sources.some((item, index) => item.pipelineId !== SOURCE_PIPELINES[index])) throw new TypeError("sourceReadiness.sources 必须是 ordered P01-P12");
  if (sources.some((item) => item.tenant.orgId !== tenant.orgId || item.tenant.projectId !== tenant.projectId)) throw new TypeError("sourceReadiness tenant 漂移");
  if (sources.some((item) => item.checkedAt !== checkedAt)) throw new TypeError("sourceReadiness checkedAt 漂移");
  const status = enumValue<SourceReadinessStatus>(raw.status, SOURCE_STATUSES, "sourceReadiness.status");
  const aggregate = sources.reduce<SourceReadinessStatus>((current, item) => SOURCE_STATUS_PRECEDENCE[item.status] > SOURCE_STATUS_PRECEDENCE[current] ? item.status : current, "ready");
  if (status !== aggregate) throw new TypeError("sourceReadiness aggregate status 漂移");
  return { schemaVersion: SOURCE_READINESS_SCHEMA_VERSION, tenant, checkedAt, cutoffAt: timestamp(raw.cutoffAt, "sourceReadiness.cutoffAt"), status, sources, receiptRef: nullable(raw.receiptRef, parseSourceReadinessExactRef) };
}

const TASK_STATUSES = ["pending", "planning", "awaiting_approval", "approved", "executing", "paused", "completed", "failed", "cancelled", "rolled_back"] as const;
const RUN_STATUSES = ["queued", "running", "succeeded", "failed", "cancelled", "unknown"] as const;
const STEP_STATUSES = ["queued", "running", "succeeded", "failed", "skipped", "unknown"] as const;
const DECIMAL = /^\d+(?:\.\d+)?$/;

function parseTaskCockpitPage(value: unknown): TaskCockpitPage {
  const raw = record(value, "taskCockpit.page"); exact(raw, ["limit", "count", "hasMore", "nextCursor"], "taskCockpit.page");
  const limit = integer(raw.limit, "taskCockpit.page.limit", 1); if (limit > 100) throw new TypeError("taskCockpit.page.limit 超限");
  const count = integer(raw.count, "taskCockpit.page.count"); if (count > 100 || count > limit) throw new TypeError("taskCockpit.page.count 不一致");
  const hasMore = bool(raw.hasMore, "taskCockpit.page.hasMore");
  const nextCursor = raw.nextCursor === null ? null : boundedText(raw.nextCursor, "taskCockpit.page.nextCursor", 4096);
  if (hasMore !== (nextCursor !== null)) throw new TypeError("taskCockpit.page cursor 不一致");
  return { limit, count, hasMore, nextCursor };
}
function parseTaskCockpitBlocker(value: unknown): TaskCockpitBlocker {
  const raw = record(value, "taskCockpit.blocker"); exact(raw, ["code", "severity", "dependency", "requiredAction"], "taskCockpit.blocker");
  const code = boundedText(raw.code, "taskCockpit.blocker.code", 120); if (!REASON.test(code)) throw new TypeError("taskCockpit.blocker.code 非法");
  return { code, severity: enumValue(raw.severity, ["warning", "blocking"] as const, "taskCockpit.blocker.severity"), dependency: boundedText(raw.dependency, "taskCockpit.blocker.dependency", 160), requiredAction: boundedText(raw.requiredAction, "taskCockpit.blocker.requiredAction", 500) };
}
function parseTaskCockpitRun(value: unknown): TaskCockpitRun {
  const raw = record(value, "taskCockpit.run"); exact(raw, ["runId", "planRevisionId", "status", "version", "startedAt", "finishedAt", "createdAt", "updatedAt"], "taskCockpit.run");
  return { runId: boundedText(raw.runId, "taskCockpit.run.runId", 200), planRevisionId: boundedText(raw.planRevisionId, "taskCockpit.run.planRevisionId", 200), status: enumValue(raw.status, RUN_STATUSES, "taskCockpit.run.status"), version: integer(raw.version, "taskCockpit.run.version", 1), startedAt: nullable(raw.startedAt, (item) => timestamp(item, "taskCockpit.run.startedAt")), finishedAt: nullable(raw.finishedAt, (item) => timestamp(item, "taskCockpit.run.finishedAt")), createdAt: timestamp(raw.createdAt, "taskCockpit.run.createdAt"), updatedAt: timestamp(raw.updatedAt, "taskCockpit.run.updatedAt") };
}
function parseTaskCockpitTask(value: unknown): TaskCockpitTask {
  const raw = record(value, "taskCockpit.task"); exact(raw, ["taskId", "taskType", "title", "status", "priority", "version", "currentPlanRevisionId", "createdAt", "updatedAt", "run"], "taskCockpit.task");
  const priority = integer(raw.priority, "taskCockpit.task.priority"); if (priority > 100) throw new TypeError("taskCockpit.task.priority 超限");
  return { taskId: boundedText(raw.taskId, "taskCockpit.task.taskId", 200), taskType: boundedText(raw.taskType, "taskCockpit.task.taskType", 160), title: boundedText(raw.title, "taskCockpit.task.title", 500), status: enumValue(raw.status, TASK_STATUSES, "taskCockpit.task.status"), priority, version: integer(raw.version, "taskCockpit.task.version", 1), currentPlanRevisionId: nullable(raw.currentPlanRevisionId, (item) => boundedText(item, "taskCockpit.task.currentPlanRevisionId", 200)), createdAt: timestamp(raw.createdAt, "taskCockpit.task.createdAt"), updatedAt: timestamp(raw.updatedAt, "taskCockpit.task.updatedAt"), run: nullable(raw.run, parseTaskCockpitRun) };
}
function parseTaskCockpitStep(value: unknown): TaskCockpitStep {
  const raw = record(value, "taskCockpit.step"); exact(raw, ["stepRunId", "stepKey", "attempt", "status", "tokenCount", "costAmount", "hasInputRefs", "hasOutputRefs", "hasError", "createdAt", "updatedAt"], "taskCockpit.step");
  const costAmount = text(raw.costAmount, "taskCockpit.step.costAmount"); if (!DECIMAL.test(costAmount)) throw new TypeError("taskCockpit.step.costAmount 非规范 decimal");
  return { stepRunId: boundedText(raw.stepRunId, "taskCockpit.step.stepRunId", 200), stepKey: boundedText(raw.stepKey, "taskCockpit.step.stepKey", 200), attempt: integer(raw.attempt, "taskCockpit.step.attempt", 1), status: enumValue(raw.status, STEP_STATUSES, "taskCockpit.step.status"), tokenCount: integer(raw.tokenCount, "taskCockpit.step.tokenCount"), costAmount, hasInputRefs: bool(raw.hasInputRefs, "taskCockpit.step.hasInputRefs"), hasOutputRefs: bool(raw.hasOutputRefs, "taskCockpit.step.hasOutputRefs"), hasError: bool(raw.hasError, "taskCockpit.step.hasError"), createdAt: timestamp(raw.createdAt, "taskCockpit.step.createdAt"), updatedAt: timestamp(raw.updatedAt, "taskCockpit.step.updatedAt") };
}
function parseTaskCockpitCheckpoint(value: unknown): TaskCockpitCheckpoint {
  const raw = record(value, "taskCockpit.checkpoint"); exact(raw, ["checkpointId", "sequence", "schemaVersion", "stepKey", "stateHash", "artifactCount", "createdAt"], "taskCockpit.checkpoint");
  return { checkpointId: boundedText(raw.checkpointId, "taskCockpit.checkpoint.checkpointId", 200), sequence: integer(raw.sequence, "taskCockpit.checkpoint.sequence", 1), schemaVersion: integer(raw.schemaVersion, "taskCockpit.checkpoint.schemaVersion", 1), stepKey: nullable(raw.stepKey, (item) => boundedText(item, "taskCockpit.checkpoint.stepKey", 200)), stateHash: boundedText(raw.stateHash, "taskCockpit.checkpoint.stateHash", 200), artifactCount: integer(raw.artifactCount, "taskCockpit.checkpoint.artifactCount"), createdAt: timestamp(raw.createdAt, "taskCockpit.checkpoint.createdAt") };
}
function parseTaskCockpitBase(raw: Record<string, unknown>, label: string): { tenant: WorkshopTenant; evaluatedAt: string } {
  if (raw.schemaVersion !== TASK_COCKPIT_SCHEMA_VERSION) throw new TypeError(`${label}.schemaVersion 漂移`);
  if (raw.stateConsistency !== "current_state_per_page") throw new TypeError(`${label}.stateConsistency 漂移`);
  return { tenant: parseTenant(raw.tenant), evaluatedAt: timestamp(raw.evaluatedAt, `${label}.evaluatedAt`) };
}
function assertUnique(items: readonly string[], label: string): void { if (new Set(items).size !== items.length) throw new TypeError(`${label} identity 重复`); }

export function parseTaskCockpitCore(value: unknown): TaskCockpitCoreResponse {
  const raw = record(value, "taskCockpit.core"); exact(raw, ["schemaVersion", "tenant", "evaluatedAt", "taskCutoff", "stateConsistency", "readiness", "blockers", "items", "page"], "taskCockpit.core");
  const base = parseTaskCockpitBase(raw, "taskCockpit.core"); if (raw.readiness !== "degraded") throw new TypeError("taskCockpit.core.readiness 漂移");
  if (!Array.isArray(raw.blockers) || raw.blockers.length < 3 || raw.blockers.length > 20) throw new TypeError("taskCockpit.core.blockers 数量非法"); const blockers = raw.blockers.map(parseTaskCockpitBlocker); assertUnique(blockers.map((item) => item.code), "taskCockpit.core.blockers");
  if (!Array.isArray(raw.items)) throw new TypeError("taskCockpit.core.items 必须是数组"); const items = raw.items.map(parseTaskCockpitTask); assertUnique(items.map((item) => item.taskId), "taskCockpit.core.items");
  const page = parseTaskCockpitPage(raw.page); if (page.count !== items.length) throw new TypeError("taskCockpit.core.page count 不一致");
  return { schemaVersion: TASK_COCKPIT_SCHEMA_VERSION, ...base, taskCutoff: timestamp(raw.taskCutoff, "taskCockpit.core.taskCutoff"), stateConsistency: "current_state_per_page", readiness: "degraded", blockers, items, page };
}
export function parseTaskCockpitSteps(value: unknown): TaskCockpitStepPageResponse {
  const raw = record(value, "taskCockpit.steps"); exact(raw, ["schemaVersion", "tenant", "runId", "evaluatedAt", "membershipCutoff", "stateConsistency", "items", "page"], "taskCockpit.steps"); const base = parseTaskCockpitBase(raw, "taskCockpit.steps");
  if (!Array.isArray(raw.items)) throw new TypeError("taskCockpit.steps.items 必须是数组"); const items = raw.items.map(parseTaskCockpitStep); assertUnique(items.map((item) => item.stepRunId), "taskCockpit.steps.items"); const page = parseTaskCockpitPage(raw.page); if (page.count !== items.length) throw new TypeError("taskCockpit.steps.page count 不一致");
  return { schemaVersion: TASK_COCKPIT_SCHEMA_VERSION, ...base, runId: boundedText(raw.runId, "taskCockpit.steps.runId", 200), membershipCutoff: timestamp(raw.membershipCutoff, "taskCockpit.steps.membershipCutoff"), stateConsistency: "current_state_per_page", items, page };
}
export function parseTaskCockpitCheckpoints(value: unknown): TaskCockpitCheckpointPageResponse {
  const raw = record(value, "taskCockpit.checkpoints"); exact(raw, ["schemaVersion", "tenant", "runId", "evaluatedAt", "membershipCutoff", "stateConsistency", "items", "page"], "taskCockpit.checkpoints"); const base = parseTaskCockpitBase(raw, "taskCockpit.checkpoints");
  if (!Array.isArray(raw.items)) throw new TypeError("taskCockpit.checkpoints.items 必须是数组"); const items = raw.items.map(parseTaskCockpitCheckpoint); assertUnique(items.map((item) => item.checkpointId), "taskCockpit.checkpoints.items"); const page = parseTaskCockpitPage(raw.page); if (page.count !== items.length) throw new TypeError("taskCockpit.checkpoints.page count 不一致");
  return { schemaVersion: TASK_COCKPIT_SCHEMA_VERSION, ...base, runId: boundedText(raw.runId, "taskCockpit.checkpoints.runId", 200), membershipCutoff: timestamp(raw.membershipCutoff, "taskCockpit.checkpoints.membershipCutoff"), stateConsistency: "current_state_per_page", items, page };
}

function parseTaskCockpitExactRef(value: unknown, expectedType: string, label: string): TaskCockpitExactRevisionRef {
  const raw = record(value, label); exact(raw, ["resourceType", "resourceId", "revision", "contentHash"], label);
  const resourceType = boundedText(raw.resourceType, `${label}.resourceType`, 80);
  if (resourceType !== expectedType) throw new TypeError(`${label}.resourceType 漂移`);
  const contentHash = boundedText(raw.contentHash, `${label}.contentHash`, 64);
  if (!RAW_SHA256.test(contentHash)) throw new TypeError(`${label}.contentHash 不是 SHA-256`);
  return { resourceType, resourceId: boundedText(raw.resourceId, `${label}.resourceId`, 200), revision: integer(raw.revision, `${label}.revision`, 1), contentHash };
}
function parseTaskCockpitStage(value: unknown): TaskCockpitStageCompilation {
  const raw = record(value, "taskCockpit.productionContext.stage");
  exact(raw, ["stageId", "title", "dependsOn", "requiredSlotIds", "applicabilityResult", "evaluatedProfile"], "taskCockpit.productionContext.stage");
  const uniqueList = (item: unknown, label: string): string[] => {
    if (!Array.isArray(item)) throw new TypeError(`${label} 必须是数组`);
    const result = item.map((entry, index) => boundedText(entry, `${label}[${index}]`, 200));
    if (new Set(result).size !== result.length) throw new TypeError(`${label} identity 重复`);
    return result;
  };
  const stageId = boundedText(raw.stageId, "taskCockpit.productionContext.stage.stageId", 200);
  const dependsOn = uniqueList(raw.dependsOn, "taskCockpit.productionContext.stage.dependsOn");
  if (dependsOn.includes(stageId)) throw new TypeError("taskCockpit.productionContext.stage 自依赖");
  return { stageId, title: boundedText(raw.title, "taskCockpit.productionContext.stage.title", 500), dependsOn, requiredSlotIds: uniqueList(raw.requiredSlotIds, "taskCockpit.productionContext.stage.requiredSlotIds"), applicabilityResult: enumValue(raw.applicabilityResult, ["applicable", "not_applicable"] as const, "taskCockpit.productionContext.stage.applicabilityResult"), evaluatedProfile: boundedText(raw.evaluatedProfile, "taskCockpit.productionContext.stage.evaluatedProfile", 160) };
}
export function parseTaskCockpitProductionContext(value: unknown): TaskCockpitProductionContextResponse {
  const raw = record(value, "taskCockpit.productionContext");
  exact(raw, ["schemaVersion", "tenant", "runId", "taskId", "evaluatedAt", "planRef", "stageTemplateRef", "responsibilityPlanRef", "compilerVersion", "stages", "applicableStageIds", "notApplicableStageIds"], "taskCockpit.productionContext");
  if (raw.schemaVersion !== TASK_COCKPIT_SCHEMA_VERSION || raw.compilerVersion !== "w2c.v1") throw new TypeError("taskCockpit.productionContext contract 漂移");
  if (!Array.isArray(raw.stages) || raw.stages.length === 0) throw new TypeError("taskCockpit.productionContext.stages 必须为非空数组");
  const stages = raw.stages.map(parseTaskCockpitStage); assertUnique(stages.map((item) => item.stageId), "taskCockpit.productionContext.stages");
  const parsePartition = (item: unknown, label: string): string[] => { if (!Array.isArray(item)) throw new TypeError(`${label} 必须是数组`); const result = item.map((entry, index) => boundedText(entry, `${label}[${index}]`, 200)); assertUnique(result, label); return result; };
  const applicableStageIds = parsePartition(raw.applicableStageIds, "taskCockpit.productionContext.applicableStageIds");
  const notApplicableStageIds = parsePartition(raw.notApplicableStageIds, "taskCockpit.productionContext.notApplicableStageIds");
  const partition = [...applicableStageIds, ...notApplicableStageIds];
  if (partition.length !== stages.length || new Set(partition).size !== stages.length || stages.some((stage) => !partition.includes(stage.stageId) || (stage.applicabilityResult === "applicable") !== applicableStageIds.includes(stage.stageId))) throw new TypeError("taskCockpit.productionContext stage partition 漂移");
  return { schemaVersion: TASK_COCKPIT_SCHEMA_VERSION, tenant: parseTenant(raw.tenant), runId: boundedText(raw.runId, "taskCockpit.productionContext.runId", 200), taskId: boundedText(raw.taskId, "taskCockpit.productionContext.taskId", 200), evaluatedAt: timestamp(raw.evaluatedAt, "taskCockpit.productionContext.evaluatedAt"), planRef: parseTaskCockpitExactRef(raw.planRef, "PlanRevision", "taskCockpit.productionContext.planRef"), stageTemplateRef: parseTaskCockpitExactRef(raw.stageTemplateRef, "StageTemplateRevision", "taskCockpit.productionContext.stageTemplateRef"), responsibilityPlanRef: parseTaskCockpitExactRef(raw.responsibilityPlanRef, "ResponsibilityPlanRevision", "taskCockpit.productionContext.responsibilityPlanRef"), compilerVersion: "w2c.v1", stages, applicableStageIds, notApplicableStageIds };
}

const OPERATIONS_SLICE_IDS = ["orders", "orderLines", "inventory", "shipments", "payments", "aftersaleEvents", "operationCases"] as const satisfies readonly OperationsSliceId[];

function parseOperationsAuthorityRef(value: unknown): OperationsAuthorityRef {
  const raw = record(value, "operations.authorityRef");
  exact(raw, ["resourceType", "resourceId", "revision", "contentHash", "receiptId"], "operations.authorityRef");
  return {
    resourceType: boundedText(raw.resourceType, "operations.authorityRef.resourceType", 120),
    resourceId: boundedText(raw.resourceId, "operations.authorityRef.resourceId", 240),
    revision: integer(raw.revision, "operations.authorityRef.revision", 1),
    contentHash: hash(raw.contentHash, "operations.authorityRef.contentHash"),
    receiptId: boundedText(raw.receiptId, "operations.authorityRef.receiptId", 240),
  };
}

function parseOperationsBlocker(value: unknown): OperationsBlocker {
  const raw = record(value, "operations.blocker");
  exact(raw, ["code", "dependency", "requiredAction"], "operations.blocker");
  const code = boundedText(raw.code, "operations.blocker.code", 120);
  if (!REASON.test(code)) throw new TypeError("operations.blocker.code 非法");
  return { code, dependency: boundedText(raw.dependency, "operations.blocker.dependency", 240), requiredAction: boundedText(raw.requiredAction, "operations.blocker.requiredAction", 1000) };
}

function parseOperationsCountLedger(value: unknown): OperationsCountLedger {
  const raw = record(value, "operations.countLedger");
  exact(raw, ["sourceTotal", "attached", "unmatched", "conflicted"], "operations.countLedger");
  const result = {
    sourceTotal: integer(raw.sourceTotal, "operations.countLedger.sourceTotal"),
    attached: integer(raw.attached, "operations.countLedger.attached"),
    unmatched: integer(raw.unmatched, "operations.countLedger.unmatched"),
    conflicted: integer(raw.conflicted, "operations.countLedger.conflicted"),
  };
  if (result.sourceTotal !== result.attached + result.unmatched + result.conflicted) throw new TypeError("operations.countLedger 数量不守恒");
  return result;
}

function parseOperationsSlice(value: unknown, expectedId: OperationsSliceId, expectedCutoff: string): OperationsSlice {
  const raw = record(value, `operations.slices.${expectedId}`);
  exact(raw, ["sliceId", "status", "dataCutoff", "authorityRefs", "blockers", "countLedger"], `operations.slices.${expectedId}`);
  const sliceId = enumValue<OperationsSliceId>(raw.sliceId, OPERATIONS_SLICE_IDS, "operations.sliceId");
  if (sliceId !== expectedId) throw new TypeError("operations.slices canonical order 漂移");
  const status = enumValue(raw.status, ["ready", "blocked"] as const, `operations.${sliceId}.status`);
  const dataCutoff = timestamp(raw.dataCutoff, `operations.${sliceId}.dataCutoff`);
  if (dataCutoff !== expectedCutoff) throw new TypeError(`operations.${sliceId}.dataCutoff 漂移`);
  if (!Array.isArray(raw.authorityRefs) || !Array.isArray(raw.blockers)) throw new TypeError(`operations.${sliceId} refs/blockers 必须是数组`);
  const authorityRefs = raw.authorityRefs.map(parseOperationsAuthorityRef);
  const blockers = raw.blockers.map(parseOperationsBlocker);
  assertUnique(authorityRefs.map((item) => `${item.resourceType}:${item.resourceId}:${item.revision}:${item.contentHash}:${item.receiptId}`), `operations.${sliceId}.authorityRefs`);
  assertUnique(blockers.map((item) => item.code), `operations.${sliceId}.blockers`);
  if (status === "ready" && (authorityRefs.length === 0 || blockers.length !== 0)) throw new TypeError(`operations.${sliceId} 伪 ready`);
  if (status === "blocked" && blockers.length === 0) throw new TypeError(`operations.${sliceId} 伪 blocked`);
  return { sliceId, status, dataCutoff, authorityRefs, blockers, countLedger: parseOperationsCountLedger(raw.countLedger) };
}

function parseOperationsPage(value: unknown): OperationsPage {
  const raw = record(value, "operations.page");
  exact(raw, ["limit", "count", "hasMore", "nextCursor"], "operations.page");
  const result = { limit: integer(raw.limit, "operations.page.limit", 1), count: integer(raw.count, "operations.page.count"), hasMore: bool(raw.hasMore, "operations.page.hasMore"), nextCursor: raw.nextCursor === null ? null : boundedText(raw.nextCursor, "operations.page.nextCursor", 4096) };
  if (result.limit > 100 || result.hasMore !== (result.nextCursor !== null) || result.hasMore || result.nextCursor !== null) throw new TypeError("operations.page cursor 漂移");
  return result;
}

export function parseOperationsView(value: unknown, expectedTenant?: WorkshopTenant): OperationsViewResponse {
  const raw = record(value, "operations");
  exact(raw, ["schemaVersion", "tenant", "evaluatedAt", "dataCutoff", "readiness", "slices", "page"], "operations");
  if (raw.schemaVersion !== OPERATIONS_SCHEMA_VERSION) throw new TypeError("operations.schemaVersion 漂移");
  if (raw.readiness !== "degraded") throw new TypeError("operations.readiness 漂移");
  const tenant = parseTenant(raw.tenant);
  if (expectedTenant && (tenant.orgId !== expectedTenant.orgId || tenant.projectId !== expectedTenant.projectId)) throw new TypeError("operations.tenant 漂移");
  const dataCutoff = timestamp(raw.dataCutoff, "operations.dataCutoff");
  if (!Array.isArray(raw.slices) || raw.slices.length !== OPERATIONS_SLICE_IDS.length) throw new TypeError("operations.slices 必须是 canonical order 七切片");
  const rawSlices = raw.slices;
  const slices = OPERATIONS_SLICE_IDS.map((sliceId, index) => parseOperationsSlice(rawSlices[index], sliceId, dataCutoff));
  const page = parseOperationsPage(raw.page);
  const attached = slices.reduce((total, slice) => total + slice.countLedger.attached, 0);
  if (page.count !== attached) throw new TypeError("operations.page count 不一致");
  return { schemaVersion: OPERATIONS_SCHEMA_VERSION, tenant, evaluatedAt: timestamp(raw.evaluatedAt, "operations.evaluatedAt"), dataCutoff, readiness: "degraded", slices, page };
}

const OPERATION_COMMAND_IDS = ["classify", "createCase", "changeMembership", "manageSla", "automationKill", "refund"] as const satisfies readonly OperationCommandId[];

function parseOperationCommandBlocker(value: unknown): OperationCommandBlocker {
  const raw = record(value, "operationCommand.blocker");
  exact(raw, ["code", "dependency", "requiredAction"], "operationCommand.blocker");
  const code = boundedText(raw.code, "operationCommand.blocker.code", 120);
  if (!REASON.test(code)) throw new TypeError("operationCommand.blocker.code 非法");
  return { code, dependency: boundedText(raw.dependency, "operationCommand.blocker.dependency", 160), requiredAction: boundedText(raw.requiredAction, "operationCommand.blocker.requiredAction", 500) };
}

function parseOperationCommand(value: unknown, expectedId: OperationCommandId): OperationCommandDescriptor {
  const raw = record(value, `operationCommand.${expectedId}`);
  exact(raw, ["commandId", "label", "status", "risk", "sideEffect", "blockers"], `operationCommand.${expectedId}`);
  const commandId = enumValue(raw.commandId, OPERATION_COMMAND_IDS, "operationCommand.commandId");
  if (commandId !== expectedId) throw new TypeError("operationCommand canonical order 漂移");
  const status = enumValue(raw.status, ["ready", "blocked"] as const, `operationCommand.${commandId}.status`);
  if (!Array.isArray(raw.blockers)) throw new TypeError(`operationCommand.${commandId}.blockers 必须是数组`);
  const blockers = raw.blockers.map(parseOperationCommandBlocker);
  assertUnique(blockers.map((item) => item.code), `operationCommand.${commandId}.blockers`);
  if (status === "ready" && blockers.length) throw new TypeError(`operationCommand.${commandId} 伪 ready`);
  if (status === "blocked" && blockers.length === 0) throw new TypeError(`operationCommand.${commandId} 伪 blocked`);
  return { commandId, label: boundedText(raw.label, `operationCommand.${commandId}.label`, 80), status, risk: enumValue(raw.risk, ["controlled", "high"] as const, `operationCommand.${commandId}.risk`), sideEffect: enumValue(raw.sideEffect, ["internalAuthority", "external"] as const, `operationCommand.${commandId}.sideEffect`), blockers };
}

export function parseOperationCommandReadiness(value: unknown, expectedTenant?: WorkshopTenant): OperationCommandReadinessResponse {
  const raw = record(value, "operationCommandReadiness");
  exact(raw, ["schemaVersion", "tenant", "evaluatedAt", "commands"], "operationCommandReadiness");
  if (raw.schemaVersion !== OPERATION_COMMAND_READINESS_SCHEMA_VERSION) throw new TypeError("operationCommandReadiness.schemaVersion 漂移");
  const tenant = parseTenant(raw.tenant);
  if (expectedTenant && (tenant.orgId !== expectedTenant.orgId || tenant.projectId !== expectedTenant.projectId)) throw new TypeError("operationCommandReadiness.tenant 漂移");
  if (!Array.isArray(raw.commands) || raw.commands.length !== OPERATION_COMMAND_IDS.length) throw new TypeError("operationCommandReadiness.commands 必须是 canonical order 六命令");
  const rawCommands = raw.commands;
  const commands = OPERATION_COMMAND_IDS.map((commandId, index) => parseOperationCommand(rawCommands[index], commandId));
  return { schemaVersion: OPERATION_COMMAND_READINESS_SCHEMA_VERSION, tenant, evaluatedAt: timestamp(raw.evaluatedAt, "operationCommandReadiness.evaluatedAt"), commands };
}

const OBSERVABLE_OPERATION_COMMAND_IDS = ["classify", "createCase", "changeMembership", "manageSla", "automationKill"] as const satisfies readonly ObservableOperationCommandId[];

export function parseOperationCommandObservation(
  value: unknown,
  expectedTenant?: WorkshopTenant,
  expectedProposalId?: string,
  expectedLeaseId?: string,
): OperationCommandObservationResponse {
  const raw = record(value, "operationCommandObservation");
  exact(raw, ["schemaVersion", "tenant", "proposalId", "leaseId", "commandId", "status", "proposalHash", "receiptId", "requestFingerprint", "operationReceiptId", "replayAllowed"], "operationCommandObservation");
  if (raw.schemaVersion !== OPERATION_COMMAND_OBSERVATION_SCHEMA_VERSION) throw new TypeError("operationCommandObservation.schemaVersion 漂移");
  const tenant = parseTenant(raw.tenant);
  if (expectedTenant && (tenant.orgId !== expectedTenant.orgId || tenant.projectId !== expectedTenant.projectId)) throw new TypeError("operationCommandObservation.tenant 漂移");
  const proposalId = boundedText(raw.proposalId, "operationCommandObservation.proposalId", 300);
  const leaseId = boundedText(raw.leaseId, "operationCommandObservation.leaseId", 300);
  if (expectedProposalId !== undefined && proposalId !== expectedProposalId) throw new TypeError("operationCommandObservation.proposalId 漂移");
  if (expectedLeaseId !== undefined && leaseId !== expectedLeaseId) throw new TypeError("operationCommandObservation.leaseId 漂移");
  if (raw.replayAllowed !== false) throw new TypeError("operationCommandObservation.replay 必须禁止");
  const receiptId = nullable(raw.receiptId, (item) => boundedText(item, "operationCommandObservation.receiptId", 300));
  const requestFingerprint = nullable(raw.requestFingerprint, (item) => {
    const result = boundedText(item, "operationCommandObservation.requestFingerprint", 64);
    if (!RAW_SHA256.test(result)) throw new TypeError("operationCommandObservation.requestFingerprint 不是 SHA-256");
    return result;
  });
  const operationReceiptId = nullable(raw.operationReceiptId, (item) => boundedText(item, "operationCommandObservation.operationReceiptId", 300));
  if ((receiptId === null) !== (requestFingerprint === null) || (receiptId === null && operationReceiptId !== null)) throw new TypeError("operationCommandObservation receipt 链漂移");
  const proposalHash = boundedText(raw.proposalHash, "operationCommandObservation.proposalHash", 64);
  if (!RAW_SHA256.test(proposalHash)) throw new TypeError("operationCommandObservation.proposalHash 不是 SHA-256");
  return {
    schemaVersion: OPERATION_COMMAND_OBSERVATION_SCHEMA_VERSION,
    tenant,
    proposalId,
    leaseId,
    commandId: enumValue<ObservableOperationCommandId>(raw.commandId, OBSERVABLE_OPERATION_COMMAND_IDS, "operationCommandObservation.commandId"),
    status: enumValue<OperationCommandObservationStatus>(raw.status, ["notStarted", "accepted", "applied", "failed", "unknown", "reconciled"], "operationCommandObservation.status"),
    proposalHash,
    receiptId,
    requestFingerprint,
    operationReceiptId,
    replayAllowed: false,
  };
}
