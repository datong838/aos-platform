// @vitest-environment jsdom

import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ModuleInterfacePage } from "./ModuleInterfacePage";
import { DraftInboxPage } from "../DraftInboxPage";
import { AipAnalystPage } from "./AipAnalystPage";

const apiMocks = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn(), apiPut: vi.fn(), apiDelete: vi.fn() }));
const ontologyMocks = vi.hoisted(() => ({ listDrafts: vi.fn(), approveDraft: vi.fn(), rejectDraft: vi.fn() }));
const actionMocks = vi.hoisted(() => ({ list: vi.fn(), timeline: vi.fn(), execution: vi.fn() }));

vi.mock("../../api/client", () => apiMocks);
vi.mock("../../api/ontologyClient", () => ({ getOntologyClient: () => ontologyMocks }));
vi.mock("../../api/aipActions", () => ({ aipActionsSdk: actionMocks }));
vi.mock("./shared", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./shared")>();
  return { ...actual, apiGet: apiMocks.apiGet, apiPost: apiMocks.apiPost, apiPut: apiMocks.apiPut };
});

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("Wave 3B W1 · 页面交互真实性", () => {
  let host: HTMLDivElement;
  let root: Root;

  async function flush() {
    await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); });
  }

  beforeEach(() => {
    host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
    Object.values(apiMocks).forEach((mock) => mock.mockReset());
    Object.values(ontologyMocks).forEach((mock) => mock.mockReset());
    Object.values(actionMocks).forEach((mock) => mock.mockReset());
    localStorage.clear();
  });

  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("Module Interface 读取失败后进入只读且保存禁用", async () => {
    apiMocks.apiGet.mockImplementation((path: string) => path === "/v1/modules"
      ? Promise.resolve({ items: [{ id: "m1", name: "M1" }] })
      : Promise.reject(new Error("interface unavailable")));
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(ModuleInterfacePage))));
    await flush();
    expect(host.textContent).toContain("当前为空态或上次成功快照，仅供只读");
    const save = Array.from(host.querySelectorAll("button")).find((b) => b.textContent?.includes("保存接口"));
    expect(save?.disabled).toBe(true);
    expect(apiMocks.apiPut).not.toHaveBeenCalled();
  });

  it("Module Interface 无真实应用时禁用编辑且不补造规划事实", async () => {
    apiMocks.apiGet.mockResolvedValue({ items: [] });
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(ModuleInterfacePage))));
    await flush();

    const inputs = Array.from(host.querySelectorAll<HTMLInputElement>("input"));
    expect(inputs.every((input) => input.disabled)).toBe(true);
    const addButtons = Array.from(host.querySelectorAll<HTMLButtonElement>("button"))
      .filter((button) => button.textContent?.includes("入参") || button.textContent?.includes("出参"));
    expect(addButtons.every((button) => button.disabled)).toBe(true);
    expect(host.textContent).toContain("请先新建或选择真实应用");
    expect(host.textContent).not.toContain("维修 Inbox");
    expect(host.textContent).not.toContain("风险告警管理");
    expect(host.textContent).not.toContain("工单列表行");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
    expect(apiMocks.apiPut).not.toHaveBeenCalled();
  });

  it("canonical Draft 服务失败时不注入旧 Mock，也不开放本地写按钮", async () => {
    actionMocks.list.mockRejectedValue(new Error("action authority unavailable"));
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(DraftInboxPage))));
    await flush();
    expect(host.textContent).toContain("Action 服务不可用：action authority unavailable");
    expect(host.textContent).not.toContain("纯度异常");
    expect(Array.from(host.querySelectorAll("button")).some((button) => button.textContent?.includes("批准精确版本"))).toBe(false);
  });

  it("Analyst 初始为空且仅开放受治理真实查询，不注入 SQL 或本地草稿", async () => {
    const listObjectTypes = vi.fn().mockResolvedValue([{ id: "Order", name: "订单" }]);
    const listLogicGraphs = vi.fn().mockResolvedValue([]);
    await act(async () => root.render(<MemoryRouter><AipAnalystPage listObjectTypes={listObjectTypes} listLogicGraphs={listLogicGraphs} /></MemoryRouter>));
    await flush();
    expect(host.textContent).toContain("选择业务对象开始查询");
    expect(host.textContent).toContain("不接受任意 SQL");
    expect(host.textContent).not.toContain("Walter and Sons");
    expect(host.textContent).not.toContain("Northampton");
    expect(host.textContent).not.toContain("未保存的本地草稿");
    expect(host.querySelector('[data-testid="sql-editor"]')).toBeNull();
    const run = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("运行真实查询"));
    expect(run).toBeDefined();
    expect(run?.disabled).toBe(true);
    expect(host.textContent).toContain("六角色模板读取失败");
  });
});
