import type {
  CreatorInternalWorkflowCommandResponse,
  CreatorInternalWorkflowDraft,
  CreatorInternalWorkflowHistoryResponse,
  CreatorInternalWorkflowListResponse,
} from "./contracts";

const SHA256 = /^[a-f0-9]{64}$/;
const COMMANDS = new Set(["create", "save", "submit_review", "approve", "reject", "restore"]);
const PURPOSES = new Set(["candidate_import", "outreach_batch", "outreach_message", "collaboration", "delivery_check", "relationship_plan"]);
const STATUSES = new Set(["draft", "in_review", "approved", "rejected"]);
const OPERATIONS = new Set(["task_brief.create", "task_brief.revise"]);
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);

function parseTenant(value: unknown): void {
  if (!isRecord(value) || typeof value.orgId !== "string" || typeof value.projectId !== "string") throw new TypeError("creator workflow tenant invalid");
}

export function parseCreatorInternalWorkflowDraft(value: unknown): CreatorInternalWorkflowDraft {
  if (!isRecord(value) || value.resourceType !== "TaskBriefRevision" || typeof value.resourceId !== "string" || !Number.isSafeInteger(value.revision) || Number(value.revision) < 1 || typeof value.contentHash !== "string" || !SHA256.test(value.contentHash) || !Number.isSafeInteger(value.version) || Number(value.version) < 1 || !PURPOSES.has(String(value.purpose)) || typeof value.title !== "string" || typeof value.summary !== "string" || !isRecord(value.details) || !STATUSES.has(String(value.status))) throw new TypeError("creator workflow draft invalid");
  return value as unknown as CreatorInternalWorkflowDraft;
}

function assertZeroSideEffects(value: unknown): void {
  if (!isRecord(value) || value.providerInvocationCount !== 0 || value.externalOutreachCount !== 0 || value.contractSignatureCount !== 0 || value.businessMutationCount !== 0) throw new TypeError("creator workflow side effects invalid");
}

export function parseCreatorInternalWorkflowCommand(value: unknown): CreatorInternalWorkflowCommandResponse {
  if (!isRecord(value)) throw new TypeError("creator workflow response invalid");
  parseTenant(value.tenant);
  if (!COMMANDS.has(String(value.command)) || typeof value.taskId !== "string" || typeof value.message !== "string" || !isRecord(value.receipt)) throw new TypeError("creator workflow response invalid");
  const receipt = value.receipt;
  if (typeof receipt.receiptId !== "string" || !OPERATIONS.has(String(receipt.operation)) || typeof receipt.idempotencyKey !== "string" || typeof receipt.replay !== "boolean") throw new TypeError("creator workflow Receipt invalid");
  parseCreatorInternalWorkflowDraft(value.draft);
  assertZeroSideEffects(value.sideEffects);
  return value as unknown as CreatorInternalWorkflowCommandResponse;
}

export function parseCreatorInternalWorkflowHistory(value: unknown): CreatorInternalWorkflowHistoryResponse {
  if (!isRecord(value) || !Array.isArray(value.items) || !Number.isSafeInteger(value.count) || value.count !== value.items.length) throw new TypeError("creator workflow history invalid");
  parseTenant(value.tenant);
  const items = value.items.map(parseCreatorInternalWorkflowDraft);
  if (items.some((item, index) => item.revision !== index + 1 || item.version !== index + 1 || (index > 0 && item.resourceId !== items[0]!.resourceId))) throw new TypeError("creator workflow history drift");
  return value as unknown as CreatorInternalWorkflowHistoryResponse;
}

export function parseCreatorInternalWorkflowList(value: unknown): CreatorInternalWorkflowListResponse {
  if (!isRecord(value) || !Array.isArray(value.items) || !Number.isSafeInteger(value.count) || value.count !== value.items.length) throw new TypeError("creator workflow list invalid");
  parseTenant(value.tenant);
  value.items.forEach(parseCreatorInternalWorkflowDraft);
  return value as unknown as CreatorInternalWorkflowListResponse;
}
