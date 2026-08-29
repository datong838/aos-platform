import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CURRENT_CASE_LIST_FIXTURE } from "../../api/integrationCases/fixtures";
import { normalizeIntegrationCaseError } from "../../api/integrationCases/errors";
import type { IntegrationCasesReadModel } from "./integrationCases/integrationCaseViewModel";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const useReadModel = vi.fn();

vi.mock("./integrationCases/useIntegrationCasesReadModel", () => ({
  useIntegrationCasesReadModel: (options: unknown) => useReadModel(options),
}));

import { IntegrationCasesPage } from "./IntegrationCasesPage";
import { businessCaseName } from "./integrationCases/IntegrationCaseCatalog";

function state<T>(data: T | null, status: "idle" | "loading" | "ready" | "empty" | "forbidden" | "not_visible_or_missing" | "error" | "stale" | "refreshing" = "ready") {
  return { data, status, error: null };
}

function model(overrides: Partial<IntegrationCasesReadModel> = {}): IntegrationCasesReadModel {
  return {
    scope: "current",
    selectedCaseId: null,
    selectCase: vi.fn(),
    list: state(CURRENT_CASE_LIST_FIXTURE),
    detail: state(null, "idle"),
    timeline: state(null, "idle"),
    visibleItems: CURRENT_CASE_LIST_FIXTURE.items,
    refreshList: vi.fn(),
    refreshDetail: vi.fn(),
    refreshTimeline: vi.fn(),
    refreshAll: vi.fn(),
    ...overrides,
  };
}

describe("IntegrationCasesPage", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    useReadModel.mockReturnValue(model());
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    vi.clearAllMocks();
  });

  async function renderPage() {
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(IntegrationCasesPage)));
    });
  }

  it("只展示服务端统计与案例，不含旧静态平台事实", async () => {
    await renderPage();
    expect(host.textContent).toContain(CURRENT_CASE_LIST_FIXTURE.items[0].displayName);
    expect(host.textContent).toContain(`服务端返回 ${CURRENT_CASE_LIST_FIXTURE.total} 个当前案例`);
    expect(host.textContent).not.toContain("9 个平台案例");
    expect(host.textContent).not.toContain("G1-G10 公共阻塞项");
    expect(host.textContent).not.toContain("日均 1.2M 行");
  });

  it("业务标题不展示开发编号，精确标识不进入目录首屏", async () => {
    const item = CURRENT_CASE_LIST_FIXTURE.items[0];
    const pollutedName = `${item.displayName}（D3：W03 客户台 + L05 分润异常）`;
    expect(businessCaseName(pollutedName)).toBe(`${item.displayName}（客户台与分润异常）`);
    expect(businessCaseName(`${item.displayName}（D3：叠加：decision_tag 注入）`)).toBe(`${item.displayName}（叠加：决策标签配置）`);
    useReadModel.mockReturnValue(model({
      list: state({ ...CURRENT_CASE_LIST_FIXTURE, items: [{ ...item, displayName: pollutedName }] }),
      visibleItems: [{ ...item, displayName: pollutedName }],
    }));
    await renderPage();
    expect(host.textContent).toContain(item.displayName);
    expect(host.textContent).not.toContain("D3");
    expect(host.textContent).not.toContain("W03");
    expect(host.textContent).not.toContain(item.caseId);
  });

  it("scope 切换清空筛选并交给 read model 清理选择", async () => {
    await renderPage();
    const input = host.querySelector<HTMLInputElement>('input[aria-label="筛选接入案例"]')!;
    await act(async () => {
      input.value = "demo";
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const reference = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("脱敏参考"))!;
    await act(async () => reference.click());
    expect(useReadModel).toHaveBeenLastCalledWith(expect.objectContaining({ scope: "reference", filter: "" }));
  });

  it("选择目录项只调用 read model，不在页面推断阶段", async () => {
    const readModel = model();
    useReadModel.mockReturnValue(readModel);
    await renderPage();
    const item = CURRENT_CASE_LIST_FIXTURE.items[0];
    const button = host.querySelector<HTMLButtonElement>(`button[data-case-id="${item.caseId}"]`)!;
    await act(async () => button.click());
    expect(readModel.selectCase).toHaveBeenCalledWith(item.caseId);
  });

  it("刷新失败保留服务端事实并明确标记 stale", async () => {
    useReadModel.mockReturnValue(model({
      list: {
        data: CURRENT_CASE_LIST_FIXTURE,
        status: "stale",
        error: normalizeIntegrationCaseError(new Error("连接失败")),
      },
    }));
    await renderPage();
    expect(host.textContent).toContain("最后一次服务端事实");
    expect(host.textContent).toContain(CURRENT_CASE_LIST_FIXTURE.items[0].displayName);
  });

  it("无权状态不渲染旧目录且可重试", async () => {
    const refreshList = vi.fn();
    useReadModel.mockReturnValue(model({
      list: state(null, "forbidden"),
      visibleItems: [],
      refreshList,
    }));
    await renderPage();
    expect(host.textContent).toContain("无权读取接入案例");
    expect(host.textContent).not.toContain(CURRENT_CASE_LIST_FIXTURE.items[0].displayName);
    const retry = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "重试")!;
    await act(async () => retry.click());
    expect(refreshList).toHaveBeenCalledTimes(1);
  });
});
