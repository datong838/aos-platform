import { describe, expect, it } from "vitest";
import {
  LARGE_TABLE_HINT_THRESHOLD,
  needsPaginationHint,
} from "./paginationGuard";
import { layoutNodeCount, normalizeLayout } from "./pages/CanvasPage";
import { resolveRenderKind, buildActionExecuteBody, newCanvasIdempotencyKey, summarizeMetricRows } from "./pages/canvasWidgets";
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

  it("106 maps action/graph string widgets", () => {
    const nodes = normalizeLayout(["Action Form", "Graph View"]);
    expect(nodes[0].kind).toBe("action");
    expect(nodes[0].pluginId).toBe("action-form");
    expect(nodes[1].kind).toBe("graph");
    expect(nodes[1].pluginId).toBe("graph-view");
  });

  it("106 resolveRenderKind upgrades legacy stub+pluginId", () => {
    expect(resolveRenderKind({ kind: "stub", pluginId: "action-form" })).toBe("action");
    expect(resolveRenderKind({ kind: "stub", pluginId: "graph-view" })).toBe("graph");
    expect(resolveRenderKind({ kind: "stub", pluginId: "metric-card" })).toBe("metric");
  });

  it("106 normalizeLayout upgrades saved stub nodes", () => {
    const nodes = normalizeLayout([
      { id: "x", kind: "stub", title: "旧", pluginId: "action-form" },
    ]);
    expect(nodes[0].kind).toBe("action");
  });

  it("107 buildActionExecuteBody defaults HITL", () => {
    const body = buildActionExecuteBody({
      actionTypeId: "CloseWorkOrder",
      payload: { reason: "x" },
    });
    expect(body.autoApprove).toBe(false);
    expect(body.objectType).toBe("WorkOrder");
    expect(body.proposed).toEqual({ reason: "x" });
    expect(body.objectId).toBeUndefined();
  });

  it("107 newCanvasIdempotencyKey has prefix", () => {
    const k = newCanvasIdempotencyKey();
    expect(k.startsWith("canvas-af-")).toBe(true);
    expect(newCanvasIdempotencyKey()).not.toBe(k);
  });

  it("108 resolveRenderKind metric-card", () => {
    expect(resolveRenderKind({ kind: "stub", pluginId: "metric-card" })).toBe("metric");
  });

  it("108 summarizeMetricRows buckets", () => {
    const s = summarizeMetricRows(
      [
        { status: "open" },
        { status: "open" },
        { status: "closed" },
        { props: { status: "open" } },
      ],
      "status",
    );
    expect(s.total).toBe(4);
    expect(s.buckets.find((b) => b.label === "open")?.count).toBe(3);
    expect(s.buckets.find((b) => b.label === "closed")?.count).toBe(1);
  });

  it("108 normalizeLayout metric string", () => {
    const nodes = normalizeLayout(["Metric Card"]);
    expect(nodes[0].kind).toBe("metric");
    expect(nodes[0].pluginId).toBe("metric-card");
  });
});

describe("schedules cron", () => {
  it("parses five cron fields", () => {
    const fields = parseCronFields("0 2 * * 1");
    expect(fields).toHaveLength(5);
    expect(fields.map((f) => f.value)).toEqual(["0", "2", "*", "*", "1"]);
  });
});
