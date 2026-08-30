export type AipErrorBody = {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  traceId: string;
};

export type ResourceRef = {
  resourceType: string;
  resourceId: string;
  revision?: string | null;
  authority: string;
};

export type PageInfo = {
  limit: number;
  nextCursor: string | null;
  hasMore: boolean;
};

export const TASK_STATUSES = [
  "pending",
  "planning",
  "awaiting_approval",
  "approved",
  "executing",
  "paused",
  "completed",
  "failed",
  "cancelled",
  "rolled_back",
] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

export const TASK_RUN_STATUSES = [
  "queued",
  "running",
  "pausing",
  "paused",
  "succeeded",
  "failed",
  "cancelled",
  "unknown",
] as const;
export type TaskRunStatus = (typeof TASK_RUN_STATUSES)[number];

export const STEP_RUN_STATUSES = [
  "queued",
  "running",
  "succeeded",
  "failed",
  "skipped",
  "unknown",
] as const;
export type StepRunStatus = (typeof STEP_RUN_STATUSES)[number];

export function parseAipErrorBody(value: unknown): AipErrorBody | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const item = value as Record<string, unknown>;
  if (
    typeof item.code !== "string" ||
    typeof item.message !== "string" ||
    typeof item.traceId !== "string" ||
    !(item.details === null || (typeof item.details === "object" && !Array.isArray(item.details)))
  ) return null;
  return {
    code: item.code,
    message: item.message,
    details: item.details as Record<string, unknown> | null,
    traceId: item.traceId,
  };
}

export function assertKnownStatus<T extends readonly string[]>(
  value: unknown,
  allowed: T,
  label: string,
): T[number] {
  if (typeof value !== "string" || !allowed.includes(value)) {
    throw new TypeError(`${label} contains an unknown status`);
  }
  return value as T[number];
}
