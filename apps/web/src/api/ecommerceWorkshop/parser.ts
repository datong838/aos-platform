import {
  ECOMMERCE_WORKSHOP_SCHEMA_VERSION,
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
} from "./contracts";

const SHA256 = /^sha256:[0-9a-f]{64}$/;
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
function bool(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") throw new TypeError(`${label} 必须是布尔值`);
  return value;
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
