import type {
  InvestigationAnalysisType,
  InvestigationCaseListResponse,
  InvestigationCaseRevision,
  InvestigationExactRef,
  InvestigationRunControl,
  InvestigationRunLifecycle,
  InvestigationRunListResponse,
  InvestigationRunRecord,
  InvestigationRunState,
  InvestigationRunView,
  InvestigationTenant,
} from "./contracts";

const HASH = /^sha256:[0-9a-f]{64}$/;
const PURPOSE = /^[a-z][a-z0-9_.-]{1,119}$/;
const ANALYSIS_TYPES = ["initial_store_analysis", "weekly_business_review", "experience_growth", "creator_sales", "product_structure"] as const;
const CASE_LIFECYCLES = ["DRAFT", "ACTIVE", "ARCHIVED", "CLOSED"] as const;
const RUN_LIFECYCLES = ["PREPARING", "WAITING_DATA", "PORTRAIT", "DIAGNOSIS", "SOLUTION_DESIGN", "REVIEW", "COMPLETED", "FAILED"] as const;
const RUN_CONTROLS = ["RUNNING", "PAUSED", "BLOCKED", "STALE", "UNKNOWN", "RECONCILING", "CANCELLED"] as const;

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new TypeError(`${label} 必须是对象`);
  return value as Record<string, unknown>;
}
function exact(raw: Record<string, unknown>, keys: readonly string[], label: string): void {
  const unexpected = Object.keys(raw).filter((key) => !keys.includes(key));
  const missing = keys.filter((key) => !(key in raw));
  if (unexpected.length || missing.length) throw new TypeError(`${label} 字段漂移`);
}
function text(value: unknown, label: string, max = 500): string {
  if (typeof value !== "string" || !value.trim() || value !== value.trim() || value.length > max) throw new TypeError(`${label} 必须是非空有界字符串`);
  return value;
}
function integer(value: unknown, label: string, min = 0): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < min) throw new TypeError(`${label} 必须是整数`);
  return value;
}
function enumValue<T extends string>(value: unknown, choices: readonly T[], label: string): T {
  if (typeof value !== "string" || !choices.includes(value as T)) throw new TypeError(`${label} 枚举无效`);
  return value as T;
}
function timestamp(value: unknown, label: string): string {
  const result = text(value, label, 80);
  if (!/(?:Z|[+-][0-9]{2}:[0-9]{2})$/.test(result) || Number.isNaN(Date.parse(result))) throw new TypeError(`${label} 必须包含时区`);
  return result;
}
function tenant(value: unknown, expected?: InvestigationTenant): InvestigationTenant {
  const raw = record(value, "tenant"); exact(raw, ["orgId", "projectId"], "tenant");
  const result = { orgId: text(raw.orgId, "tenant.orgId", 200), projectId: text(raw.projectId, "tenant.projectId", 200) };
  if (expected && (result.orgId !== expected.orgId || result.projectId !== expected.projectId)) throw new TypeError("tenant 漂移");
  return result;
}
function ref(value: unknown, label: string, expectedType?: string): InvestigationExactRef {
  const raw = record(value, label);
  const allowed = raw.receiptId === undefined ? ["resourceType", "resourceId", "revision", "contentHash"] : ["resourceType", "resourceId", "revision", "contentHash", "receiptId"];
  exact(raw, allowed, label);
  const resourceType = text(raw.resourceType, `${label}.resourceType`, 120);
  if (expectedType && resourceType !== expectedType) throw new TypeError(`${label} 必须引用 ${expectedType}`);
  const revision = typeof raw.revision === "number" ? integer(raw.revision, `${label}.revision`, 1) : text(raw.revision, `${label}.revision`, 160);
  const contentHash = text(raw.contentHash, `${label}.contentHash`, 71);
  if (!HASH.test(contentHash)) throw new TypeError(`${label}.contentHash 非法`);
  const receiptId = raw.receiptId === undefined ? undefined : text(raw.receiptId, `${label}.receiptId`, 240);
  return { resourceType, resourceId: text(raw.resourceId, `${label}.resourceId`, 240), revision, contentHash, ...(receiptId ? { receiptId } : {}) };
}
function nullableRef(value: unknown, label: string, expectedType?: string): InvestigationExactRef | null { return value === null ? null : ref(value, label, expectedType); }
function sameTenant(left: InvestigationTenant, right: InvestigationTenant): boolean { return left.orgId === right.orgId && left.projectId === right.projectId; }

function parseCase(value: unknown, expectedTenant: InvestigationTenant): InvestigationCaseRevision {
  const raw = record(value, "case");
  exact(raw, ["schemaVersion", "tenant", "caseId", "revision", "version", "priorRef", "contentHash", "lifecycle", "analysisType", "title", "purposeCode", "channelRef", "businessEntityRef", "entityChannelBindingRef", "investigationProfileRef", "scopeRef", "schedulePolicyRef", "createdBy", "createdAt"], "case");
  if (raw.schemaVersion !== "aos.ecommerce.business-investigation-case/v1") throw new TypeError("case schemaVersion 无效");
  const revision = integer(raw.revision, "case.revision", 1); const version = integer(raw.version, "case.version", 1);
  if (revision !== version) throw new TypeError("case revision/version 漂移");
  const contentHash = text(raw.contentHash, "case.contentHash", 71); if (!HASH.test(contentHash)) throw new TypeError("case contentHash 非法");
  const purposeCode = text(raw.purposeCode, "case.purposeCode", 120); if (!PURPOSE.test(purposeCode)) throw new TypeError("case purposeCode 非法");
  const priorRef = nullableRef(raw.priorRef, "case.priorRef", "BusinessInvestigationCaseRevision");
  const caseId = text(raw.caseId, "case.caseId", 200);
  if ((revision === 1 && priorRef !== null) || (revision > 1 && (!priorRef || priorRef.resourceId !== caseId || priorRef.revision !== revision - 1))) throw new TypeError("case priorRef 漂移");
  return {
    schemaVersion: "aos.ecommerce.business-investigation-case/v1", tenant: tenant(raw.tenant, expectedTenant), caseId, revision, version, priorRef, contentHash,
    lifecycle: enumValue(raw.lifecycle, CASE_LIFECYCLES, "case.lifecycle"), analysisType: enumValue<InvestigationAnalysisType>(raw.analysisType, ANALYSIS_TYPES, "case.analysisType"),
    title: text(raw.title, "case.title"), purposeCode,
    channelRef: ref(raw.channelRef, "case.channelRef", "ChannelRevision"), businessEntityRef: ref(raw.businessEntityRef, "case.businessEntityRef", "BusinessEntityRevision"),
    entityChannelBindingRef: ref(raw.entityChannelBindingRef, "case.entityChannelBindingRef", "BusinessEntityChannelBindingRevision"), investigationProfileRef: ref(raw.investigationProfileRef, "case.investigationProfileRef", "InvestigationProfileRevision"), scopeRef: ref(raw.scopeRef, "case.scopeRef", "InvestigationScopeRevision"), schedulePolicyRef: nullableRef(raw.schedulePolicyRef, "case.schedulePolicyRef", "SchedulePolicyRevision"),
    createdBy: text(raw.createdBy, "case.createdBy", 200), createdAt: timestamp(raw.createdAt, "case.createdAt"),
  };
}

function parseRunRecord(value: unknown, expectedTenant: InvestigationTenant, expectedCaseId: string): InvestigationRunRecord {
  const raw = record(value, "run.authority"); exact(raw, ["schemaVersion", "tenant", "runId", "version", "contentHash", "caseRef", "analysisType", "triggerKind", "triggerKey", "lifecycle", "control", "createdBy", "createdAt"], "run.authority");
  if (raw.schemaVersion !== "aos.ecommerce.business-investigation-run/v1" || raw.version !== 1 || raw.lifecycle !== "PREPARING" || raw.control !== "RUNNING") throw new TypeError("run authority 合同漂移");
  const contentHash = text(raw.contentHash, "run.contentHash", 71); if (!HASH.test(contentHash)) throw new TypeError("run contentHash 非法");
  const caseRef = ref(raw.caseRef, "run.caseRef", "BusinessInvestigationCaseRevision"); if (caseRef.resourceId !== expectedCaseId) throw new TypeError("run caseRef 漂移");
  return { schemaVersion: "aos.ecommerce.business-investigation-run/v1", tenant: tenant(raw.tenant, expectedTenant), runId: text(raw.runId, "run.runId", 200), version: 1, contentHash, caseRef, analysisType: enumValue(raw.analysisType, ANALYSIS_TYPES, "run.analysisType"), triggerKind: enumValue(raw.triggerKind, ["manual", "scheduled", "topic", "recovery"] as const, "run.triggerKind"), triggerKey: text(raw.triggerKey, "run.triggerKey", 240), lifecycle: "PREPARING", control: "RUNNING", createdBy: text(raw.createdBy, "run.createdBy", 200), createdAt: timestamp(raw.createdAt, "run.createdAt") };
}

function parseRunState(value: unknown, expectedTenant: InvestigationTenant, runId: string): InvestigationRunState {
  const raw = record(value, "run.state"); exact(raw, ["schemaVersion", "tenant", "runId", "version", "priorRef", "lifecycle", "control", "eventSequence", "contentHash", "pendingRequirementRef", "uncertainCommand", "createdBy", "createdAt"], "run.state");
  if (raw.schemaVersion !== "aos.ecommerce.business-investigation-run-state/v1" || raw.runId !== runId) throw new TypeError("run state identity 漂移");
  const version = integer(raw.version, "run.state.version", 1); if (raw.eventSequence !== version) throw new TypeError("run state eventSequence 漂移");
  const contentHash = text(raw.contentHash, "run.state.contentHash", 71); if (!HASH.test(contentHash)) throw new TypeError("run state contentHash 非法");
  const priorRef = nullableRef(raw.priorRef, "run.state.priorRef", "BusinessInvestigationRunStateRevision");
  if ((version === 1 && priorRef !== null) || (version > 1 && (!priorRef || priorRef.resourceId !== runId || priorRef.revision !== version - 1))) throw new TypeError("run state priorRef 漂移");
  const uncertainRaw = raw.uncertainCommand === null ? null : record(raw.uncertainCommand, "run.state.uncertainCommand");
  let uncertainCommand: InvestigationRunState["uncertainCommand"] = null;
  if (uncertainRaw) { exact(uncertainRaw, ["commandId", "operation", "requestHash"], "run.state.uncertainCommand"); const requestHash = text(uncertainRaw.requestHash, "run.state.uncertainCommand.requestHash", 71); if (!HASH.test(requestHash)) throw new TypeError("uncertain requestHash 非法"); uncertainCommand = { commandId: text(uncertainRaw.commandId, "run.state.uncertainCommand.commandId", 200), operation: text(uncertainRaw.operation, "run.state.uncertainCommand.operation", 120), requestHash }; }
  const lifecycle = enumValue<InvestigationRunLifecycle>(raw.lifecycle, RUN_LIFECYCLES, "run.state.lifecycle");
  const control = enumValue<InvestigationRunControl>(raw.control, RUN_CONTROLS, "run.state.control");
  if (["UNKNOWN", "RECONCILING"].includes(control) !== Boolean(uncertainCommand)) throw new TypeError("run uncertain 状态漂移");
  return { schemaVersion: "aos.ecommerce.business-investigation-run-state/v1", tenant: tenant(raw.tenant, expectedTenant), runId, version, priorRef, lifecycle, control, eventSequence: version, contentHash, pendingRequirementRef: nullableRef(raw.pendingRequirementRef, "run.state.pendingRequirementRef", "DataRequirementRevision"), uncertainCommand, createdBy: text(raw.createdBy, "run.state.createdBy", 200), createdAt: timestamp(raw.createdAt, "run.state.createdAt") };
}

function parseRun(value: unknown, expectedTenant: InvestigationTenant, caseId: string): InvestigationRunView {
  const raw = record(value, "run"); exact(raw, ["authority", "state"], "run");
  const authority = parseRunRecord(raw.authority, expectedTenant, caseId); const state = parseRunState(raw.state, expectedTenant, authority.runId);
  if (!sameTenant(authority.tenant, state.tenant)) throw new TypeError("run tenant 漂移");
  return { authority, state };
}

export function parseInvestigationCaseList(value: unknown, expectedTenant?: InvestigationTenant): InvestigationCaseListResponse {
  const raw = record(value, "caseList"); exact(raw, ["tenant", "items", "count"], "caseList"); const responseTenant = tenant(raw.tenant, expectedTenant);
  if (!Array.isArray(raw.items) || raw.items.length > 200) throw new TypeError("caseList.items 非法");
  const items = raw.items.map((item) => parseCase(item, responseTenant)); const count = integer(raw.count, "caseList.count");
  if (count !== items.length || new Set(items.map((item) => item.caseId)).size !== items.length) throw new TypeError("caseList count 或 identity 不守恒");
  return { tenant: responseTenant, items, count };
}

export function parseInvestigationRunList(value: unknown, caseId: string, expectedTenant?: InvestigationTenant): InvestigationRunListResponse {
  const raw = record(value, "runList"); exact(raw, ["tenant", "items", "count"], "runList"); const responseTenant = tenant(raw.tenant, expectedTenant);
  if (!Array.isArray(raw.items) || raw.items.length > 200) throw new TypeError("runList.items 非法");
  const items = raw.items.map((item) => parseRun(item, responseTenant, caseId)); const count = integer(raw.count, "runList.count");
  if (count !== items.length || new Set(items.map((item) => item.authority.runId)).size !== items.length) throw new TypeError("runList count 或 identity 不守恒");
  return { tenant: responseTenant, items, count };
}
