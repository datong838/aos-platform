import { describe, expect, it } from "vitest";
import {
  IntegrationCaseClientError,
  IntegrationCaseError,
  normalizeIntegrationCaseError,
  type IntegrationCaseApiErrorBody,
} from "./errors";

function raw(status: number, mutation = false, code = `CODE_${status}`): IntegrationCaseClientError {
  const body: IntegrationCaseApiErrorBody = {
    code,
    message: `server ${status}`,
    details: { status },
    traceId: `trace-${status}`,
  };
  return new IntegrationCaseClientError(body.message, {
    status,
    body,
    operationId: mutation ? "create_integration_case" : "get_integration_case",
    mutation,
  });
}

describe("M4-1 integration case error adapter", () => {
  it.each([
    [400, "invalid_request", "fix_request"],
    [401, "unauthenticated", "reauthenticate"],
    [403, "forbidden", "request_access"],
    [404, "not_visible_or_missing", "none"],
    [409, "conflict", "refresh_then_retry"],
    [422, "invalid_request", "fix_request"],
    [428, "precondition_required", "failure_closed"],
    [500, "server_error", "retry_read"],
  ] as const)("normalizes HTTP %i", (status, kind, recovery) => {
    expect(normalizeIntegrationCaseError(raw(status))).toMatchObject({
      status, kind, recovery, failureClosed: true,
    });
  });

  it("collapses hidden and missing GET resources into the same non-disclosing 404", () => {
    const hidden = normalizeIntegrationCaseError(raw(404, false, "MARKING_ACCESS_DENIED"));
    const missing = normalizeIntegrationCaseError(raw(404, false, "NOT_FOUND"));
    for (const error of [hidden, missing]) {
      expect(error).toMatchObject({
        code: "NOT_VISIBLE_OR_MISSING",
        message: "资源不可见或不存在。",
        details: null,
        notVisibleOrMissing: true,
      });
    }
  });

  it("distinguishes a failed read from an unknown mutation outcome", () => {
    const readNetwork = normalizeIntegrationCaseError(raw(0, false, "NETWORK"));
    expect(readNetwork).toMatchObject({ recovery: "retry_read", retryable: true, outcomeUnknown: false, requiresRefresh: false });

    const writeNetwork = normalizeIntegrationCaseError(raw(0, true, "NETWORK"));
    expect(writeNetwork).toMatchObject({ recovery: "retry_same_command", retryable: true, outcomeUnknown: true, requiresRefresh: true });

    const write500 = normalizeIntegrationCaseError(raw(500, true, "EVIDENCE_INTEGRITY_CORRUPT"));
    expect(write500).toMatchObject({ code: "EVIDENCE_INTEGRITY_CORRUPT", outcomeUnknown: true, requiresRefresh: true });
  });

  it("keeps proactive offline rejection as known zero-execution", () => {
    const error = raw(0, true, "OFFLINE_MUTATION_DISABLED");
    expect(normalizeIntegrationCaseError(error)).toMatchObject({
      kind: "offline_mutation_disabled",
      retryable: false,
      outcomeUnknown: false,
      failureClosed: true,
    });
  });

  it("keeps an invalid success response distinct from a transport failure", () => {
    const malformed = raw(0, true, "INVALID_SUCCESS_RESPONSE");
    expect(normalizeIntegrationCaseError(malformed)).toMatchObject({
      kind: "unknown",
      code: "INVALID_SUCCESS_RESPONSE",
      recovery: "retry_same_command",
      outcomeUnknown: true,
      requiresRefresh: true,
    });
  });

  it("is idempotent and fails closed for an unsupported shape", () => {
    const normalized = normalizeIntegrationCaseError(raw(409, true));
    expect(normalizeIntegrationCaseError(normalized)).toBe(normalized);
    expect(normalized).toBeInstanceOf(IntegrationCaseError);
    expect(normalizeIntegrationCaseError({ status: 502, body: "bad" })).toMatchObject({
      status: null,
      kind: "unknown",
      recovery: "failure_closed",
    });
  });
});
