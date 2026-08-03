import type { AssetControlErrorStatus } from "./operations";
import type { ApiErrorBody, JsonValue } from "./types";

export type AssetControlFailureStatus = 0 | AssetControlErrorStatus | null;

export type AssetControlFailureKind =
  | "network"
  | "offline_mutation_disabled"
  | "invalid_request"
  | "unauthenticated"
  | "forbidden"
  | "not_visible_or_missing"
  | "conflict"
  | "precondition_failed"
  | "precondition_required"
  | "service_unavailable"
  | "server_error"
  | "unknown";

export type AssetControlRecovery =
  | "retry_same_command"
  | "fix_request"
  | "reauthenticate"
  | "request_access"
  | "refresh_then_retry"
  | "none"
  | "failure_closed";

export interface AssetControlFailure {
  status: AssetControlFailureStatus;
  kind: AssetControlFailureKind;
  code: string;
  message: string;
  traceId: string | null;
  details: { [key: string]: JsonValue } | null;
  recovery: AssetControlRecovery;
  isConflict: boolean;
  requiresRefresh: boolean;
  notVisibleOrMissing: boolean;
  retryable: boolean;
  /** Network loss can occur after the server committed a mutation. */
  outcomeUnknown: boolean;
  /** No error may be interpreted as a successful control-plane operation. */
  failureClosed: true;
}

type FailurePolicy = Omit<
  AssetControlFailure,
  "status" | "code" | "traceId" | "details" | "failureClosed"
>;

const STATUS_POLICIES: Record<AssetControlErrorStatus, FailurePolicy> = {
  400: {
    kind: "invalid_request",
    message: "请求不符合资产控制契约，请检查输入后重试。",
    recovery: "fix_request",
    isConflict: false,
    requiresRefresh: false,
    notVisibleOrMissing: false,
    retryable: false,
    outcomeUnknown: false,
  },
  401: {
    kind: "unauthenticated",
    message: "身份认证已失效，请重新登录。",
    recovery: "reauthenticate",
    isConflict: false,
    requiresRefresh: false,
    notVisibleOrMissing: false,
    retryable: false,
    outcomeUnknown: false,
  },
  403: {
    kind: "forbidden",
    message: "当前身份无权执行此资产控制操作。",
    recovery: "request_access",
    isConflict: false,
    requiresRefresh: false,
    notVisibleOrMissing: false,
    retryable: false,
    outcomeUnknown: false,
  },
  404: {
    kind: "not_visible_or_missing",
    message: "资源不可见或不存在。",
    recovery: "none",
    isConflict: false,
    requiresRefresh: false,
    notVisibleOrMissing: true,
    retryable: false,
    outcomeUnknown: false,
  },
  409: {
    kind: "conflict",
    message: "资源状态已变化，请刷新读取最新状态后再决定是否重试。",
    recovery: "refresh_then_retry",
    isConflict: true,
    requiresRefresh: true,
    notVisibleOrMissing: false,
    retryable: false,
    outcomeUnknown: false,
  },
  412: {
    kind: "precondition_failed",
    message: "资源版本已变化，请刷新读取最新版本后再决定是否重试。",
    recovery: "refresh_then_retry",
    isConflict: true,
    requiresRefresh: true,
    notVisibleOrMissing: false,
    retryable: false,
    outcomeUnknown: false,
  },
  422: {
    kind: "invalid_request",
    message: "请求未通过服务端校验或解析资源上限，请调整输入后重新发起命令。",
    recovery: "fix_request",
    isConflict: false,
    requiresRefresh: false,
    notVisibleOrMissing: false,
    retryable: false,
    outcomeUnknown: false,
  },
  428: {
    kind: "precondition_required",
    message: "操作缺少强版本前置条件，已停止执行。",
    recovery: "failure_closed",
    isConflict: false,
    requiresRefresh: false,
    notVisibleOrMissing: false,
    retryable: false,
    outcomeUnknown: false,
  },
  500: {
    kind: "server_error",
    message: "资产控制服务暂时异常，本次操作结果未知；请先刷新状态，重试时复用原幂等键。",
    recovery: "retry_same_command",
    isConflict: false,
    requiresRefresh: true,
    notVisibleOrMissing: false,
    retryable: true,
    outcomeUnknown: true,
  },
  503: {
    kind: "service_unavailable",
    message: "信任根暂时不可用，服务端已确认失败关闭；请稍后重新发起新命令。",
    recovery: "none",
    isConflict: false,
    requiresRefresh: false,
    notVisibleOrMissing: false,
    retryable: false,
    outcomeUnknown: false,
  },
};

const NETWORK_POLICY: FailurePolicy = {
  kind: "network",
  message: "无法确认资产控制操作结果；恢复连接后请先刷新状态，重试时复用原幂等键。",
  recovery: "retry_same_command",
  isConflict: false,
  requiresRefresh: true,
  notVisibleOrMissing: false,
  retryable: true,
  outcomeUnknown: true,
};

const OFFLINE_MUTATION_DISABLED_POLICY: FailurePolicy = {
  kind: "offline_mutation_disabled",
  message: "当前处于离线状态，资产控制写操作已在发送前停止。",
  recovery: "failure_closed",
  isConflict: false,
  requiresRefresh: false,
  notVisibleOrMissing: false,
  retryable: false,
  outcomeUnknown: false,
};

const UNKNOWN_POLICY: FailurePolicy = {
  kind: "unknown",
  message: "收到无法识别的资产控制错误，已停止执行。",
  recovery: "failure_closed",
  isConflict: false,
  requiresRefresh: false,
  notVisibleOrMissing: false,
  retryable: false,
  outcomeUnknown: false,
};

export class AssetControlError extends Error implements AssetControlFailure {
  readonly status: AssetControlFailureStatus;
  readonly kind: AssetControlFailureKind;
  readonly code: string;
  readonly traceId: string | null;
  readonly details: { [key: string]: JsonValue } | null;
  readonly recovery: AssetControlRecovery;
  readonly isConflict: boolean;
  readonly requiresRefresh: boolean;
  readonly notVisibleOrMissing: boolean;
  readonly retryable: boolean;
  readonly outcomeUnknown: boolean;
  readonly failureClosed = true as const;

  constructor(failure: AssetControlFailure, options?: { cause?: unknown }) {
    super(failure.message);
    if (options && Object.prototype.hasOwnProperty.call(options, "cause")) {
      (this as Error & { cause?: unknown }).cause = options.cause;
    }
    this.name = "AssetControlError";
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function errorStatus(error: unknown): number | null {
  if (!isRecord(error)) return null;
  return typeof error.status === "number" && Number.isInteger(error.status)
    ? error.status
    : null;
}

function errorBody(error: unknown): Partial<ApiErrorBody> | null {
  if (!isRecord(error) || !isRecord(error.body)) return null;
  return error.body as Partial<ApiErrorBody>;
}

function safeCode(body: Partial<ApiErrorBody> | null, fallback: string): string {
  return typeof body?.code === "string" && body.code.trim() ? body.code : fallback;
}

function safeTraceId(body: Partial<ApiErrorBody> | null): string | null {
  return typeof body?.traceId === "string" && body.traceId.trim()
    ? body.traceId
    : null;
}

function safeDetails(
  body: Partial<ApiErrorBody> | null,
): { [key: string]: JsonValue } | null {
  if (!isRecord(body?.details)) return null;
  return body.details as { [key: string]: JsonValue };
}

function isSupportedStatus(status: number | null): status is AssetControlErrorStatus {
  return (
    status !== null && Object.prototype.hasOwnProperty.call(STATUS_POLICIES, status)
  );
}

function isNetworkFailure(status: number | null, body: Partial<ApiErrorBody> | null): boolean {
  return status === 0 || body?.code === "NETWORK" || body?.code === "OFFLINE_NO_CACHE";
}

function isOfflineMutationDisabled(body: Partial<ApiErrorBody> | null): boolean {
  return body?.code === "OFFLINE_MUTATION_DISABLED";
}

function failureFromPolicy(
  status: AssetControlFailureStatus,
  policy: FailurePolicy,
  code: string,
  traceId: string | null,
  details: { [key: string]: JsonValue } | null,
): AssetControlFailure {
  return {
    status,
    ...policy,
    code,
    traceId,
    details,
    failureClosed: true,
  };
}

/**
 * Normalize common api/client.ts errors without changing that shared layer.
 * Unknown bodies and statuses fail closed; callers must never infer success.
 */
export function normalizeAssetControlError(error: unknown): AssetControlError {
  if (error instanceof AssetControlError) return error;

  const status = errorStatus(error);
  const body = errorBody(error);
  // The SDK raises this before fetch. It is therefore a known non-execution,
  // not a network failure with an unknown mutation outcome.
  if (isOfflineMutationDisabled(body)) {
    return new AssetControlError(
      failureFromPolicy(
        0,
        OFFLINE_MUTATION_DISABLED_POLICY,
        "OFFLINE_MUTATION_DISABLED",
        safeTraceId(body),
        null,
      ),
      { cause: error },
    );
  }
  if (isNetworkFailure(status, body)) {
    return new AssetControlError(
      failureFromPolicy(
        0,
        NETWORK_POLICY,
        safeCode(body, "NETWORK"),
        safeTraceId(body),
        null,
      ),
      { cause: error },
    );
  }

  if (isSupportedStatus(status)) {
    const hideResourceDetails = status === 404;
    return new AssetControlError(
      failureFromPolicy(
        status,
        STATUS_POLICIES[status],
        hideResourceDetails
          ? "NOT_VISIBLE_OR_MISSING"
          : safeCode(body, `HTTP_${status}`),
        safeTraceId(body),
        hideResourceDetails ? null : safeDetails(body),
      ),
      { cause: error },
    );
  }

  return new AssetControlError(
    failureFromPolicy(
      null,
      UNKNOWN_POLICY,
      safeCode(body, "UNCLASSIFIED_ERROR"),
      safeTraceId(body),
      null,
    ),
    { cause: error },
  );
}

export function requiresAssetControlRefresh(error: unknown): boolean {
  return normalizeAssetControlError(error).requiresRefresh;
}

export function isAssetControlConflict(error: unknown): boolean {
  return normalizeAssetControlError(error).isConflict;
}
