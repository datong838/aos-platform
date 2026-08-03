import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createIntegrationCaseCommand,
  integrationCaseIdempotencyKeyFor,
} from "./idempotency";

const FIRST_UUID = "00000000-0000-4000-8000-000000000201";
const SECOND_UUID = "00000000-0000-4000-8000-000000000202";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("M4-1 integration case idempotent command identity", () => {
  it("keeps one key stable for retries and creates a new key for a new command", () => {
    vi.spyOn(globalThis.crypto, "randomUUID")
      .mockReturnValueOnce(FIRST_UUID)
      .mockReturnValueOnce(SECOND_UUID);
    const first = createIntegrationCaseCommand();
    const second = createIntegrationCaseCommand();
    expect(integrationCaseIdempotencyKeyFor(first)).toBe(`integration-case-${FIRST_UUID}`);
    expect(integrationCaseIdempotencyKeyFor(first)).toBe(integrationCaseIdempotencyKeyFor(first));
    expect(integrationCaseIdempotencyKeyFor(second)).not.toBe(integrationCaseIdempotencyKeyFor(first));
    expect(Object.isFrozen(first)).toBe(true);
  });

  it("fails closed without secure UUID generation", () => {
    vi.stubGlobal("crypto", {});
    expect(() => createIntegrationCaseCommand()).toThrow(/secure random UUID/);
  });
});
