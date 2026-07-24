import { describe, expect, it } from "vitest";
import { hasMarkingAccess } from "./marking";

describe("widget marking", () => {
  it("allows when no required markings", () => {
    expect(hasMarkingAccess(undefined, [])).toBe(true);
  });

  it("denies when missing marking", () => {
    expect(hasMarkingAccess(["restricted"], ["public"])).toBe(false);
  });

  it("allows when all markings present", () => {
    expect(hasMarkingAccess(["restricted"], ["public", "restricted"])).toBe(
      true,
    );
  });
});
