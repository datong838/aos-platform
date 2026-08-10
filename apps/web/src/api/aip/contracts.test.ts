import { describe, expect, it } from "vitest";
import { assertKnownStatus, parseAipErrorBody, TASK_RUN_STATUSES } from "./contracts";

describe("AIP-0 frozen frontend contracts", () => {
  it("parses the canonical error envelope and preserves traceId", () => {
    expect(parseAipErrorBody({ code: "AIP_VERSION_CONFLICT", message: "conflict", details: null, traceId: "t-1" })).toEqual({
      code: "AIP_VERSION_CONFLICT",
      message: "conflict",
      details: null,
      traceId: "t-1",
    });
  });

  it("fails closed on malformed error and unknown status", () => {
    expect(parseAipErrorBody({ code: "X", message: "bad" })).toBeNull();
    expect(() => assertKnownStatus("mostly-done", TASK_RUN_STATUSES, "taskRun")).toThrow(/unknown status/);
  });
});

