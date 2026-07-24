import { describe, expect, it } from "vitest";
import { lintClientSideId } from "./ontologyGuard";

describe("ontologyGuard", () => {
  it("accepts PascalCase ids", () => {
    expect(lintClientSideId("WorkOrder").ok).toBe(true);
  });
  it("rejects lowercase ids", () => {
    expect(lintClientSideId("workOrder").ok).toBe(false);
  });
});
