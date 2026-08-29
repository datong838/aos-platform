import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { normalizeIntegrationCaseError } from "../../../api/integrationCases/errors";
import { HASH_A, HASH_B, TIMELINE_FIXTURE } from "../../../api/integrationCases/fixtures";
import type { IntegrationCaseTimelineResponse } from "../../../api/integrationCases/types";
import type { IntegrationCaseReadViewState } from "./IntegrationCaseDetail";
import { IntegrationCaseTimeline } from "./IntegrationCaseTimeline";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function state(
  overrides: Partial<IntegrationCaseReadViewState<IntegrationCaseTimelineResponse>> = {},
): IntegrationCaseReadViewState<IntegrationCaseTimelineResponse> {
  return { data: TIMELINE_FIXTURE, status: "ready", error: null, ...overrides };
}

describe("IntegrationCaseTimeline", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  async function render(
    value: IntegrationCaseReadViewState<IntegrationCaseTimelineResponse> = state(),
    onRetry = vi.fn(),
  ) {
    await act(async () => root.render(<IntegrationCaseTimeline state={value} onRetry={onRetry} />));
    return onRetry;
  }

  it("只按服务端阶段事件展示且审计明细默认折叠", async () => {
    await render();

    expect(host.querySelectorAll("[data-event-sequence]")).toHaveLength(2);
    expect(host.textContent).toContain("无前序阶段 → planned");
    expect(host.textContent).toContain("planned → connection_verified");
    expect(host.textContent).toContain("created");
    expect(host.textContent).toContain("evidence_added");
    expect(host.textContent).toContain(HASH_A);
    expect(host.textContent).toContain(HASH_B);
    expect(host.textContent).toContain("事件序列不用于推断未返回的阶段或证据");
    expect(host.querySelector<HTMLDetailsElement>('details[aria-label="阶段事件审计详情"]')?.open).toBe(false);
    expect(host.querySelectorAll("input, textarea, select")).toHaveLength(0);
  });

  it("服务端 ready 空页与请求 empty 是不同状态", async () => {
    await render(state({ data: { ...TIMELINE_FIXTURE, items: [], total: 0 } }));
    expect(host.textContent).toContain("服务端尚未返回阶段事件");
    expect(host.textContent).not.toContain(TIMELINE_FIXTURE.caseId);

    await render(state({ data: null, status: "empty" }));
    expect(host.textContent).toContain("服务端未返回阶段事件时间线");
    expect(host.textContent).not.toContain(TIMELINE_FIXTURE.caseId);
  });

  it("时间线 loading、error、stale、refreshing 独立呈现并避免错误态残留", async () => {
    await render(state({ data: null, status: "loading" }));
    expect(host.textContent).toContain("正在读取阶段事件");

    const integrity = normalizeIntegrationCaseError({
      status: 500,
      body: { code: "EVIDENCE_INTEGRITY_CORRUPT", message: "raw detail", details: null, traceId: "trace-1" },
    });
    await render(state({ status: "error", error: integrity }));
    expect(host.textContent).toContain("EVIDENCE_INTEGRITY_CORRUPT");
    expect(host.textContent).toContain("读取已失败关闭");
    expect(host.textContent).not.toContain(TIMELINE_FIXTURE.caseId);
    expect(host.textContent).not.toContain("raw detail");

    await render(state({ status: "stale", error: integrity }));
    expect(host.textContent).toContain("最后一次成功读取的服务端事实");
    expect(host.textContent).toContain(TIMELINE_FIXTURE.caseId);

    await render(state({ status: "refreshing", error: null }));
    expect(host.textContent).toContain("正在刷新阶段事件");
    expect(host.textContent).toContain(TIMELINE_FIXTURE.caseId);

    await render(state({ status: "forbidden" }));
    expect(host.textContent).toContain("无权查看阶段事件");
    expect(host.textContent).not.toContain(TIMELINE_FIXTURE.caseId);
  });

  it("时间线重试只调用父层回调", async () => {
    const retry = await render(state({ data: null, status: "empty" }));
    await act(async () => host.querySelector("button")?.click());
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
