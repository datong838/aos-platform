import { describe, expect, it } from "vitest";
import {
  LARGE_TABLE_HINT_THRESHOLD,
  needsPaginationHint,
} from "./paginationGuard";
import { layoutNodeCount, normalizeLayout } from "./pages/CanvasPage";
import { parseCronFields } from "./pages/s2/dataSchedules";

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

  it("upgrades legacy string widgets", () => {
    const nodes = normalizeLayout(["Filter site", "Object Table"]);
    expect(nodes).toHaveLength(2);
    expect(nodes[0].kind).toBe("filter");
    expect(nodes[1].kind).toBe("table");
  });

  it("keeps object widgets", () => {
    const nodes = normalizeLayout([{ id: "a", kind: "buddy", title: "Buddy" }]);
    expect(nodes[0].kind).toBe("buddy");
  });
});

describe("schedules cron", () => {
  it("parses five cron fields", () => {
    const fields = parseCronFields("0 2 * * 1");
    expect(fields).toHaveLength(5);
    expect(fields.map((f) => f.value)).toEqual(["0", "2", "*", "*", "1"]);
  });
});
