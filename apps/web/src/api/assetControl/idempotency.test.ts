import { afterEach, describe, expect, it, vi } from "vitest";

import { createIdempotentCommand, idempotencyKeyFor } from "./idempotency";

const FIRST_UUID = "00000000-0000-4000-8000-000000000001";
const SECOND_UUID = "00000000-0000-4000-8000-000000000002";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("asset-control idempotent command identity", () => {
  it("creates a valid 1-160 character Idempotency-Key", () => {
    vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(FIRST_UUID);

    const key = idempotencyKeyFor(createIdempotentCommand());

    expect(key).toBe(`asset-control-${FIRST_UUID}`);
    expect(key.length).toBeGreaterThanOrEqual(1);
    expect(key.length).toBeLessThanOrEqual(160);
    expect(key).toBe(key.trim());
  });

  it("reuses the same key for retries of one command", () => {
    vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(FIRST_UUID);
    const command = createIdempotentCommand();

    const initialAttempt = idempotencyKeyFor(command);
    const networkRetry = idempotencyKeyFor(command);

    expect(networkRetry).toBe(initialAttempt);
    expect(globalThis.crypto.randomUUID).toHaveBeenCalledTimes(1);
    expect(Object.isFrozen(command)).toBe(true);
  });

  it("uses a new key for each new command", () => {
    vi.spyOn(globalThis.crypto, "randomUUID")
      .mockReturnValueOnce(FIRST_UUID)
      .mockReturnValueOnce(SECOND_UUID);

    const first = createIdempotentCommand();
    const second = createIdempotentCommand();

    expect(idempotencyKeyFor(first)).not.toBe(idempotencyKeyFor(second));
    expect(globalThis.crypto.randomUUID).toHaveBeenCalledTimes(2);
  });

  it("fails closed when secure UUID generation is unavailable", () => {
    vi.stubGlobal("crypto", {});

    expect(() => createIdempotentCommand()).toThrow(
      "secure random UUID generation is unavailable",
    );
  });
});
