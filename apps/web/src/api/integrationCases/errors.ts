import type { IntegrationCaseErrorStatus } from "./operations";

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export interface IntegrationCaseApiErrorBody {
  code: string;
  message: string;
  details: { [key: string]: JsonValue } | null;
  traceId: string;
}

export type IntegrationCaseFailureKind =
  | "network"
  | "offline_mutation_disabled"
  | "invalid_request"
  | "unauthenticated"
  | "forbidden"
  | "not_visible_or_missing"
  | "conflict"
  | "precondition_required"
  | "server_error"
  | "unknown";

export type IntegrationCaseRecovery =
  | "retry_read"
  | "retry_same_command"
  | "fix_request"
  | "reauthenticate"
  | "request_access"
  | "refresh_then_retry"
  | "none"
  | "failure_closed";

export interface IntegrationCaseFailure {
  status: 0 | IntegrationCaseErrorStatus | null;
  kind: IntegrationCaseFailureKind;
  code: string;
  message: string;
  traceId: string | null;
  details: { [key: string]: JsonValue } | null;
  recovery: IntegrationCaseRecovery;
  isConflict: boolean;
  requiresRefresh: boolean;
  notVisibleOrMissing: boolean;
  retryable: boolean;
  outcomeUnknown: boolean;
  failureClosed: true;
}

export class IntegrationCaseClientError extends Error {
  readonly status: number;
  readonly body: IntegrationCaseApiErrorBody;
  readonly operationId: string;
  readonly mutation: boolean;

  constructor(message: string, options: {
    status: number;
    body: IntegrationCaseApiErrorBody;
    operationId: string;
    mutation: boolean;
  }) {
    super(message);
    this.name = "IntegrationCaseClientError";
    this.status = options.status;
    this.body = options.body;
    this.operationId = options.operationId;
    this.mutation = options.mutation;
  }
}

export class IntegrationCaseError extends Error implements IntegrationCaseFailure {
  readonly status: 0 | IntegrationCaseErrorStatus | null;
  readonly kind: IntegrationCaseFailureKind;
  readonly code: string;
  readonly traceId: string | null;
  readonly details: { [key: string]: JsonValue } | null;
  readonly recovery: IntegrationCaseRecovery;
  readonly isConflict: boolean;
  readonly requiresRefresh: boolean;
  readonly notVisibleOrMissing: boolean;
  readonly retryable: boolean;
  readonly outcomeUnknown: boolean;
  readonly failureClosed = true as const;

  constructor(failure: IntegrationCaseFailure, options?: { cause?: unknown }) {
    super(failure.message);
    this.name = "IntegrationCaseError";
    if (options && Object.prototype.hasOwnProperty.call(options, "cause")) {
      (this as Error & { cause?: unknown }).cause = options.cause;
    }
    this.status = failure.status;
    this.kind = failure.kind;
    this.code = failure.code;
    this.traceId = failure.traceId;
    this.details = failure.details;
    this.recovery = failure.recovery;
    this.isConflict = failure.isConflict;
    this.requiresRefresh = failure.requiresRefresh;
    this.notVisibleOrMissing = failure.notVisibleOrMissing;
    this.retryable = failure.retryable;
    this.outcomeUnknown = failure.outcomeUnknown;
  }
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function raw(error: unknown): {
  status: number | null;
  body: Partial<IntegrationCaseApiErrorBody> | null;
  mutation: boolean;
} {
  if (!record(error)) return { status: null, body: null, mutation: false };
  return {
    status: typeof error.status === "number" && Number.isInteger(error.status) ? error.status : null,
    body: record(error.body) ? error.body as Partial<IntegrationCaseApiErrorBody> : null,
    mutation: error.mutation === true,
  };
}

function failure(
  status: 0 | IntegrationCaseErrorStatus | null,
  kind: IntegrationCaseFailureKind,
  code: string,
  message: string,
  recovery: IntegrationCaseRecovery,
  options: Partial<Pick<IntegrationCaseFailure, "traceId" | "details" | "isConflict" | "requiresRefresh" | "notVisibleOrMissing" | "retryable" | "outcomeUnknown">> = {},
): IntegrationCaseFailure {
  return {
    status, kind, code, message, recovery,
    traceId: options.traceId ?? null,
    details: options.details ?? null,
    isConflict: options.isConflict ?? false,
    requiresRefresh: options.requiresRefresh ?? false,
    notVisibleOrMissing: options.notVisibleOrMissing ?? false,
    retryable: options.retryable ?? false,
    outcomeUnknown: options.outcomeUnknown ?? false,
    failureClosed: true,
  };
}

function safeCode(body: Partial<IntegrationCaseApiErrorBody> | null, fallback: string): string {
  return typeof body?.code === "string" && body.code.trim() ? body.code : fallback;
}

function safeTrace(body: Partial<IntegrationCaseApiErrorBody> | null): string | null {
  return typeof body?.traceId === "string" && body.traceId.trim() ? body.traceId : null;
}

function safeDetails(body: Partial<IntegrationCaseApiErrorBody> | null): { [key: string]: JsonValue } | null {
  return record(body?.details) ? body.details as { [key: string]: JsonValue } : null;
}

export function normalizeIntegrationCaseError(error: unknown): IntegrationCaseError {
  if (error instanceof IntegrationCaseError) return error;
  const { status, body, mutation } = raw(error);
  const traceId = safeTrace(body);
  const code = safeCode(body, status === null ? "UNCLASSIFIED_ERROR" : `HTTP_${status}`);

  let normalized: IntegrationCaseFailure;
  if (body?.code === "OFFLINE_MUTATION_DISABLED") {
    normalized = failure(0, "offline_mutation_disabled", "OFFLINE_MUTATION_DISABLED", "当前处于离线状态，接入案例写操作已在发送前停止。", "failure_closed");
  } else if (body?.code === "INVALID_SUCCESS_RESPONSE") {
    normalized = mutation
      ? failure(0, "unknown", "INVALID_SUCCESS_RESPONSE", "服务端返回了不可信的写响应；请先刷新，并用原幂等键重试同一命令。", "retry_same_command", { retryable: true, requiresRefresh: true, outcomeUnknown: true })
      : failure(0, "unknown", "INVALID_SUCCESS_RESPONSE", "服务端返回了不可信的读取响应，已失败关闭。", "failure_closed");
  } else if (status === 0 || body?.code === "NETWORK") {
    normalized = mutation
      ? failure(0, "network", "NETWORK", "无法确认写操作结果；恢复连接后请先刷新，并用原幂等键重试同一命令。", "retry_same_command", { retryable: true, requiresRefresh: true, outcomeUnknown: true })
      : failure(0, "network", "NETWORK", "无法读取接入案例；恢复连接后可以重试读取。", "retry_read", { retryable: true });
  } else if (status === 404) {
    normalized = failure(404, "not_visible_or_missing", "NOT_VISIBLE_OR_MISSING", "资源不可见或不存在。", "none", { notVisibleOrMissing: true });
  } else if (status === 403) {
    normalized = failure(403, "forbidden", code, "当前身份无权执行此接入案例操作。", "request_access", { traceId, details: safeDetails(body) });
  } else if (status === 409) {
    normalized = failure(409, "conflict", code, "资源状态已变化，请刷新后再决定是否重试。", "refresh_then_retry", { traceId, details: safeDetails(body), isConflict: true, requiresRefresh: true });
  } else if (status === 422) {
    normalized = failure(422, "invalid_request", code, "请求未通过接入案例契约校验。", "fix_request", { traceId, details: safeDetails(body) });
  } else if (status === 428) {
    normalized = failure(428, "precondition_required", code, "操作缺少强版本前置条件，已停止执行。", "failure_closed", { traceId, details: safeDetails(body) });
  } else if (status === 500) {
    normalized = mutation
      ? failure(500, "server_error", code, "服务端异常，写操作结果未知；请刷新并用原幂等键重试。", "retry_same_command", { traceId, requiresRefresh: true, retryable: true, outcomeUnknown: true })
      : failure(500, "server_error", code, "接入案例服务异常，读取已失败关闭。", "retry_read", { traceId, retryable: true });
  } else if (status === 400) {
    normalized = failure(400, "invalid_request", code, "请求不符合接入案例契约。", "fix_request", { traceId, details: safeDetails(body) });
  } else if (status === 401) {
    normalized = failure(401, "unauthenticated", code, "身份认证已失效，请重新登录。", "reauthenticate", { traceId });
  } else {
    normalized = failure(null, "unknown", code, "收到无法识别的接入案例错误，已停止执行。", "failure_closed");
  }
  return new IntegrationCaseError(normalized, { cause: error });
}
