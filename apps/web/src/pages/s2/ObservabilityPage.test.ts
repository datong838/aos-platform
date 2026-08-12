import { describe, expect, it } from "vitest";

import type { TelemetrySpan, UsageReceipt } from "../../api/aipEvidence/contracts";
import { filterAuthoritySpans, formatSpanDuration, formatUsageQuantity, summarizeAuthority } from "./ObservabilityPage";

const span = (overrides: Partial<TelemetrySpan> = {}): TelemetrySpan => ({
  spanRecordId: "span-record-1",
  provider: "openai",
  providerReceiptId: "provider-span-1",
  lineageId: "lin-1",
  traceId: "trace-1",
  spanId: "span-1",
  parentSpanId: null,
  name: "model.invoke",
  kind: "model",
  status: "ok",
  producerStartedAt: "2026-08-12T01:00:00.000Z",
  producerEndedAt: "2026-08-12T01:00:01.250Z",
  observedAt: "2026-08-12T01:00:02Z",
  attributesHash: "a".repeat(64),
  sourceHash: "b".repeat(64),
  quality: "measured",
  ingestedAt: "2026-08-12T01:00:03Z",
  ...overrides,
});

const receipt = (overrides: Partial<UsageReceipt> = {}): UsageReceipt => ({
  receiptId: "usage-1",
  provider: "openai",
  providerReceiptId: "provider-usage-1",
  lineageId: "lin-1",
  usageKind: "input_token",
  quantity: 120,
  unit: "token",
  currency: null,
  quality: "measured",
  sourceHash: "c".repeat(64),
  observedAt: "2026-08-12T01:00:02Z",
  ...overrides,
});

describe("AIP 权威可观测性", () => {
  it("只按权威记录计数，并分别保留 measured/estimated/unknown", () => {
    expect(summarizeAuthority(
      [span(), span({ spanRecordId: "span-record-2", providerReceiptId: "provider-span-2", status: "error", quality: "estimated" })],
      [receipt({ quality: "unknown", quantity: null })],
    )).toEqual({
      spanCount: 2,
      errorSpanCount: 1,
      usageReceiptCount: 1,
      measuredCount: 1,
      estimatedCount: 1,
      unknownCount: 1,
    });
  });

  it("未知用量不伪造为 0，实测用量保持单位", () => {
    expect(formatUsageQuantity(receipt({ quality: "unknown", quantity: null }))).toBe("未知（未伪造 0）");
    expect(formatUsageQuantity(receipt())).toBe("120 token");
    expect(formatUsageQuantity(receipt({ usageKind: "cost", quantity: 1.25, unit: "currency", currency: "CNY" }))).toBe("CNY 1.25");
  });

  it("Span 时长只由生产者时间计算，缺少结束时间保持未知", () => {
    expect(formatSpanDuration(span())).toBe("1.25s");
    expect(formatSpanDuration(span({ producerEndedAt: null }))).toBe("未知");
    expect(formatSpanDuration(span({ producerEndedAt: "2026-08-12T00:59:59Z" }))).toBe("无效");
  });

  it("过滤匹配 trace/span/provider/name/kind/status", () => {
    const spans = [span(), span({ spanRecordId: "span-record-2", providerReceiptId: "provider-span-2", traceId: "trace-2", name: "tool.call", kind: "tool", provider: "browser" })];
    expect(filterAuthoritySpans(spans, "BROWSER")).toHaveLength(1);
    expect(filterAuthoritySpans(spans, "trace-1")).toHaveLength(1);
    expect(filterAuthoritySpans(spans, "")).toHaveLength(2);
  });
});
