import type {
  AssistContext,
  AssistEvent,
  AssistSubject,
  AssistThread,
  Blocker,
  QueryColumn,
  QueryResultRevision,
  QueryRow,
  QuerySource,
  ResourceRef,
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
function nullableString(value: unknown, label: string): string | null {
  return value === null ? null : string(value, label);
}
function integer(value: unknown, label: string, min = 1): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < min) throw new Error(`${label} 非法`);
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
  exact(raw, "QueryResultRevision", ["tenant", "queryId", "revision", "kind", "status", "columns", "rows", "sourceRefs", "lineageRefs", "blockers", "uncertainties", "cutoffAt", "contentHash", "createdAt"]);
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
  const result: QueryResultRevision = {
    tenant: scope, queryId: string(raw.queryId, "queryId"), revision: integer(raw.revision, "revision"),
    kind: enumeration(raw.kind, "kind", ["semantic", "knowledge", "metric"] as const),
    status: enumeration(raw.status, "status", ["complete", "empty", "degraded", "partial", "blocked"] as const),
    columns, rows, sourceRefs: sources, lineageRefs: refs(raw.lineageRefs, "lineageRefs"),
    blockers: array(raw.blockers, "blockers").map((item, index) => blocker(item, `blockers[${index}]`)),
    uncertainties: array(raw.uncertainties, "uncertainties").map((x) => string(x, "uncertainty")),
    cutoffAt: iso(raw.cutoffAt, "cutoffAt"), contentHash: sha(raw.contentHash, "contentHash"), createdAt: iso(raw.createdAt, "createdAt"),
  };
  if (result.status === "blocked" && (result.rows.length || result.columns.length || result.sourceRefs.length || !result.blockers.length)) throw new Error("blocked Result revision 载荷非法");
  if (result.status === "empty" && (result.rows.length || result.blockers.length || !result.sourceRefs.length)) throw new Error("empty Result revision 载荷非法");
  if (!["blocked", "empty"].includes(result.status) && (!result.sourceRefs.length || result.blockers.length)) throw new Error("Result revision 来源或 blocker 非法");
  if (["degraded", "partial"].includes(result.status) && !result.uncertainties.length) throw new Error("partial/degraded 必须声明不确定性");
  return result;
}
export function parseAssistThread(value: unknown, expectedTenant?: Tenant): AssistThread {
  const raw = object(value, "AssistThread"); exact(raw, "AssistThread", ["tenant", "threadId", "subject", "status", "version", "createdBy", "createdAt"]);
  const scope = tenant(raw.tenant); assertTenant(scope, expectedTenant);
  const subjectRaw = object(raw.subject, "subject"); exact(subjectRaw, "subject", ["taskRef", "taskRunRef", "agentRunRef", "selectionRefs", "cutoffAt"]);
  return { tenant: scope, threadId: string(raw.threadId, "threadId"), subject: subject(subjectRaw, "subject"), status: enumeration(raw.status, "status", ["open", "blocked", "closed"] as const), version: integer(raw.version, "version"), createdBy: string(raw.createdBy, "createdBy"), createdAt: iso(raw.createdAt, "createdAt") };
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
  if (events.length < 2 || !["blocked", "done", "error"].includes(events.at(-1)?.eventType ?? "")) throw new Error("Assist SSE 缺少合法终态");
  return events;
}
