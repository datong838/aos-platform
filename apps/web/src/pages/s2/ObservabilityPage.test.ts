// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TelemetrySpan, UsageReceipt } from "../../api/aipEvidence/contracts";
import { filterAuthoritySpans, formatSpanDuration, formatUsageQuantity, missingAuthorityReason, ObservabilityPage, parseObservabilityDeepLink, summarizeAuthority } from "./ObservabilityPage";

const evidenceMocks = vi.hoisted(() => ({ spans: vi.fn(), usage: vi.fn(), evidenceChain: vi.fn() }));
const actionMocks = vi.hoisted(() => ({ list: vi.fn() }));
const workbenchMocks = vi.hoisted(() => ({ listAssistSubjects: vi.fn() }));
vi.mock("../../api/aipEvidence", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/aipEvidence")>();
  return { ...original, aipEvidenceSdk: { spans: evidenceMocks.spans, usage: evidenceMocks.usage, evidenceChain: evidenceMocks.evidenceChain } };
});
vi.mock("../../api/aipActions", () => ({ aipActionsSdk: actionMocks }));
vi.mock("../../api/aipWorkbench", () => ({ listAssistSubjects: workbenchMocks.listAssistSubjects }));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

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
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    evidenceMocks.spans.mockReset();
    evidenceMocks.usage.mockReset();
    evidenceMocks.evidenceChain.mockReset();
    actionMocks.list.mockReset();
    actionMocks.list.mockResolvedValue({ items: [], count: 0 });
    workbenchMocks.listAssistSubjects.mockReset();
    workbenchMocks.listAssistSubjects.mockResolvedValue({ tenant: { orgId: "org-org", projectId: "dev-project" }, items: [], count: 0 });
    window.history.replaceState({}, "", "/aip/observability");
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

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

  it("只接受 canonical lineageId 深链，并要求 rootType/rootId 成对出现", () => {
    expect(parseObservabilityDeepLink("?lineageId=lin-1&rootType=task_run&rootId=run-1")).toEqual({
      lineageId: "lin-1", rootType: "task_run", rootId: "run-1",
    });
    expect(parseObservabilityDeepLink("?trace=trace-1&rootType=unknown&rootId=x")).toEqual({
      lineageId: "", rootType: null, rootId: "",
    });
  });

  it("Span/Usage 空记录显示缺证原因，不解释成业务数量 0", () => {
    expect(missingAuthorityReason("span", 0)).toContain("不是业务数量 0");
    expect(missingAuthorityReason("usage", 0)).toContain("不是 Token 或费用 0");
    expect(missingAuthorityReason("usage", 2)).toBeNull();
  });

  it("从 exact URL 自动读取同一 lineage，并保留 root 回链和分项缺证状态", async () => {
    window.history.replaceState({}, "", "/aip/observability?lineageId=lin-1&rootType=task_run&rootId=run-1");
    evidenceMocks.spans.mockResolvedValue([]);
    evidenceMocks.usage.mockResolvedValue([receipt()]);
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(ObservabilityPage))));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(evidenceMocks.spans).toHaveBeenCalledWith("lin-1");
    expect(evidenceMocks.usage).toHaveBeenCalledWith("lin-1");
    expect(host.textContent).toContain("当前权威 Lineage 尚未写入 Telemetry Span");
    expect(host.textContent).toContain("已写入 1 条权威用量凭证");
    expect(host.querySelector<HTMLAnchorElement>("[data-testid='observability-back-lineage']")?.getAttribute("href"))
      .toBe("/aip/lineage?rootType=task_run&rootId=run-1");
    expect(host.querySelector<HTMLButtonElement>("[data-testid='observability-export']")?.disabled).toBe(false);
  });

  it("从最近任务运行解析 exact lineage 并展示业务诊断入口", async () => {
    workbenchMocks.listAssistSubjects.mockResolvedValue({ tenant: { orgId: "org-org", projectId: "dev-project" }, items: [{
      subject: {
        taskRef: { resourceType: "Task", resourceId: "task-1", revision: "1", authority: "aip-task-store" },
        taskRunRef: { resourceType: "TaskRun", resourceId: "run-1", revision: "1", authority: "aip-task-store" },
        agentRunRef: { resourceType: "AgentRun", resourceId: "agent-run-1", revision: "1", authority: "aip-agent-run-store" },
        selectionRefs: [], cutoffAt: "2026-08-31T01:00:00Z",
      }, taskTitle: "复核价格异常", taskDescription: "", owner: "价格运营", taskStatus: "executing", runStatus: "running", agentStatus: "running", source: "task", updatedAt: "2026-08-31T01:00:00Z",
    }], count: 1 });
    evidenceMocks.evidenceChain.mockResolvedValue({ rootType: "task_run", rootId: "run-1", lineageId: "lin-1", events: [], spans: [span()], usageReceipts: [receipt()] });
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(ObservabilityPage))));
    await vi.waitFor(() => expect(host.textContent).toContain("复核价格异常"));
    const picker = host.querySelector<HTMLSelectElement>("[aria-label='observability-task-run-record']")!;
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set?.call(picker, "run-1");
    await act(async () => picker.dispatchEvent(new Event("change", { bubbles: true })));
    const query = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "查看运行证据")!;
    await act(async () => query.click());
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(evidenceMocks.evidenceChain).toHaveBeenCalledWith("task_run", "run-1");
    expect(host.textContent).toContain("预算约束");
    expect(host.textContent).toContain("告警处置");
    expect(host.querySelector<HTMLAnchorElement>("[data-testid='observability-back-lineage']")?.getAttribute("href")).toBe("/aip/lineage?rootType=task_run&rootId=run-1");
  });
});
