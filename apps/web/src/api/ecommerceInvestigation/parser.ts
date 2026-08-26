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
  InvestigationRunStateCommandResponse,
  InvestigationRunView,
  InvestigationTenant,
  InvestigationWorkbenchView,
  InvestigationRuntimeProjection,
  InvestigationResourceRef,
  InvestigationCurrentWorkspace,
} from "./contracts";

const HASH = /^sha256:[0-9a-f]{64}$/;
const PURPOSE = /^[a-z][a-z0-9_.-]{1,119}$/;
const ANALYSIS_TYPES = ["initial_store_analysis", "weekly_business_review", "experience_growth", "creator_sales", "product_structure"] as const;
const CASE_LIFECYCLES = ["DRAFT", "ACTIVE", "ARCHIVED", "CLOSED"] as const;
const RUN_LIFECYCLES = ["PREPARING", "WAITING_DATA", "PORTRAIT", "DIAGNOSIS", "SOLUTION_DESIGN", "REVIEW", "COMPLETED", "FAILED"] as const;
const RUN_CONTROLS = ["RUNNING", "PAUSED", "BLOCKED", "STALE", "UNKNOWN", "RECONCILING", "CANCELLED"] as const;
const STAGE_IDS = ["portrait", "diagnosis", "solution-design"] as const;
const STAGE_TITLES = ["经营画像", "问题与机会", "方案设计"] as const;
const STAGE_STATUSES = ["not_started", "running", "waiting_data", "waiting_human", "blocked", "review", "accepted", "returned", "completed"] as const;
const TASK_RUN_STATUSES = ["queued", "running", "pausing", "paused", "succeeded", "failed", "cancelled", "unknown"] as const;
const LEGACY_ARTIFACT_TYPES = ["BusinessDossierRevision", "ProblemMapRevision", "SolutionSetRevision", "DecisionReportRevision"] as const;
const ARTIFACT_TYPES = ["BusinessDossierRevision", "ProblemMapRevision", "OpportunityMapRevision", "SolutionPortfolioRevision"] as const;
const TIMELINE_TYPES = ["case_revision", "run_created", "state_revision", "artifact_bound"] as const;
const RUN_COMMANDS = ["PAUSE_RUN", "RESUME_RUN", "CANCEL_RUN"] as const;

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
function resourceRef(value: unknown, label: string): InvestigationResourceRef {
  const raw = record(value, label); exact(raw, ["resourceType", "resourceId", "revision", "authority"], label);
  return { resourceType: text(raw.resourceType, `${label}.resourceType`, 120), resourceId: text(raw.resourceId, `${label}.resourceId`, 240), revision: raw.revision === null ? null : text(raw.revision, `${label}.revision`, 160), authority: text(raw.authority, `${label}.authority`, 200) };
}
function resourceRefs(value: unknown, label: string, max = 200): InvestigationResourceRef[] {
  if (!Array.isArray(value) || value.length > max) throw new TypeError(`${label} 非法`);
  const result = value.map((item, index) => resourceRef(item, `${label}[${index}]`));
  if (new Set(result.map((item) => JSON.stringify(item))).size !== result.length) throw new TypeError(`${label} 必须唯一`);
  return result;
}
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

export function parseInvestigationRunStateCommandResponse(
  value: unknown,
  runId: string,
  expectedTenant?: InvestigationTenant,
): InvestigationRunStateCommandResponse {
  const raw = record(value, "runCommand");
  exact(raw, ["tenant", "authority", "replayed"], "runCommand");
  const responseTenant = tenant(raw.tenant, expectedTenant);
  if (typeof raw.replayed !== "boolean") throw new TypeError("runCommand.replayed 必须是布尔值");
  return {
    tenant: responseTenant,
    authority: parseRunState(raw.authority, responseTenant, runId),
    replayed: raw.replayed,
  };
}

function nullableText(value: unknown, label: string, max = 240): string | null { return value === null ? null : text(value, label, max); }

function parseRuntime(value: unknown): InvestigationRuntimeProjection {
  const raw = record(value, "view.runtime"); exact(raw, ["bindingStatus", "taskId", "planRef", "taskRunRef", "taskRunStatus", "checkpoint", "stages", "completed", "total", "currentStageId"], "view.runtime");
  const bindingStatus = enumValue(raw.bindingStatus, ["unbound", "task_pending", "bound"] as const, "view.runtime.bindingStatus");
  const taskId = nullableText(raw.taskId, "view.runtime.taskId", 200); const planRef = nullableRef(raw.planRef, "view.runtime.planRef", "PlanRevision");
  let taskRunRef: InvestigationRuntimeProjection["taskRunRef"] = null;
  if (raw.taskRunRef !== null) { const item = record(raw.taskRunRef, "view.runtime.taskRunRef"); exact(item, ["resourceType", "resourceId", "version"], "view.runtime.taskRunRef"); if (item.resourceType !== "TaskRun") throw new TypeError("view.runtime.taskRunRef 类型漂移"); taskRunRef = { resourceType: "TaskRun", resourceId: text(item.resourceId, "view.runtime.taskRunRef.resourceId", 200), version: integer(item.version, "view.runtime.taskRunRef.version", 1) }; }
  const taskRunStatus = raw.taskRunStatus === null ? null : enumValue(raw.taskRunStatus, TASK_RUN_STATUSES, "view.runtime.taskRunStatus");
  let checkpoint: InvestigationRuntimeProjection["checkpoint"] = null;
  if (raw.checkpoint !== null) { const item = record(raw.checkpoint, "view.runtime.checkpoint"); exact(item, ["checkpointId", "sequence", "stepKey", "stateHash", "createdAt"], "view.runtime.checkpoint"); const stateHash = text(item.stateHash, "view.runtime.checkpoint.stateHash", 64); if (!/^[0-9a-f]{64}$/.test(stateHash)) throw new TypeError("Checkpoint stateHash 非法"); checkpoint = { checkpointId: text(item.checkpointId, "view.runtime.checkpoint.checkpointId", 200), sequence: integer(item.sequence, "view.runtime.checkpoint.sequence", 1), stepKey: nullableText(item.stepKey, "view.runtime.checkpoint.stepKey", 200), stateHash, createdAt: timestamp(item.createdAt, "view.runtime.checkpoint.createdAt") }; }
  if (!Array.isArray(raw.stages) || raw.stages.length !== 3) throw new TypeError("StageRail 数量漂移");
  const stages = raw.stages.map((value, index) => { const item = record(value, `view.runtime.stages[${index}]`); exact(item, ["stageId", "title", "status", "stepRunId", "attempt"], `view.runtime.stages[${index}]`); const stageId = enumValue(item.stageId, STAGE_IDS, "stageId"); const title = text(item.title, "stage.title", 120); if (stageId !== STAGE_IDS[index] || title !== STAGE_TITLES[index]) throw new TypeError("StageRail 顺序或标题漂移"); const stepRunId = nullableText(item.stepRunId, "stage.stepRunId", 200); const attempt = item.attempt === null ? null : integer(item.attempt, "stage.attempt", 1); if ((stepRunId === null) !== (attempt === null)) throw new TypeError("Stage StepRun identity 漂移"); return { stageId, title, status: enumValue(item.status, STAGE_STATUSES, "stage.status"), stepRunId, attempt }; });
  const completed = integer(raw.completed, "view.runtime.completed"); if (raw.total !== 3 || completed !== stages.filter((item) => item.status === "completed").length) throw new TypeError("StageRail 进度不守恒");
  const currentStageId = raw.currentStageId === null ? null : enumValue(raw.currentStageId, STAGE_IDS, "view.runtime.currentStageId");
  if (bindingStatus === "unbound" && [taskId, planRef, taskRunRef, taskRunStatus, checkpoint].some(Boolean)) throw new TypeError("unbound runtime 泄露旧 lineage");
  if (bindingStatus === "task_pending" && (!taskId || !planRef || taskRunRef || taskRunStatus || checkpoint)) throw new TypeError("task_pending runtime 漂移");
  if (bindingStatus === "bound" && (!taskId || !planRef || !taskRunRef || !taskRunStatus)) throw new TypeError("bound runtime 不完整");
  return { bindingStatus, taskId, planRef, taskRunRef, taskRunStatus, checkpoint, stages, completed, total: 3, currentStageId };
}

function parseCurrentWorkspace(value: unknown): InvestigationCurrentWorkspace {
  const raw = record(value, "view.currentWorkspace");
  exact(raw, ["stageId", "title", "question", "status", "responsibilitySlotIds", "assigneeRefs", "inputRefs", "outputRefs", "areas", "nonClaims"], "view.currentWorkspace");
  const stageId = raw.stageId === null ? null : enumValue(raw.stageId, STAGE_IDS, "currentWorkspace.stageId");
  const title = text(raw.title, "currentWorkspace.title", 120); const question = text(raw.question, "currentWorkspace.question", 500);
  const status = enumValue(raw.status, ["unbound", "task_pending", "not_started", "running", "blocked", "completed"] as const, "currentWorkspace.status");
  if (!Array.isArray(raw.responsibilitySlotIds) || raw.responsibilitySlotIds.length > 50) throw new TypeError("responsibilitySlotIds 非法");
  const responsibilitySlotIds = raw.responsibilitySlotIds.map((item, index) => text(item, `responsibilitySlotIds[${index}]`, 200));
  if (new Set(responsibilitySlotIds).size !== responsibilitySlotIds.length) throw new TypeError("responsibilitySlotIds 必须唯一");
  const assigneeRefs = resourceRefs(raw.assigneeRefs, "currentWorkspace.assigneeRefs", 50); const inputRefs = resourceRefs(raw.inputRefs, "currentWorkspace.inputRefs"); const outputRefs = resourceRefs(raw.outputRefs, "currentWorkspace.outputRefs");
  if (!Array.isArray(raw.areas) || raw.areas.length !== 4) throw new TypeError("currentWorkspace.areas 数量漂移");
  const expectedAreas = ["known", "unknown", "assumption", "counter_evidence"] as const;
  const areas = raw.areas.map((value, index) => { const item = record(value, `currentWorkspace.areas[${index}]`); exact(item, ["area", "title", "status", "summary", "resourceRefs", "exactRefs"], `currentWorkspace.areas[${index}]`); const area = enumValue(item.area, expectedAreas, "contribution.area"); if (area !== expectedAreas[index]) throw new TypeError("contribution area 顺序漂移"); if (!Array.isArray(item.exactRefs) || item.exactRefs.length > 20) throw new TypeError("contribution exactRefs 非法"); return { area, title: text(item.title, "contribution.title", 120), status: enumValue(item.status, ["reference_only", "present", "unknown"] as const, "contribution.status"), summary: text(item.summary, "contribution.summary", 500), resourceRefs: resourceRefs(item.resourceRefs, "contribution.resourceRefs"), exactRefs: item.exactRefs.map((candidate, refIndex) => ref(candidate, `contribution.exactRefs[${refIndex}]`)) }; });
  if (!Array.isArray(raw.nonClaims) || raw.nonClaims.length < 3 || raw.nonClaims.length > 10) throw new TypeError("currentWorkspace.nonClaims 非法"); const nonClaims = raw.nonClaims.map((item, index) => text(item, `nonClaims[${index}]`, 500));
  if (stageId === null && (status !== "unbound" || responsibilitySlotIds.length || assigneeRefs.length || inputRefs.length || outputRefs.length)) throw new TypeError("unbound currentWorkspace 泄露旧阶段数据");
  return { stageId, title, question, status, responsibilitySlotIds, assigneeRefs, inputRefs, outputRefs, areas, nonClaims };
}

export function parseInvestigationWorkbenchView(value: unknown, runId: string, expectedTenant?: InvestigationTenant): InvestigationWorkbenchView {
  const raw = record(value, "view");
  const schemaVersion = enumValue(raw.schemaVersion, ["aos.ecommerce.business-investigation-workbench-view/v3", "aos.ecommerce.business-investigation-workbench-view/v4", "aos.ecommerce.business-investigation-workbench-view/v5"] as const, "Workbench schemaVersion");
  const canonicalDrilldown = schemaVersion.endsWith("/v4") || schemaVersion.endsWith("/v5");
  const v5 = schemaVersion.endsWith("/v5");
  exact(raw, ["schemaVersion", "tenant", "projectionHash", "sourceWatermark", "observedAt", "caseRef", "runRef", "stateRef", "caseEnvelope", "lifecycle", "control", "pendingRequirementRef", "uncertainCommand", "runtime", "currentWorkspace", "artifacts", ...(canonicalDrilldown ? ["evidence", "timeline"] : []), ...(v5 ? ["commandProjection"] : [])], "view");
  const responseTenant = tenant(raw.tenant, expectedTenant);
  const projectionHash = text(raw.projectionHash, "view.projectionHash", 71); if (!HASH.test(projectionHash)) throw new TypeError("projectionHash 非法");
  const watermarkRaw = record(raw.sourceWatermark, "view.sourceWatermark"); exact(watermarkRaw, ["caseRevision", "runVersion", "stateVersion", "bindingHashes", "runtimeHash", "contentHash"], "view.sourceWatermark"); if (!Array.isArray(watermarkRaw.bindingHashes) || watermarkRaw.bindingHashes.some((item) => typeof item !== "string" || !HASH.test(item))) throw new TypeError("bindingHashes 非法"); const bindingHashes = watermarkRaw.bindingHashes as string[]; if (JSON.stringify(bindingHashes) !== JSON.stringify([...new Set(bindingHashes)].sort())) throw new TypeError("bindingHashes 非 canonical"); const runtimeHash = watermarkRaw.runtimeHash === null ? null : text(watermarkRaw.runtimeHash, "runtimeHash", 71); const watermarkHash = text(watermarkRaw.contentHash, "watermark.contentHash", 71); if ((runtimeHash && !HASH.test(runtimeHash)) || !HASH.test(watermarkHash)) throw new TypeError("watermark hash 非法");
  const caseRef = ref(raw.caseRef, "view.caseRef", "BusinessInvestigationCaseRevision"); const runRef = ref(raw.runRef, "view.runRef", "BusinessInvestigationRun"); const stateRef = ref(raw.stateRef, "view.stateRef", "BusinessInvestigationRunStateRevision"); if (runRef.resourceId !== runId || stateRef.resourceId !== runId) throw new TypeError("Workbench Run identity 漂移");
  const envelopeRaw = record(raw.caseEnvelope, "view.caseEnvelope"); exact(envelopeRaw, ["title", "analysisType", "lifecycle", "channelRef", "businessEntityRef", "investigationProfileRef", "scopeRef", "schedulePolicyRef", "createdBy", "createdAt"], "view.caseEnvelope");
  const caseEnvelope = { title: text(envelopeRaw.title, "caseEnvelope.title"), analysisType: enumValue(envelopeRaw.analysisType, ANALYSIS_TYPES, "caseEnvelope.analysisType"), lifecycle: enumValue(envelopeRaw.lifecycle, CASE_LIFECYCLES, "caseEnvelope.lifecycle"), channelRef: ref(envelopeRaw.channelRef, "caseEnvelope.channelRef", "ChannelRevision"), businessEntityRef: ref(envelopeRaw.businessEntityRef, "caseEnvelope.businessEntityRef", "BusinessEntityRevision"), investigationProfileRef: ref(envelopeRaw.investigationProfileRef, "caseEnvelope.investigationProfileRef", "InvestigationProfileRevision"), scopeRef: ref(envelopeRaw.scopeRef, "caseEnvelope.scopeRef", "InvestigationScopeRevision"), schedulePolicyRef: nullableRef(envelopeRaw.schedulePolicyRef, "caseEnvelope.schedulePolicyRef", "SchedulePolicyRevision"), createdBy: text(envelopeRaw.createdBy, "caseEnvelope.createdBy", 200), createdAt: timestamp(envelopeRaw.createdAt, "caseEnvelope.createdAt") };
  if (caseRef.resourceId === "" || caseRef.revision !== integer(watermarkRaw.caseRevision, "watermark.caseRevision", 1) || runRef.revision !== integer(watermarkRaw.runVersion, "watermark.runVersion", 1) || stateRef.revision !== integer(watermarkRaw.stateVersion, "watermark.stateVersion", 1)) throw new TypeError("Workbench watermark 漂移");
  const uncertainRaw = raw.uncertainCommand === null ? null : record(raw.uncertainCommand, "view.uncertainCommand"); let uncertainCommand: InvestigationWorkbenchView["uncertainCommand"] = null; if (uncertainRaw) { exact(uncertainRaw, ["commandId", "operation", "requestHash"], "view.uncertainCommand"); const requestHash = text(uncertainRaw.requestHash, "uncertainCommand.requestHash", 71); if (!HASH.test(requestHash)) throw new TypeError("uncertain requestHash 非法"); uncertainCommand = { commandId: text(uncertainRaw.commandId, "uncertainCommand.commandId", 200), operation: text(uncertainRaw.operation, "uncertainCommand.operation", 120), requestHash }; }
  const artifactTypes = canonicalDrilldown ? ARTIFACT_TYPES : LEGACY_ARTIFACT_TYPES;
  if (!Array.isArray(raw.artifacts) || raw.artifacts.length !== 4) throw new TypeError("artifact slots 数量漂移"); const artifacts = raw.artifacts.map((value, index) => { const item = record(value, `artifacts[${index}]`); exact(item, ["artifactType", "status", "artifactRef", "bindingId", "bindingHash", "selectionRevision", "dataCutoff", "lineageRef"], `artifacts[${index}]`); const artifactType = enumValue(item.artifactType, artifactTypes, "artifactType"); if (artifactType !== artifactTypes[index]) throw new TypeError("artifact slots 顺序漂移"); const status = enumValue(item.status, ["bound", "missing"] as const, "artifact.status"); const artifactRef = nullableRef(item.artifactRef, "artifactRef", artifactType); const bindingId = nullableText(item.bindingId, "bindingId", 200); const bindingHash = item.bindingHash === null ? null : text(item.bindingHash, "bindingHash", 71); const selectionRevision = item.selectionRevision === null ? null : integer(item.selectionRevision, "selectionRevision", 1); const dataCutoff = item.dataCutoff === null ? null : timestamp(item.dataCutoff, "dataCutoff"); const lineageRef = nullableRef(item.lineageRef, "lineageRef"); if ((bindingHash && !HASH.test(bindingHash)) || (status === "missing" && [artifactRef, bindingId, bindingHash, selectionRevision, dataCutoff, lineageRef].some(Boolean)) || (status === "bound" && [artifactRef, bindingId, bindingHash, selectionRevision, dataCutoff, lineageRef].some((item) => item === null))) throw new TypeError("artifact slot 状态漂移"); return { artifactType, status, artifactRef, bindingId, bindingHash, selectionRevision, dataCutoff, lineageRef }; });
  let evidence: InvestigationWorkbenchView["evidence"] = { status: "missing", exactRefs: [], locatorRefs: [] };
  let timeline: InvestigationWorkbenchView["timeline"] = [];
  if (canonicalDrilldown) {
    const evidenceRaw = record(raw.evidence, "view.evidence"); exact(evidenceRaw, ["status", "exactRefs", "locatorRefs"], "view.evidence");
    if (!Array.isArray(evidenceRaw.exactRefs) || evidenceRaw.exactRefs.length > 200) throw new TypeError("evidence.exactRefs 非法");
    const exactRefs = evidenceRaw.exactRefs.map((item, index) => ref(item, `evidence.exactRefs[${index}]`)); const locatorRefs = resourceRefs(evidenceRaw.locatorRefs, "evidence.locatorRefs");
    const evidenceStatus = enumValue(evidenceRaw.status, ["exact", "missing"] as const, "evidence.status");
    if ((evidenceStatus === "exact") !== Boolean(exactRefs.length) || new Set(exactRefs.map((item) => JSON.stringify(item))).size !== exactRefs.length) throw new TypeError("evidence status 或 exact refs 漂移");
    evidence = { status: evidenceStatus, exactRefs, locatorRefs };
    if (!Array.isArray(raw.timeline) || raw.timeline.length < 3 || raw.timeline.length > 20) throw new TypeError("timeline 数量非法");
    timeline = raw.timeline.map((value, index) => { const item = record(value, `timeline[${index}]`); exact(item, ["eventId", "eventType", "title", "occurredAt", "exactRef", "relatedRef"], `timeline[${index}]`); return { eventId: text(item.eventId, "timeline.eventId", 300), eventType: enumValue(item.eventType, TIMELINE_TYPES, "timeline.eventType"), title: text(item.title, "timeline.title", 200), occurredAt: timestamp(item.occurredAt, "timeline.occurredAt"), exactRef: ref(item.exactRef, "timeline.exactRef"), relatedRef: nullableRef(item.relatedRef, "timeline.relatedRef") }; });
    const ordering = timeline.map((item) => [Date.parse(item.occurredAt), item.eventId] as const); const sorted = [...ordering].sort((left, right) => left[0] - right[0] || left[1].localeCompare(right[1])); if (JSON.stringify(ordering) !== JSON.stringify(sorted) || new Set(timeline.map((item) => item.eventId)).size !== timeline.length) throw new TypeError("timeline 非 canonical");
  }
  const lifecycle = enumValue(raw.lifecycle, RUN_LIFECYCLES, "view.lifecycle");
  const control = enumValue(raw.control, RUN_CONTROLS, "view.control");
  let commandProjection: InvestigationWorkbenchView["commandProjection"] = null;
  if (v5) {
    const commandRaw = record(raw.commandProjection, "view.commandProjection");
    exact(commandRaw, ["expectedStateVersion", "allowedCommands", "externalEffectsAllowed"], "view.commandProjection");
    if (!Array.isArray(commandRaw.allowedCommands) || commandRaw.allowedCommands.length > 2) throw new TypeError("allowedCommands 非法");
    const allowedCommands = commandRaw.allowedCommands.map((item) => enumValue(item, RUN_COMMANDS, "allowedCommand"));
    const canonical = RUN_COMMANDS.filter((item) => allowedCommands.includes(item));
    if (new Set(allowedCommands).size !== allowedCommands.length || JSON.stringify(allowedCommands) !== JSON.stringify(canonical)) throw new TypeError("allowedCommands 非 canonical");
    const expectedStateVersion = integer(commandRaw.expectedStateVersion, "commandProjection.expectedStateVersion", 1);
    if (expectedStateVersion !== stateRef.revision || commandRaw.externalEffectsAllowed !== false) throw new TypeError("commandProjection authority 漂移");
    const terminal = lifecycle === "COMPLETED" || lifecycle === "FAILED";
    const expectedCommands = terminal ? [] : control === "RUNNING" ? ["PAUSE_RUN", "CANCEL_RUN"] : control === "PAUSED" ? ["RESUME_RUN", "CANCEL_RUN"] : [];
    if (JSON.stringify(allowedCommands) !== JSON.stringify(expectedCommands)) throw new TypeError("allowedCommands 与 Run 状态不一致");
    commandProjection = { expectedStateVersion, allowedCommands, externalEffectsAllowed: false };
  }
  return { schemaVersion, drilldownVersion: canonicalDrilldown ? "canonical-v4" : "legacy-v3", tenant: responseTenant, projectionHash, sourceWatermark: { caseRevision: integer(watermarkRaw.caseRevision, "caseRevision", 1), runVersion: integer(watermarkRaw.runVersion, "runVersion", 1), stateVersion: integer(watermarkRaw.stateVersion, "stateVersion", 1), bindingHashes, runtimeHash, contentHash: watermarkHash }, observedAt: timestamp(raw.observedAt, "view.observedAt"), caseRef, runRef, stateRef, caseEnvelope, lifecycle, control, pendingRequirementRef: nullableRef(raw.pendingRequirementRef, "view.pendingRequirementRef", "DataRequirementRevision"), uncertainCommand, runtime: parseRuntime(raw.runtime), currentWorkspace: parseCurrentWorkspace(raw.currentWorkspace), artifacts, evidence, timeline, commandProjection };
}
