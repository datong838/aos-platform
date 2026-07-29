/**
 * W3-C6 · pipelineCanvas 纯函数单测
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  buildDemoHistory,
  formatHistoryTime,
  historyPathLabel,
  pickTransformNode,
  xformStorageKey,
  loadLocalXform,
  saveLocalXform,
  formatTrialMsg,
  type GraphPayload,
} from "./pipelineCanvas";

describe("W3-C6 buildDemoHistory", () => {
  it("returns 3 demo entries", () => {
    const items = buildDemoHistory({ id: "pipe-1", lastBuild: { id: "b1", status: "SUCCEEDED" } }, "pipe-1");
    expect(items.length).toBe(3);
    expect(items[0].action).toBe("created");
    expect(items[1].detail).toContain("b1");
  });

  it("works with null pipe", () => {
    const items = buildDemoHistory(null, "x");
    expect(items.length).toBe(3);
    expect(items.every((h) => h.pipeline_id === "x")).toBe(true);
  });
});

describe("W3-C6 formatHistoryTime / historyPathLabel", () => {
  it("formats unix seconds", () => {
    const s = formatHistoryTime(1_700_000_000);
    expect(s).not.toBe("—");
    expect(s.length).toBeGreaterThan(4);
  });

  it("dash for invalid", () => {
    expect(formatHistoryTime(undefined)).toBe("—");
  });

  it("path labels", () => {
    expect(historyPathLabel(true)).toBe("演示路径");
    expect(historyPathLabel(false)).toBe("API");
  });
});

describe("W3-C6 pickTransformNode", () => {
  it("picks transform node_type", () => {
    const g: GraphPayload = {
      nodes: [
        { id: "a", node_type: "source" },
        { id: "b", node_type: "transform", name: "xf" },
      ],
    };
    expect(pickTransformNode(g)?.id).toBe("b");
  });

  it("falls back to name containing transform", () => {
    const g: GraphPayload = { nodes: [{ id: "t1", name: "my_transform" }] };
    expect(pickTransformNode(g)?.id).toBe("t1");
  });

  it("null when empty", () => {
    expect(pickTransformNode(null)).toBeNull();
    expect(pickTransformNode({ nodes: [] })).toBeNull();
  });
});

describe("W3-C6 xform localStorage", () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    localStorage.clear();
  });

  it("round-trips config", () => {
    expect(xformStorageKey("p1")).toBe("aos.pipeline.xform.p1");
    saveLocalXform("p1", { expression: "a+1", filter: "x>0" });
    expect(loadLocalXform("p1")).toEqual({ expression: "a+1", filter: "x>0" });
  });

  it("returns null when missing", () => {
    expect(loadLocalXform("missing")).toBeNull();
  });
});

describe("W3-C6 formatTrialMsg", () => {
  it("ok api", () => {
    expect(formatTrialMsg(true, false, "10ms")).toContain("API");
    expect(formatTrialMsg(true, false, "10ms")).toContain("成功");
  });

  it("fail demo", () => {
    expect(formatTrialMsg(false, true, "err")).toContain("演示路径");
    expect(formatTrialMsg(false, true, "err")).toContain("失败");
  });
});
