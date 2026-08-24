import { describe, expect, it, vi } from "vitest";

import type { AipClient } from "../aip/client";
import { AipEvidenceSdk } from "./client";
import { parseEvidenceDisclosureDecision, parseLineageEvents, parseTelemetrySpans, parseUsageReceipts } from "./contracts";

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

const evalRun = {
  runId: "eval-run-1",
  suiteRef: { assetType: "eval_suite", assetId: "suite-1", revision: "2", contentHash: "1".repeat(64) },
  target: { assetType: "logic_graph", assetId: "logic-1", revision: "3", contentHash: "2".repeat(64) },
  dataset: {
    datasetId: "dataset-1", revision: 4, contentHash: "3".repeat(64), sourceHash: "4".repeat(64),
    redactionPolicy: { assetType: "policy", assetId: "redact-1", revision: "1", contentHash: "5".repeat(64) },
  },
  judge: { judgeId: "judge-1", revision: 2, contentHash: "6".repeat(64), modelRoute: null },
  status: "succeeded", idempotencyKey: "eval-once", createdBy: "user-1", createdAt: "2026-08-12T01:00:00Z",
  startedAt: "2026-08-12T01:00:01Z", finishedAt: "2026-08-12T01:00:02Z", version: 3,
};

const disclosure = {
  tenant: { orgId: "org-org", projectId: "dev-project" },
  decisionId: "disclosure-1",
  evidenceRef: { resourceType: "Evidence", resourceId: "evidence-1", revision: 1, contentHash: "7".repeat(64) },
  purpose: "summary", requestedLevel: "l1", grantedLevel: "l1", status: "allowed", reasons: [],
  citation: { auditRef: { resourceType: "EvidenceDisclosureDecision", resourceId: "disclosure-1", revision: 1 }, evidenceId: "evidence-1" },
  displayPayload: { layer: "l1", sourceType: "database", freshnessAt: "2026-08-25T01:00:00Z", marking: ["public"], licenseStatus: "internal_controlled" },
  redactionReceipt: { bodyReturned: true }, decisionHash: "8".repeat(64), expiresAt: null,
  createdBy: "user:dev", createdAt: "2026-08-25T01:00:01Z",
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

  it("按 exact root 组合读取 Lineage、Span 与 Usage，且只采用服务端 lineageId", async () => {
    const request = vi.fn()
      .mockResolvedValueOnce([event])
      .mockResolvedValueOnce([span])
      .mockResolvedValueOnce([usage]);
    const sdk = new AipEvidenceSdk({ request } as unknown as AipClient);
    await expect(sdk.evidenceChain("task_run", "run-1")).resolves.toMatchObject({
      rootType: "task_run",
      rootId: "run-1",
      lineageId: "lin-1",
      events: [{ eventId: "evt-1" }],
      spans: [{ spanRecordId: "span-record-1" }],
      usageReceipts: [{ receiptId: "usage-1" }],
    });
    expect(request).toHaveBeenNthCalledWith(1, "listLineageAuthority", { params: { root_type: "task_run", root_id: "run-1" } });
    expect(request).toHaveBeenNthCalledWith(2, "listTelemetrySpans", { params: { lineage_id: "lin-1" } });
    expect(request).toHaveBeenNthCalledWith(3, "listUsageReceipts", { params: { lineage_id: "lin-1" } });
  });

  it("exact root 没有 Lineage 时保持真实空链，不猜测 lineageId 或读取 Telemetry", async () => {
    const request = vi.fn().mockResolvedValueOnce([]);
    const sdk = new AipEvidenceSdk({ request } as unknown as AipClient);
    await expect(sdk.evidenceChain("action", "proposal-1")).resolves.toEqual({
      rootType: "action",
      rootId: "proposal-1",
      lineageId: null,
      events: [],
      spans: [],
      usageReceipts: [],
    });
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("跨 lineage、重复 provider receipt 与 usage 质量伪造失败关闭", () => {
    expect(() => parseTelemetrySpans([{ ...span, lineageId: "other" }], "lin-1")).toThrow("lineageId 不匹配");
    expect(() => parseTelemetrySpans([span, { ...span, spanRecordId: "span-record-2" }])).toThrow("重复 provider receipt");
    expect(() => parseUsageReceipts([{ ...usage, quality: "unknown", quantity: 0 }])).toThrow("quantity/quality 不一致");
    expect(() => parseUsageReceipts([{ ...usage, usageKind: "cost", currency: null }])).toThrow("currency/usageKind 不一致");
  });

  it("读取精确 AIP-4 EvalRun 权威引用，路径与 run id 一致", async () => {
    const request = vi.fn().mockResolvedValue(evalRun);
    const sdk = new AipEvidenceSdk({ request } as unknown as AipClient);
    await expect(sdk.evalRun("eval-run-1")).resolves.toMatchObject({
      runId: "eval-run-1",
      status: "succeeded",
      target: { revision: "3", contentHash: "2".repeat(64) },
    });
    expect(request).toHaveBeenCalledWith("getEvalAuthorityRun", { params: { run_id: "eval-run-1" } });
  });

  it("EvalRun 错配、非 eval_suite 与终态缺失 finishedAt 失败关闭", async () => {
    for (const malformed of [
      { ...evalRun, runId: "other" },
      { ...evalRun, suiteRef: { ...evalRun.suiteRef, assetType: "logic_graph" } },
      { ...evalRun, finishedAt: null },
    ]) {
      const sdk = new AipEvidenceSdk({ request: vi.fn().mockResolvedValue(malformed) } as unknown as AipClient);
      await expect(sdk.evalRun("eval-run-1")).rejects.toThrow();
    }
  });

  it("通过唯一 AIP client 解析 Disclosure 且自动提交幂等键", async () => {
    const request = vi.fn().mockResolvedValue(disclosure);
    const sdk = new AipEvidenceSdk({ request } as unknown as AipClient);
    await expect(sdk.resolveDisclosure({
      evidenceRef: disclosure.evidenceRef as { resourceType: "Evidence"; resourceId: string; revision: number; contentHash: string },
      purpose: "summary",
      requestedLevel: "l1",
    }, "disclosure-once")).resolves.toMatchObject({ decisionId: "disclosure-1", status: "allowed" });
    expect(request).toHaveBeenCalledWith("resolveEvidenceDisclosure", {
      body: expect.objectContaining({ purpose: "summary", requestedLevel: "l1" }),
      headers: { "Idempotency-Key": "disclosure-once" },
    });
    request.mockClear();
    await expect(sdk.getDisclosure("disclosure-1")).resolves.toMatchObject({ evidenceRef: { resourceId: "evidence-1" } });
    expect(request).toHaveBeenCalledWith("getEvidenceDisclosure", { params: { decision_id: "disclosure-1" } });
  });

  it("Disclosure 的审计引用、L2 对齐和失败关闭零正文均严格校验", () => {
    expect(() => parseEvidenceDisclosureDecision({ ...disclosure, status: "blocked", grantedLevel: null, reasons: ["DENIED"] })).toThrow("fail-closed");
    expect(() => parseEvidenceDisclosureDecision({ ...disclosure, citation: { auditRef: { resourceType: "EvidenceDisclosureDecision", resourceId: "other", revision: 1 } } })).toThrow("auditRef");
    const blocked = { ...disclosure, status: "blocked", grantedLevel: null, reasons: ["MARKING_ACCESS_DENIED"], displayPayload: {}, redactionReceipt: { bodyReturned: false } };
    expect(parseEvidenceDisclosureDecision(blocked)).toMatchObject({ status: "blocked", displayPayload: {} });
    const l2 = { ...disclosure, purpose: "excerpt", requestedLevel: "l2", grantedLevel: "l2", displayPayload: { layer: "l2", excerpt: "最小片段", locator: { row: "1" }, excerptHash: "9".repeat(64) }, citation: { ...disclosure.citation, excerptHash: "9".repeat(64) } };
    expect(parseEvidenceDisclosureDecision(l2)).toMatchObject({ grantedLevel: "l2" });
    expect(() => parseEvidenceDisclosureDecision({ ...l2, citation: { ...l2.citation, excerptHash: "a".repeat(64) } })).toThrow("L2 citation");
  });
});
