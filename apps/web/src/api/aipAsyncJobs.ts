import { apiGetAuthoritative } from "./client";
import { getTenant } from "./tenant";

export type AsyncJobAuthorityType = "research_job" | "query_job" | "knowledge_pipeline_run";
export type AsyncJobRef = { authority: string; authorityType: AsyncJobAuthorityType; jobId: string; version: string };
export type AsyncResourceRef = { resourceType: string; resourceId: string; revision: string | null; authority: string };
export type AsyncJobPermissions = { canCancel: boolean; canRetry: boolean; canReconcile: boolean };
export type AsyncJobProgress = { state: "unknown" | "measured" | "partial" | "complete"; completedUnits: number | null; totalUnits: number | null };
export type AsyncJobItem = {
  jobRef: AsyncJobRef; taskRef: AsyncResourceRef | null; subjectRefs: AsyncResourceRef[];
  status: string; displayStatus: string; progress: AsyncJobProgress; partialRefs: AsyncResourceRef[];
  cancelability: string; resumability: string; reconcileRequired: boolean; cancelRequested: boolean;
  checkpointRef: AsyncResourceRef | null; receiptRefs: AsyncResourceRef[]; lineageRef: string | null;
  startedAt: string | null; updatedAt: string | null; deadline: string | null; nextPollAt: string | null;
  owner: string | null; blockedReasons: string[]; permissions: AsyncJobPermissions;
};
export type AsyncJobProjection = { tenant: { orgId: string; projectId: string }; items: AsyncJobItem[]; count: number };

const AUTHORITY_TYPES = new Set(["research_job", "query_job", "knowledge_pipeline_run"]);
const STATUSES = new Set(["queued", "running", "paused", "succeeded", "complete", "empty", "partial", "degraded", "blocked", "failed", "cancelled", "unknown", "timed_out"]);
const PROGRESS = new Set(["unknown", "measured", "partial", "complete"]);

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} 必须是对象`);
  return value as Record<string, unknown>;
}
function exact(value: Record<string, unknown>, keys: string[], label: string) {
  if (Object.keys(value).sort().join("\0") !== [...keys].sort().join("\0")) throw new Error(`${label} 字段集不匹配`);
}
function text(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} 必须是非空字符串`);
  return value;
}
function nullableText(value: unknown, label: string): string | null {
  return value === null ? null : text(value, label);
}
function bool(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") throw new Error(`${label} 必须是布尔值`);
  return value;
}
function count(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) throw new Error(`${label} 必须是非负整数`);
  return value;
}
function nullableCount(value: unknown, label: string): number | null {
  return value === null ? null : count(value, label);
}
function instant(value: unknown, label: string): string | null {
  const result = nullableText(value, label);
  if (result !== null && Number.isNaN(Date.parse(result))) throw new Error(`${label} 必须是 ISO 时间`);
  return result;
}
function strings(value: unknown, label: string): string[] {
  if (!Array.isArray(value)) throw new Error(`${label} 必须是数组`);
  return value.map((item, index) => text(item, `${label}[${index}]`));
}
function ref(value: unknown, label: string): AsyncResourceRef {
  const raw = record(value, label); exact(raw, ["resourceType", "resourceId", "revision", "authority"], label);
  return { resourceType: text(raw.resourceType, `${label}.resourceType`), resourceId: text(raw.resourceId, `${label}.resourceId`), revision: nullableText(raw.revision, `${label}.revision`), authority: text(raw.authority, `${label}.authority`) };
}
function refs(value: unknown, label: string): AsyncResourceRef[] {
  if (!Array.isArray(value)) throw new Error(`${label} 必须是数组`);
  return value.map((item, index) => ref(item, `${label}[${index}]`));
}
function item(value: unknown, index: number): AsyncJobItem {
  const label = `items[${index}]`; const raw = record(value, label);
  exact(raw, ["jobRef", "taskRef", "subjectRefs", "status", "displayStatus", "progress", "partialRefs", "cancelability", "resumability", "reconcileRequired", "cancelRequested", "checkpointRef", "receiptRefs", "lineageRef", "startedAt", "updatedAt", "deadline", "nextPollAt", "owner", "blockedReasons", "permissions"], label);
  const job = record(raw.jobRef, `${label}.jobRef`); exact(job, ["authority", "authorityType", "jobId", "version"], `${label}.jobRef`);
  const authorityType = text(job.authorityType, `${label}.jobRef.authorityType`);
  if (!AUTHORITY_TYPES.has(authorityType)) throw new Error(`${label}.jobRef.authorityType 非法`);
  const status = text(raw.status, `${label}.status`); const displayStatus = text(raw.displayStatus, `${label}.displayStatus`);
  if (!STATUSES.has(status) || !STATUSES.has(displayStatus)) throw new Error(`${label} 状态非法`);
  const progress = record(raw.progress, `${label}.progress`); exact(progress, ["state", "completedUnits", "totalUnits"], `${label}.progress`);
  const progressState = text(progress.state, `${label}.progress.state`);
  if (!PROGRESS.has(progressState)) throw new Error(`${label}.progress.state 非法`);
  const permissions = record(raw.permissions, `${label}.permissions`); exact(permissions, ["canCancel", "canRetry", "canReconcile"], `${label}.permissions`);
  return {
    jobRef: { authority: text(job.authority, `${label}.jobRef.authority`), authorityType: authorityType as AsyncJobAuthorityType, jobId: text(job.jobId, `${label}.jobRef.jobId`), version: text(job.version, `${label}.jobRef.version`) },
    taskRef: raw.taskRef === null ? null : ref(raw.taskRef, `${label}.taskRef`), subjectRefs: refs(raw.subjectRefs, `${label}.subjectRefs`),
    status, displayStatus, progress: { state: progressState as AsyncJobProgress["state"], completedUnits: nullableCount(progress.completedUnits, `${label}.progress.completedUnits`), totalUnits: nullableCount(progress.totalUnits, `${label}.progress.totalUnits`) },
    partialRefs: refs(raw.partialRefs, `${label}.partialRefs`), cancelability: text(raw.cancelability, `${label}.cancelability`), resumability: text(raw.resumability, `${label}.resumability`), reconcileRequired: bool(raw.reconcileRequired, `${label}.reconcileRequired`), cancelRequested: bool(raw.cancelRequested, `${label}.cancelRequested`),
    checkpointRef: raw.checkpointRef === null ? null : ref(raw.checkpointRef, `${label}.checkpointRef`), receiptRefs: refs(raw.receiptRefs, `${label}.receiptRefs`), lineageRef: nullableText(raw.lineageRef, `${label}.lineageRef`),
    startedAt: instant(raw.startedAt, `${label}.startedAt`), updatedAt: instant(raw.updatedAt, `${label}.updatedAt`), deadline: instant(raw.deadline, `${label}.deadline`), nextPollAt: instant(raw.nextPollAt, `${label}.nextPollAt`), owner: nullableText(raw.owner, `${label}.owner`), blockedReasons: strings(raw.blockedReasons, `${label}.blockedReasons`),
    permissions: { canCancel: bool(permissions.canCancel, `${label}.permissions.canCancel`), canRetry: bool(permissions.canRetry, `${label}.permissions.canRetry`), canReconcile: bool(permissions.canReconcile, `${label}.permissions.canReconcile`) },
  };
}

export function parseAsyncJobProjection(value: unknown): AsyncJobProjection {
  const raw = record(value, "AsyncJobProjection"); exact(raw, ["tenant", "items", "count"], "AsyncJobProjection");
  const tenant = record(raw.tenant, "tenant"); exact(tenant, ["orgId", "projectId"], "tenant");
  if (!Array.isArray(raw.items)) throw new Error("items 必须是数组");
  const items = raw.items.map(item); const declared = count(raw.count, "count");
  if (declared !== items.length) throw new Error("count 与 items 长度不一致");
  return { tenant: { orgId: text(tenant.orgId, "tenant.orgId"), projectId: text(tenant.projectId, "tenant.projectId") }, items, count: declared };
}

export async function listAsyncJobs(limit = 50): Promise<AsyncJobProjection> {
  const parsed = parseAsyncJobProjection(await apiGetAuthoritative<unknown>(`/v1/aip/async-jobs?limit=${Math.max(1, Math.min(200, Math.trunc(limit)))}`));
  const tenant = getTenant();
  if (parsed.tenant.orgId !== tenant.orgId || parsed.tenant.projectId !== tenant.projectId) throw new Error("异步任务投影租户与当前会话不一致");
  return parsed;
}
