import { describe, expect, it, vi } from "vitest";

import type { AipClient } from "../aip/client";
import { AipEvidenceSdk } from "./client";
import { parseLineageEvents } from "./contracts";

const event = {
  eventId: "evt-1",
  lineageId: "lin-1",
  rootType: "task_run",
  rootId: "run-1",
  sequence: 1,
  eventType: "input",
  subject: null,
  artifact: null,
  payloadHash: "a".repeat(64),
  quality: "measured",
  occurredAt: "2026-08-12T01:00:00Z",
  observedAt: "2026-08-12T01:00:01Z",
  sourceKind: "task_run",
  sourceId: "run-1",
  sourceHash: "b".repeat(64),
  tenant: { orgId: "org-org", projectId: "dev-project" },
};

describe("AipEvidenceSdk", () => {
  it("通过唯一 AIP client 按 root 查询权威谱系", async () => {
    const request = vi.fn().mockResolvedValue([event]);
    const sdk = new AipEvidenceSdk({ request } as unknown as AipClient);
    await expect(sdk.lineage("task_run", "run-1")).resolves.toMatchObject([{ eventId: "evt-1", quality: "measured" }]);
    expect(request).toHaveBeenCalledWith("listLineageAuthority", {
      params: { root_type: "task_run", root_id: "run-1" },
    });
  });

  it("空列表保持真实空态，不生成固定步骤", () => {
    expect(parseLineageEvents([])).toEqual([]);
  });

  it("序列断裂、root 漂移与不完整 source tuple 均失败关闭", () => {
    expect(() => parseLineageEvents([{ ...event, sequence: 2 }])).toThrow("sequence 不连续");
    expect(() => parseLineageEvents([event, { ...event, eventId: "evt-2", sequence: 2, rootId: "other" }])).toThrow("root 引用不一致");
    expect(() => parseLineageEvents([{ ...event, sourceHash: null }])).toThrow("source tuple 不完整");
  });
});
