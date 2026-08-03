import { describe, expect, it } from "vitest";
import {
  AssetControlError,
  isAssetControlConflict,
  normalizeAssetControlError,
  requiresAssetControlRefresh,
} from "./errors";

function apiError(
  status: number,
  code = `CODE_${status}`,
  details: Record<string, unknown> | null = { status },
): Error {
  return Object.assign(new Error(`server message ${status}`), {
    status,
    body: {
      code,
      message: `server message ${status}`,
      details,
      traceId: `trace-${status}`,
    },
  });
}

describe("M3-1 asset-control error normalization", () => {
  it.each([
    [400, "invalid_request", "fix_request"],
    [401, "unauthenticated", "reauthenticate"],
    [403, "forbidden", "request_access"],
    [404, "not_visible_or_missing", "none"],
    [409, "conflict", "refresh_then_retry"],
    [412, "precondition_failed", "refresh_then_retry"],
    [422, "invalid_request", "fix_request"],
    [428, "precondition_required", "failure_closed"],
    [500, "server_error", "retry_same_command"],
  ] as const)("normalizes HTTP %i", (status, kind, recovery) => {
    const normalized = normalizeAssetControlError(apiError(status));
    expect(normalized).toBeInstanceOf(AssetControlError);
    expect(normalized).toMatchObject({
      status,
      kind,
      recovery,
      traceId: `trace-${status}`,
      failureClosed: true,
    });
  });

  it("requires a refresh for 409 and 412 instead of automatic overwrite", () => {
    for (const status of [409, 412]) {
      const normalized = normalizeAssetControlError(apiError(status));
      expect(normalized.isConflict).toBe(true);
      expect(normalized.requiresRefresh).toBe(true);
      expect(normalized.retryable).toBe(false);
      expect(isAssetControlConflict(normalized)).toBe(true);
      expect(requiresAssetControlRefresh(normalized)).toBe(true);
    }
  });

  it("uses one non-disclosing 404 result and drops server details", () => {
    const hidden = normalizeAssetControlError(
      apiError(404, "MARKING_ACCESS_DENIED", { resourceId: "secret-bundle" }),
    );
    const missing = normalizeAssetControlError(
      apiError(404, "NOT_FOUND", { resourceId: "missing-bundle" }),
    );

    for (const normalized of [hidden, missing]) {
      expect(normalized.code).toBe("NOT_VISIBLE_OR_MISSING");
      expect(normalized.message).toBe("资源不可见或不存在。");
      expect(normalized.details).toBeNull();
      expect(normalized.notVisibleOrMissing).toBe(true);
    }
  });

  it("marks a network error as an unknown mutation outcome", () => {
    const network = Object.assign(new Error("无法连接 aos-api"), {
      status: 0,
      body: { code: "NETWORK", message: "无法连接 aos-api" },
    });
    const normalized = normalizeAssetControlError(network);

    expect(normalized).toMatchObject({
      status: 0,
      kind: "network",
      code: "NETWORK",
      retryable: true,
      requiresRefresh: true,
      outcomeUnknown: true,
      failureClosed: true,
    });
    expect(normalized.message).toMatch(/复用原幂等键/);
  });

  it("keeps a proactively disabled offline mutation separate from NETWORK", () => {
    const disabled = Object.assign(new Error("mutation disabled while offline"), {
      status: 0,
      body: {
        code: "OFFLINE_MUTATION_DISABLED",
        message: "asset control mutations are disabled while offline",
        details: null,
        traceId: "",
      },
    });
    const normalized = normalizeAssetControlError(disabled);

    expect(normalized).toMatchObject({
      status: 0,
      kind: "offline_mutation_disabled",
      code: "OFFLINE_MUTATION_DISABLED",
      traceId: null,
      outcomeUnknown: false,
      retryable: false,
      requiresRefresh: false,
      failureClosed: true,
    });
    expect(normalized.kind).not.toBe("network");
    expect(normalized.message).toMatch(/发送前停止/);
  });

  it("treats HTTP 500 as an unknown outcome that requires a refresh", () => {
    const normalized = normalizeAssetControlError(
      apiError(500, "INTERNAL_ERROR", null),
    );

    expect(normalized).toMatchObject({
      status: 500,
      kind: "server_error",
      recovery: "retry_same_command",
      retryable: true,
      requiresRefresh: true,
      outcomeUnknown: true,
      failureClosed: true,
    });
    expect(normalized.message).toMatch(/先刷新状态/);
    expect(normalized.message).toMatch(/复用原幂等键/);
  });

  it("keeps 428 failure closed because a refresh cannot supply a missing header", () => {
    const normalized = normalizeAssetControlError(
      apiError(428, "PRECONDITION_REQUIRED"),
    );
    expect(normalized).toMatchObject({
      requiresRefresh: false,
      retryable: false,
      recovery: "failure_closed",
      failureClosed: true,
    });
  });

  it("keeps resolver resource limits failure closed without claiming success", () => {
    const normalized = normalizeAssetControlError(
      apiError(422, "RESOLUTION_LIMIT_EXCEEDED", {
        resource: "backtrackingStates",
      }),
    );

    expect(normalized).toMatchObject({
      status: 422,
      kind: "invalid_request",
      recovery: "fix_request",
      retryable: false,
      requiresRefresh: false,
      outcomeUnknown: false,
      failureClosed: true,
    });
  });

  it("fails closed for malformed bodies and unsupported statuses", () => {
    const malformed = Object.assign(new Error("bad gateway"), {
      status: 502,
      body: "not-json",
    });
    const normalized = normalizeAssetControlError(malformed);

    expect(normalized).toMatchObject({
      status: null,
      kind: "unknown",
      code: "UNCLASSIFIED_ERROR",
      recovery: "failure_closed",
      retryable: false,
      failureClosed: true,
    });
    expect(normalized.details).toBeNull();
  });

  it("is idempotent for an already normalized failure", () => {
    const normalized = normalizeAssetControlError(apiError(409));
    expect(normalizeAssetControlError(normalized)).toBe(normalized);
  });
});
