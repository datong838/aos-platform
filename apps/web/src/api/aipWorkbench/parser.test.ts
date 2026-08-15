import { describe, expect, it } from "vitest";
import { parseAssistEvent, parseQueryResult, validateAssistStream } from "./parser";

const tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = { resourceType: "SelectionRevision", resourceId: "sel-1", revision: "1", authority: "test" };
const baseEvent = { threadId: "thread-1", turnId: "turn-1", occurredAt: "2026-08-16T00:00:00Z", context: null, blocker: null, content: null, proposalRef: null, usageRefs: [], lineageRefs: [] };

describe("aipWorkbench strict parser", () => {
  it("accepts honest blocked Analyst result and rejects drift", () => {
    const value = { tenant, queryId: "q-1", revision: 1, kind: "metric", status: "blocked", columns: [], rows: [], sourceRefs: [], lineageRefs: [], blockers: [{ code: "METRIC_OWNER_UNAVAILABLE", message: "blocked", dependencyRef: null, retryable: false }], uncertainties: [], cutoffAt: "2026-08-16T00:00:00Z", contentHash: "a".repeat(64), createdAt: "2026-08-16T00:00:01Z" };
    expect(parseQueryResult(value, tenant).status).toBe("blocked");
    expect(() => parseQueryResult({ ...value, shadow: "mock" }, tenant)).toThrow("额外字段");
    expect(() => parseQueryResult({ ...value, tenant: { orgId: "dev-org", projectId: "dev-project" } }, tenant)).toThrow("tenant echo");
  });

  it("requires contiguous terminal Assist events", () => {
    const start = parseAssistEvent({ ...baseEvent, eventType: "start", sequence: 1 });
    const blocked = parseAssistEvent({ ...baseEvent, eventType: "blocked", sequence: 2, blocker: { code: "ASSIST_AGENT_RUN_NOT_FOUND", message: "blocked", dependencyRef: null, retryable: false } });
    expect(validateAssistStream([start, blocked])).toHaveLength(2);
    expect(() => validateAssistStream([start])).toThrow("终态");
    expect(() => validateAssistStream([start, { ...blocked, sequence: 3 }])).toThrow("序列漂移");
    expect(ref.revision).toBe("1");
  });
});
