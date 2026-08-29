import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { normalizeIntegrationCaseError } from "../../../api/integrationCases/errors";
import {
  CURRENT_CASE_DETAIL_FIXTURE,
  HASH_A,
  HASH_B,
  REFERENCE_CASE_DETAIL_FIXTURE,
} from "../../../api/integrationCases/fixtures";
import type { IntegrationCaseDetail as IntegrationCaseDetailResponse } from "../../../api/integrationCases/types";
import {
  IntegrationCaseDetail,
  type IntegrationCaseReadViewState,
} from "./IntegrationCaseDetail";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function state(
  overrides: Partial<IntegrationCaseReadViewState<IntegrationCaseDetailResponse>> = {},
): IntegrationCaseReadViewState<IntegrationCaseDetailResponse> {
  return { data: CURRENT_CASE_DETAIL_FIXTURE, status: "ready", error: null, ...overrides };
}

describe("IntegrationCaseDetail", () => {
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
    value: IntegrationCaseReadViewState<IntegrationCaseDetailResponse> = state(),
    onRetry = vi.fn(),
  ) {
    await act(async () => root.render(<IntegrationCaseDetail state={value} onRetry={onRetry} />));
    return onRetry;
  }

  it("首屏展示中文阶段摘要，技术阶段门与证据默认折叠", async () => {
    await render();

    expect(host.textContent).toContain("当前阶段连接已验证");
    expect(host.textContent).toContain("已满足阶段 2 / 8；待处理事项 1 项");
    expect(host.querySelector<HTMLDetailsElement>('details[aria-label="阶段门与证据审计详情"]')?.open).toBe(false);
    expect(host.querySelectorAll("[data-stage]")).toHaveLength(8);
    expect(host.querySelector('[data-stage="data_verified"]')?.getAttribute("data-gate-status")).toBe("blocked");
    expect(host.textContent).toContain("MISSING_PIPELINE_RUN");
    expect(host.textContent).toContain("missing:pipeline_run");
    expect(host.textContent).toContain("source_connection");
    expect(host.textContent).toContain("connector:commerce-primary");
    expect(host.textContent).toContain(HASH_A);
    expect(host.textContent).toContain(HASH_B);
    expect(host.textContent).toContain("页面不据此重算或推断阶段");
    expect(host.textContent).toContain("页面不自行计算阶段");
    expect(host.querySelectorAll("input, textarea, select")).toHaveLength(0);
  });

  it("current 可展示服务端租户引用但不展示 metrics 或 Evidence 原文", async () => {
    await render();

    expect(host.textContent).toContain(CURRENT_CASE_DETAIL_FIXTURE.owner);
    expect(host.textContent).toContain(CURRENT_CASE_DETAIL_FIXTURE.installationId);
    expect(host.textContent).toContain(CURRENT_CASE_DETAIL_FIXTURE.overlayRevision);
    expect(host.textContent).toContain(CURRENT_CASE_DETAIL_FIXTURE.compositionId);
    expect(host.textContent).toContain(CURRENT_CASE_DETAIL_FIXTURE.lockHash);
    expect(host.textContent).not.toContain("datasetRowCount");
    expect(host.textContent).not.toContain("latencyMs");
    expect(host.textContent).not.toContain("raw-claim-value");
    expect(host.textContent).not.toContain("actor@example.test");
  });

  it("reference 严格隐藏 current 专属引用、blocker owner 与统计", async () => {
    const hiddenOwner = "subject:must-not-leak";
    const reference = {
      ...REFERENCE_CASE_DETAIL_FIXTURE,
      blockers: [{
        blockerId: "00000000-0000-4000-8000-000000000199",
        code: "REFERENCE_BLOCKER",
        severity: "medium" as const,
        status: "open" as const,
        gate: "production_ready" as const,
        reasonRefs: ["reference:reason"],
        evidenceRefs: [],
        owner: hiddenOwner,
        firstObservedAt: "2026-08-03T08:00:00+00:00",
        updatedAt: "2026-08-03T09:00:00+00:00",
      }],
    };
    await render(state({ data: reference }));

    expect(host.textContent).toContain("独立脱敏参考副本");
    expect(host.textContent).toContain("REFERENCE_BLOCKER");
    expect(host.textContent).not.toContain(hiddenOwner);
    expect(host.querySelector('[aria-label="当前租户引用"]')).toBeNull();
    expect(host.textContent).not.toContain("subject:case-owner-001");
    expect(host.textContent).not.toContain("00000000-0000-4000-8000-000000000103");
    expect(host.textContent).not.toContain("overlay-7");
    expect(host.textContent).not.toContain("connectorCount");
  });

  it("详情 loading、empty、error、stale、refreshing 独立呈现且非披露态不残留数据", async () => {
    await render(state({ data: null, status: "loading" }));
    expect(host.textContent).toContain("正在读取接入案例详情");

    await render(state({ data: null, status: "empty" }));
    expect(host.textContent).toContain("服务端未返回接入案例详情");

    const network = normalizeIntegrationCaseError({ status: 0, body: { code: "NETWORK" } });
    await render(state({ data: CURRENT_CASE_DETAIL_FIXTURE, status: "error", error: network }));
    expect(host.textContent).toContain("无法读取接入案例");
    expect(host.textContent).not.toContain(CURRENT_CASE_DETAIL_FIXTURE.displayName);

    await render(state({ status: "stale", error: network }));
    expect(host.textContent).toContain("最后一次成功读取的服务端事实");
    expect(host.textContent).toContain(CURRENT_CASE_DETAIL_FIXTURE.displayName);

    await render(state({ status: "refreshing" }));
    expect(host.textContent).toContain("正在刷新接入案例详情");
    expect(host.textContent).toContain(CURRENT_CASE_DETAIL_FIXTURE.displayName);

    await render(state({ status: "not_visible_or_missing" }));
    expect(host.textContent).toContain("不区分不存在与不可见");
    expect(host.textContent).not.toContain(CURRENT_CASE_DETAIL_FIXTURE.displayName);
  });

  it("重试只调用父层回调且组件没有 mutation", async () => {
    const retry = await render(state({ data: null, status: "empty" }));
    const button = host.querySelector("button");
    expect(button?.textContent).toBe("重试读取");
    await act(async () => button?.click());
    expect(retry).toHaveBeenCalledTimes(1);
    expect(host.querySelectorAll("button")).toHaveLength(1);
  });
});
