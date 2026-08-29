import { describe, expect, it } from "vitest";

import { pipelineFlowLine, pipelineStatusKey } from "./pipelineMeta";

describe("pipelineStatusKey", () => {
  it.each([
    ["SUCCEEDED", "success"],
    ["success", "success"],
    ["FAILED", "failed"],
    ["error", "failed"],
    ["RUNNING", "running"],
    ["in_progress", "running"],
    [undefined, "unknown"],
  ])("normalizes %s to %s", (status, expected) => {
    expect(pipelineStatusKey(status)).toBe(expected);
  });
});

describe("pipelineFlowLine", () => {
  it("renders the real source and pipeline as a Chinese business flow", () => {
    const flow = pipelineFlowLine({
      id: "P05-order-qyh",
      sourceId: "niushop-qyh",
      displayName: "栖月汇-订单",
      datasetRid: "ri.aos.dataset.P05-order-qyh",
    });

    expect(flow).toBe("栖月汇微商城 → 数据抽取 → 栖月汇-订单");
    expect(flow).not.toContain("Ingest");
    expect(flow).not.toContain("ri.aos");
  });
});
