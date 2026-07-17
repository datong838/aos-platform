import { describe, expect, it } from "vitest";
import {
  LARGE_TABLE_HINT_THRESHOLD,
  needsPaginationHint,
} from "./paginationGuard";
import { layoutNodeCount } from "./pages/CanvasPage";

describe("pagination guard", () => {
  it("flags totals over 10k", () => {
    expect(needsPaginationHint(LARGE_TABLE_HINT_THRESHOLD)).toBe(false);
    expect(needsPaginationHint(LARGE_TABLE_HINT_THRESHOLD + 1)).toBe(true);
  });
});

describe("canvas layout", () => {
  it("has default tree nodes", () => {
    expect(layoutNodeCount()).toBeGreaterThanOrEqual(3);
  });
});
