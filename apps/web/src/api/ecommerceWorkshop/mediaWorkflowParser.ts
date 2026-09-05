import type { MediaInternalWorkflowCommandResponse, MediaInternalWorkflowDraft, MediaInternalWorkflowHistoryResponse, MediaInternalWorkflowListResponse } from "./contracts";

const SHA256 = /^[a-f0-9]{64}$/;
const COMMANDS = new Set(["create", "save_input", "attach_evidence", "pause", "resume", "return", "reassign", "prepare_batch", "prepare_sample", "select_template", "schedule", "prepare_live"]);
const MEDIA_TYPES = new Set(["planting_copy", "short_video", "digital_human_live"]);
const STATUSES = new Set(["draft", "prepared", "paused", "returned", "scheduled"]);
const OPERATIONS = new Set(["task_brief.create", "task_brief.revise"]);
const DETAIL_KEYS = new Set(["mediaType", "businessObject", "objective", "assignee", "evidence", "batch", "sample", "template", "schedule", "liveControl", "pausedFromStatus", "returnReason", "lastCommand"]);
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);

function parseTenant(value: unknown): void { if (!isRecord(value) || typeof value.orgId !== "string" || typeof value.projectId !== "string") throw new TypeError("media workflow tenant invalid"); }

export function parseMediaInternalWorkflowDraft(value: unknown): MediaInternalWorkflowDraft {
  if (!isRecord(value) || value.resourceType !== "TaskBriefRevision" || typeof value.resourceId !== "string" || !Number.isSafeInteger(value.revision) || Number(value.revision) < 1 || typeof value.contentHash !== "string" || !SHA256.test(value.contentHash) || !Number.isSafeInteger(value.version) || Number(value.version) < 1 || !MEDIA_TYPES.has(String(value.mediaType)) || typeof value.title !== "string" || typeof value.summary !== "string" || !isRecord(value.details) || !STATUSES.has(String(value.status))) throw new TypeError("media workflow draft invalid");
  if (Object.keys(value.details).some((key) => !DETAIL_KEYS.has(key)) || value.details.mediaType !== value.mediaType) throw new TypeError("media workflow details drift");
  return value as unknown as MediaInternalWorkflowDraft;
}

function assertZeroSideEffects(value: unknown): void { if (!isRecord(value) || value.providerInvocationCount !== 0 || value.externalGenerationCount !== 0 || value.feeChargeCount !== 0 || value.publicationCount !== 0 || value.businessMutationCount !== 0) throw new TypeError("media workflow side effects invalid"); }

export function parseMediaInternalWorkflowCommand(value: unknown): MediaInternalWorkflowCommandResponse {
  if (!isRecord(value)) throw new TypeError("media workflow response invalid");
  parseTenant(value.tenant);
  if (!COMMANDS.has(String(value.command)) || typeof value.taskId !== "string" || typeof value.message !== "string" || !isRecord(value.receipt)) throw new TypeError("media workflow response invalid");
  if (typeof value.receipt.receiptId !== "string" || !OPERATIONS.has(String(value.receipt.operation)) || typeof value.receipt.idempotencyKey !== "string" || typeof value.receipt.replay !== "boolean") throw new TypeError("media workflow Receipt invalid");
  parseMediaInternalWorkflowDraft(value.draft); assertZeroSideEffects(value.sideEffects);
  return value as unknown as MediaInternalWorkflowCommandResponse;
}

function parseCollection(value: unknown, label: string): MediaInternalWorkflowHistoryResponse {
  if (!isRecord(value) || !Array.isArray(value.items) || !Number.isSafeInteger(value.count) || value.count !== value.items.length) throw new TypeError(`${label} invalid`);
  parseTenant(value.tenant); value.items.forEach(parseMediaInternalWorkflowDraft);
  return value as unknown as MediaInternalWorkflowHistoryResponse;
}

export function parseMediaInternalWorkflowHistory(value: unknown): MediaInternalWorkflowHistoryResponse { const parsed = parseCollection(value, "media workflow history"); if (parsed.items.some((item, index) => item.revision !== index + 1 || item.version !== index + 1 || (index > 0 && item.resourceId !== parsed.items[0]!.resourceId))) throw new TypeError("media workflow history drift"); return parsed; }
export function parseMediaInternalWorkflowList(value: unknown): MediaInternalWorkflowListResponse { return parseCollection(value, "media workflow list"); }
