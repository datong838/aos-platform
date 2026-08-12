import { describe, expect, it, vi } from "vitest";

import type { AipClient } from "../aip/client";
import { AipEvidenceSdk } from "./client";
import { parseLineageEvents, parseTelemetrySpans, parseUsageReceipts } from "./contracts";

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

const span = {
  spanRecordId: "span-record-1", provider: "openai", providerReceiptId: "span-provider-1", lineageId: "lin-1",
  traceId: "trace-1", spanId: "span-1", parentSpanId: null, name: "model.invoke", kind: "model", status: "ok",
  producerStartedAt: "2026-08-12T01:00:00Z", producerEndedAt: "2026-08-12T01:00:01Z", observedAt: "2026-08-12T01:00:02Z",
  attributesHash: "c".repeat(64), sourceHash: "d".repeat(64), quality: "measured", ingestedAt: "2026-08-12T01:00:03Z",
};

const usage = {
  receiptId: "usage-1", provider: "openai", providerReceiptId: "usage-provider-1", lineageId: "lin-1",
  usageKind: "input_token", quantity: 100, unit: "token", currency: null, quality: "measured",
  sourceHash: "e".repeat(64), observedAt: "2026-08-12T01:00:02Z",
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

  it("通过唯一 AIP client 读取同一 lineage 的 spans 与 usage", async () => {
    const request = vi.fn().mockResolvedValueOnce([span]).mockResolvedValueOnce([usage]);
    const sdk = new AipEvidenceSdk({ request } as unknown as AipClient);
    await expect(sdk.spans("lin-1")).resolves.toMatchObject([{ spanRecordId: "span-record-1" }]);
    await expect(sdk.usage("lin-1")).resolves.toMatchObject([{ receiptId: "usage-1", quantity: 100 }]);
    expect(request).toHaveBeenNthCalledWith(1, "listTelemetrySpans", { params: { lineage_id: "lin-1" } });
    expect(request).toHaveBeenNthCalledWith(2, "listUsageReceipts", { params: { lineage_id: "lin-1" } });
  });

  it("跨 lineage、重复 provider receipt 与 usage 质量伪造失败关闭", () => {
    expect(() => parseTelemetrySpans([{ ...span, lineageId: "other" }], "lin-1")).toThrow("lineageId 不匹配");
    expect(() => parseTelemetrySpans([span, { ...span, spanRecordId: "span-record-2" }])).toThrow("重复 provider receipt");
    expect(() => parseUsageReceipts([{ ...usage, quality: "unknown", quantity: 0 }])).toThrow("quantity/quality 不一致");
    expect(() => parseUsageReceipts([{ ...usage, usageKind: "cost", currency: null }])).toThrow("currency/usageKind 不一致");
  });
});
