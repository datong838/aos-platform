import { describe, expect, it } from "vitest";
import { formatNetworkError } from "./client";

describe("api client network errors", () => {
  it("rewrites Failed to fetch", () => {
    const err = formatNetworkError(new Error("Failed to fetch"), "GET", "/v1/datasets");
    expect(err.message).toMatch(/aos-api/);
    expect(err.message).toMatch(/ensure-api/);
  });
});
