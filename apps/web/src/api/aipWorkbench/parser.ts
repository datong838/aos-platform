import type {
  AssistContext,
  AssistEvent,
  AssistSubject,
  AssistSubjectOptionList,
  AssistThread,
  AssistThreadHistory,
  AnalystRoleQueryTemplateList,
  Blocker,
  QueryColumn,
  QueryResultRevision,
  QueryRow,
  QuerySource,
  ResourceRef,
  TaskRunControlResult,
  Tenant,
} from "./contracts";

function object(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} 必须是对象`);
  return value as Record<string, unknown>;
}
function exact(raw: Record<string, unknown>, label: string, fields: readonly string[]): void {
  const extra = Object.keys(raw).filter((key) => !fields.includes(key));
  const missing = fields.filter((key) => !(key in raw));
  if (extra.length) throw new Error(`${label} 包含额外字段：${extra.join("、")}`);
  if (missing.length) throw new Error(`${label} 缺少字段：${missing.join("、")}`);
}
function string(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} 必须是非空字符串`);
  return value;
}
function text(value: unknown, label: string): string {
  if (typeof value !== "string") throw new Error(`${label} 必须是字符串`);
  return value;
}
function nullableString(value: unknown, label: string): string | null {
  return value === null ? null : string(value, label);
}
function integer(value: unknown, label: string, min = 1): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < min) throw new Error(`${label} 非法`);
  return value;
}
function number(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(`${label} 非数字`);
  return value;
}
function boolean(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") throw new Error(`${label} 必须是布尔值`);
  return value;
}
function array(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${label} 必须是数组`);
  return value;
}
function iso(value: unknown, label: string): string {
  const result = string(value, label);
  if (Number.isNaN(Date.parse(result))) throw new Error(`${label} 非 ISO 时间`);
  return result;
}
function enumeration<T extends string>(value: unknown, label: string, values: readonly T[]): T {
  const result = string(value, label) as T;
  if (!values.includes(result)) throw new Error(`${label} 非法`);
  return result;
}
function sha(value: unknown, label: string): string {
  const result = string(value, label);
  if (!/^[0-9a-f]{64}$/.test(result)) throw new Error(`${label} 非 SHA-256`);
  return result;
}
function tenant(value: unknown, label = "tenant"): Tenant {
  const raw = object(value, label); exact(raw, label, ["orgId", "projectId"]);
  return { orgId: string(raw.orgId, `${label}.orgId`), projectId: string(raw.projectId, `${label}.projectId`) };
}
function assertTenant(actual: Tenant, expected?: Tenant): void {
  if (expected && (actual.orgId !== expected.orgId || actual.projectId !== expected.projectId)) throw new Error("tenant echo 不一致");
}
export function parseResourceRef(value: unknown, label = "ref"): ResourceRef {
  const raw = object(value, label); exact(raw, label, ["resourceType", "resourceId", "revision", "authority"]);
  return {
    resourceType: string(raw.resourceType, `${label}.resourceType`),
    resourceId: string(raw.resourceId, `${label}.resourceId`),
    revision: string(raw.revision, `${label}.revision`),
    authority: string(raw.authority, `${label}.authority`),
  };
}
function refs(value: unknown, label: string): ResourceRef[] {
  return array(value, label).map((item, index) => parseResourceRef(item, `${label}[${index}]`));
}
function blocker(value: unknown, label: string): Blocker {
  const raw = object(value, label); exact(raw, label, ["code", "message", "dependencyRef", "retryable"]);
  return {
    code: string(raw.code, `${label}.code`), message: string(raw.message, `${label}.message`),
    dependencyRef: raw.dependencyRef === null ? null : parseResourceRef(raw.dependencyRef, `${label}.dependencyRef`),
    retryable: boolean(raw.retryable, `${label}.retryable`),
  };
}
function subject(raw: Record<string, unknown>, label: string): AssistSubject {
  return {
    taskRef: parseResourceRef(raw.taskRef, `${label}.taskRef`),
    taskRunRef: parseResourceRef(raw.taskRunRef, `${label}.taskRunRef`),
    agentRunRef: parseResourceRef(raw.agentRunRef, `${label}.agentRunRef`),
    selectionRefs: refs(raw.selectionRefs, `${label}.selectionRefs`),
    cutoffAt: iso(raw.cutoffAt, `${label}.cutoffAt`),
  };
}
export function parseQueryResult(value: unknown, expectedTenant?: Tenant): QueryResultRevision {
  const raw = object(value, "QueryResultRevision");
  exact(raw, "QueryResultRevision", ["tenant", "queryId", "revision", "kind", "status", "columns", "rows", "sourceRefs", "lineageRefs", "blockers", "uncertainties", "confidence", "cutoffAt", "contentHash", "createdAt"]);
  const scope = tenant(raw.tenant); assertTenant(scope, expectedTenant);
  const columns: QueryColumn[] = array(raw.columns, "columns").map((value, index) => {
    const item = object(value, `columns[${index}]`); exact(item, `columns[${index}]`, ["key", "label", "valueType", "marking"]);
    return { key: string(item.key, "column.key"), label: string(item.label, "column.label"), valueType: enumeration(item.valueType, "column.valueType", ["string", "number", "boolean", "datetime", "object_ref"] as const), marking: nullableString(item.marking, "column.marking") };
  });
  const rows: QueryRow[] = array(raw.rows, "rows").map((value, index) => {
    const item = object(value, `rows[${index}]`); exact(item, `rows[${index}]`, ["rowId", "values"]);
    return { rowId: string(item.rowId, "row.rowId"), values: object(item.values, "row.values") };
  });
  const sources: QuerySource[] = array(raw.sourceRefs, "sourceRefs").map((value, index) => {
    const item = object(value, `sourceRefs[${index}]`); exact(item, `sourceRefs[${index}]`, ["ref", "contentHash", "cutoffAt", "freshness", "markings"]);
    return { ref: parseResourceRef(item.ref), contentHash: sha(item.contentHash, "source.contentHash"), cutoffAt: iso(item.cutoffAt, "source.cutoffAt"), freshness: enumeration(item.freshness, "source.freshness", ["fresh", "stale", "unknown"] as const), markings: array(item.markings, "source.markings").map((x) => string(x, "marking")) };
  });
  const confidenceRaw = object(raw.confidence, "confidence");
  exact(confidenceRaw, "confidence", ["status", "score", "basis"]);
  const confidenceStatus = enumeration(confidenceRaw.status, "confidence.status", ["measured", "not_applicable", "unknown"] as const);
  const confidenceScore = confidenceRaw.score === null ? null : number(confidenceRaw.score, "confidence.score");
  const confidenceBasis = array(confidenceRaw.basis, "confidence.basis").map((x) => string(x, "confidence.basis"));
  if (!confidenceBasis.length) throw new Error("confidence.basis 不得为空");
  if (confidenceStatus === "measured" && (confidenceScore === null || confidenceScore < 0 || confidenceScore > 1)) throw new Error("measured confidence.score 非法");
  if (confidenceStatus !== "measured" && confidenceScore !== null) throw new Error("未测量 confidence 不得包含 score");
  const result: QueryResultRevision = {
    tenant: scope, queryId: string(raw.queryId, "queryId"), revision: integer(raw.revision, "revision"),
    kind: enumeration(raw.kind, "kind", ["semantic", "knowledge", "metric"] as const),
    status: enumeration(raw.status, "status", ["complete", "empty", "degraded", "partial", "blocked"] as const),
    columns, rows, sourceRefs: sources, lineageRefs: refs(raw.lineageRefs, "lineageRefs"),
    blockers: array(raw.blockers, "blockers").map((item, index) => blocker(item, `blockers[${index}]`)),
    uncertainties: array(raw.uncertainties, "uncertainties").map((x) => string(x, "uncertainty")),
    confidence: { status: confidenceStatus, score: confidenceScore, basis: confidenceBasis },
    cutoffAt: iso(raw.cutoffAt, "cutoffAt"), contentHash: sha(raw.contentHash, "contentHash"), createdAt: iso(raw.createdAt, "createdAt"),
  };
  if (result.status === "blocked" && (result.rows.length || result.columns.length || result.sourceRefs.length || !result.blockers.length)) throw new Error("blocked Result revision 载荷非法");
  if (result.status === "empty" && (result.rows.length || result.blockers.length || !result.sourceRefs.length)) throw new Error("empty Result revision 载荷非法");
  if (!["blocked", "empty"].includes(result.status) && (!result.sourceRefs.length || result.blockers.length)) throw new Error("Result revision 来源或 blocker 非法");
  if (["degraded", "partial"].includes(result.status) && !result.uncertainties.length) throw new Error("partial/degraded 必须声明不确定性");
  return result;
}

export function parseAnalystRoleQueryTemplates(value: unknown, expectedTenant?: Tenant): AnalystRoleQueryTemplateList {
  const raw = object(value, "AnalystRoleQueryTemplateList");
  exact(raw, "AnalystRoleQueryTemplateList", ["tenant", "bundleRef", "contentHash", "items", "count"]);
  const scope = tenant(raw.tenant); assertTenant(scope, expectedTenant);
  const items = array(raw.items, "items").map((value, index) => {
    const item = object(value, `items[${index}]`);
    exact(item, `items[${index}]`, ["templateId", "revision", "roleId", "roleName", "queryKind", "defaultObjectType", "defaultPrompt", "requiredObjectTypes", "requiredLogicIds", "sourceDataTypes", "purpose", "policy", "readiness", "blockers"]);
    const readiness = enumeration(item.readiness, "template.readiness", ["ready", "blocked"] as const);
    const blockers = array(item.blockers, "template.blockers").map((entry, blockerIndex) => blocker(entry, `items[${index}].blockers[${blockerIndex}]`));
    if (readiness === "ready" && blockers.length) throw new Error("ready template 不得包含 blocker");
    if (readiness === "blocked" && !blockers.length) throw new Error("blocked template 必须包含 blocker");
    const queryKind = enumeration(item.queryKind, "template.queryKind", ["semantic", "knowledge", "metric"] as const);
    const defaultObjectType = item.defaultObjectType === null ? null : string(item.defaultObjectType, "template.defaultObjectType");
    if (queryKind === "semantic" && defaultObjectType === null) throw new Error("semantic template 缺少默认 Object Type");
    return {
      templateId: string(item.templateId, "template.templateId"), revision: integer(item.revision, "template.revision"),
      roleId: string(item.roleId, "template.roleId"), roleName: string(item.roleName, "template.roleName"), queryKind,
      defaultObjectType, defaultPrompt: text(item.defaultPrompt, "template.defaultPrompt"),
      requiredObjectTypes: array(item.requiredObjectTypes, "template.requiredObjectTypes").map((x) => string(x, "requiredObjectType")),
      requiredLogicIds: array(item.requiredLogicIds, "template.requiredLogicIds").map((x) => string(x, "requiredLogicId")),
      sourceDataTypes: array(item.sourceDataTypes, "template.sourceDataTypes").map((x) => string(x, "sourceDataType")),
      purpose: string(item.purpose, "template.purpose"), policy: enumeration(item.policy, "template.policy", ["canonical-read-only"] as const),
      readiness, blockers,
    };
  });
  const count = integer(raw.count, "count");
  if (count !== 6 || items.length !== 6) throw new Error("六角色模板数量漂移");
  if (new Set(items.map((item) => item.roleId)).size !== 6 || new Set(items.map((item) => item.templateId)).size !== 6) throw new Error("六角色模板身份漂移");
  return { tenant: scope, bundleRef: parseResourceRef(raw.bundleRef, "bundleRef"), contentHash: sha(raw.contentHash, "contentHash"), items, count: 6 };
}
export function parseAssistThread(value: unknown, expectedTenant?: Tenant): AssistThread {
  const raw = object(value, "AssistThread"); exact(raw, "AssistThread", ["tenant", "threadId", "subject", "status", "version", "createdBy", "createdAt"]);
  const scope = tenant(raw.tenant); assertTenant(scope, expectedTenant);
  const subjectRaw = object(raw.subject, "subject"); exact(subjectRaw, "subject", ["taskRef", "taskRunRef", "agentRunRef", "selectionRefs", "cutoffAt"]);
  return { tenant: scope, threadId: string(raw.threadId, "threadId"), subject: subject(subjectRaw, "subject"), status: enumeration(raw.status, "status", ["open", "blocked", "closed"] as const), version: integer(raw.version, "version"), createdBy: string(raw.createdBy, "createdBy"), createdAt: iso(raw.createdAt, "createdAt") };
}
export function parseAssistSubjectOptions(value: unknown, expectedTenant?: Tenant): AssistSubjectOptionList {
  const raw = object(value, "AssistSubjectOptionList"); exact(raw, "AssistSubjectOptionList", ["tenant", "items", "count"]);
  const scope = tenant(raw.tenant); assertTenant(scope, expectedTenant);
  const items = array(raw.items, "items").map((value, index) => {
    const item = object(value, `items[${index}]`);
    exact(item, `items[${index}]`, ["subject", "taskTitle", "taskDescription", "owner", "taskStatus", "runStatus", "agentStatus", "source", "updatedAt"]);
    const subjectRaw = object(item.subject, `items[${index}].subject`);
    exact(subjectRaw, `items[${index}].subject`, ["taskRef", "taskRunRef", "agentRunRef", "selectionRefs", "cutoffAt"]);
    return { subject: subject(subjectRaw, `items[${index}].subject`), taskTitle: string(item.taskTitle, "taskTitle"), taskDescription: text(item.taskDescription, "taskDescription"), owner: string(item.owner, "owner"), taskStatus: string(item.taskStatus, "taskStatus"), runStatus: string(item.runStatus, "runStatus"), agentStatus: string(item.agentStatus, "agentStatus"), source: string(item.source, "source"), updatedAt: iso(item.updatedAt, "updatedAt") };
  });
  const count = integer(raw.count, "count", 0);
  if (count !== items.length) throw new Error("AssistSubjectOptionList count 不一致");
  return { tenant: scope, items, count };
}
export function parseAssistThreadHistory(value: unknown, expectedTenant?: Tenant): AssistThreadHistory {
  const raw = object(value, "AssistThreadHistory"); exact(raw, "AssistThreadHistory", ["thread", "participants", "turns", "eventCursor"]);
  const thread = parseAssistThread(raw.thread, expectedTenant);
  const participants = array(raw.participants, "participants").map((item) => string(item, "participant"));
  const turns = array(raw.turns, "turns").map((value, index) => {
    const item = object(value, `turns[${index}]`); exact(item, `turns[${index}]`, ["turnId", "turnSequence", "message", "attachmentRefs", "referenceRefs", "createdBy", "createdAt", "events"]);
    const events = array(item.events, `turns[${index}].events`).map(parseAssistEvent);
    return { turnId: string(item.turnId, "turnId"), turnSequence: integer(item.turnSequence, "turnSequence"), message: string(item.message, "message"), attachmentRefs: refs(item.attachmentRefs, "attachmentRefs"), referenceRefs: refs(item.referenceRefs, "referenceRefs"), createdBy: string(item.createdBy, "createdBy"), createdAt: iso(item.createdAt, "createdAt"), events };
  });
  return { thread, participants, turns, eventCursor: string(raw.eventCursor, "eventCursor") };
}
export function parseTaskRunControlResult(value: unknown): TaskRunControlResult {
  const raw = object(value, "TaskRunControlResult");
  exact(raw, "TaskRunControlResult", ["task", "run"]);
  const task = object(raw.task, "task");
  exact(task, "task", ["id", "type", "title", "status", "priority", "createdBy", "createdAt", "currentPlanRevisionId", "version", "description", "goal", "selectionRef", "policyRevision", "updatedAt"]);
  const run = object(raw.run, "run");
  exact(run, "run", ["id", "taskId", "planRevisionId", "status", "startedAt", "finishedAt", "lastCheckpointId", "logicGraphId", "logicRevision", "version", "createdBy", "createdAt", "updatedAt"]);
  const taskActor = object(task.createdBy, "task.createdBy");
  exact(taskActor, "task.createdBy", ["actorType", "actorId"]);
  const runActor = object(run.createdBy, "run.createdBy");
  exact(runActor, "run.createdBy", ["actorType", "actorId"]);
  string(taskActor.actorType, "task.createdBy.actorType"); string(taskActor.actorId, "task.createdBy.actorId");
  string(runActor.actorType, "run.createdBy.actorType"); string(runActor.actorId, "run.createdBy.actorId");
  string(task.type, "task.type"); string(task.title, "task.title"); text(task.description, "task.description"); integer(task.priority, "task.priority", 0);
  iso(task.createdAt, "task.createdAt"); iso(task.updatedAt, "task.updatedAt");
  object(task.goal, "task.goal");
  if (task.selectionRef !== null) parseResourceRef(task.selectionRef, "task.selectionRef");
  nullableString(task.currentPlanRevisionId, "task.currentPlanRevisionId");
  nullableString(task.policyRevision, "task.policyRevision");
  string(run.taskId, "run.taskId"); string(run.planRevisionId, "run.planRevisionId");
  if (run.startedAt !== null) iso(run.startedAt, "run.startedAt");
  if (run.finishedAt !== null) iso(run.finishedAt, "run.finishedAt");
  nullableString(run.lastCheckpointId, "run.lastCheckpointId");
  nullableString(run.logicGraphId, "run.logicGraphId");
  if (run.logicRevision !== null) integer(run.logicRevision, "run.logicRevision");
  iso(run.createdAt, "run.createdAt"); iso(run.updatedAt, "run.updatedAt");
  return {
    task: { id: string(task.id, "task.id"), status: string(task.status, "task.status"), version: integer(task.version, "task.version") },
    run: { id: string(run.id, "run.id"), status: string(run.status, "run.status"), version: integer(run.version, "run.version") },
  };
}
function context(value: unknown): AssistContext {
  const raw = object(value, "context"); exact(raw, "context", ["tenant", "taskRef", "taskRunRef", "planRef", "agentRunRef", "agentInstanceRef", "skillRef", "logicRef", "modelRouteRef", "policyRef", "evalRef", "skillBindingRef", "capabilityBindingRefs", "selectionRefs", "knowledgeCitationRefs", "markings", "cutoffAt", "readinessBlockers", "contextHash"]);
  return { tenant: tenant(raw.tenant), ...subject(raw, "context"), planRef: parseResourceRef(raw.planRef), agentInstanceRef: parseResourceRef(raw.agentInstanceRef), skillRef: parseResourceRef(raw.skillRef), logicRef: parseResourceRef(raw.logicRef), modelRouteRef: parseResourceRef(raw.modelRouteRef), policyRef: parseResourceRef(raw.policyRef), evalRef: parseResourceRef(raw.evalRef), skillBindingRef: parseResourceRef(raw.skillBindingRef), capabilityBindingRefs: refs(raw.capabilityBindingRefs, "capabilityBindingRefs"), knowledgeCitationRefs: refs(raw.knowledgeCitationRefs, "knowledgeCitationRefs"), markings: array(raw.markings, "markings").map((x) => string(x, "marking")), readinessBlockers: array(raw.readinessBlockers, "readinessBlockers").map((x, i) => blocker(x, `readinessBlockers[${i}]`)), contextHash: sha(raw.contextHash, "contextHash") };
}
export function parseAssistEvent(value: unknown): AssistEvent {
  const raw = object(value, "AssistEvent"); exact(raw, "AssistEvent", ["eventType", "threadId", "turnId", "sequence", "occurredAt", "context", "blocker", "content", "proposalRef", "usageRefs", "lineageRefs"]);
  const result: AssistEvent = { eventType: enumeration(raw.eventType, "eventType", ["start", "context", "blocked", "delta", "proposal", "done", "error"] as const), threadId: string(raw.threadId, "threadId"), turnId: string(raw.turnId, "turnId"), sequence: integer(raw.sequence, "sequence"), occurredAt: iso(raw.occurredAt, "occurredAt"), context: raw.context === null ? null : context(raw.context), blocker: raw.blocker === null ? null : blocker(raw.blocker, "blocker"), content: nullableString(raw.content, "content"), proposalRef: raw.proposalRef === null ? null : parseResourceRef(raw.proposalRef), usageRefs: refs(raw.usageRefs, "usageRefs"), lineageRefs: refs(raw.lineageRefs, "lineageRefs") };
  const payload = { context: Boolean(result.context), blocker: Boolean(result.blocker), content: Boolean(result.content), proposal: Boolean(result.proposalRef) };
  const required = { start: [], context: ["context"], blocked: ["blocker"], delta: ["content"], proposal: ["proposal"], done: [], error: ["blocker"] }[result.eventType];
  const present = Object.entries(payload).filter(([, enabled]) => enabled).map(([name]) => name);
  if (present.sort().join() !== required.sort().join()) throw new Error(`${result.eventType} event 载荷非法`);
  if (!["done", "error"].includes(result.eventType) && (result.usageRefs.length || result.lineageRefs.length)) throw new Error("usage/lineage 仅允许终态");
  return result;
}

export function validateAssistStream(events: AssistEvent[]): AssistEvent[] {
  if (!events.length || events[0].eventType !== "start") throw new Error("Assist SSE 缺少 start");
  const { threadId, turnId } = events[0];
  events.forEach((event, index) => {
    if (event.sequence !== index + 1 || event.threadId !== threadId || event.turnId !== turnId) throw new Error("Assist SSE 序列漂移");
  });
  const terminalEvent = events[events.length - 1];
  if (events.length < 2 || !["blocked", "done", "error"].includes(terminalEvent?.eventType ?? "")) throw new Error("Assist SSE 缺少合法终态");
  return events;
}
