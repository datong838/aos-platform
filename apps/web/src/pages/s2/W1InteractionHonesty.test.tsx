import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ModuleInterfacePage } from "./ModuleInterfacePage";
import { DraftInboxPage } from "../DraftInboxPage";
import { AipAnalystPage } from "./AipAnalystPage";

const apiMocks = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn(), apiPut: vi.fn(), apiDelete: vi.fn() }));
const ontologyMocks = vi.hoisted(() => ({ listDrafts: vi.fn(), approveDraft: vi.fn(), rejectDraft: vi.fn() }));

vi.mock("../../api/client", () => apiMocks);
vi.mock("../../api/ontologyClient", () => ({ getOntologyClient: () => ontologyMocks }));
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

  it("Draft live 模式禁用无 PG 契约的评论与退回修改", async () => {
    ontologyMocks.listDrafts.mockResolvedValue({ items: [{ id: "d1", title: "D1", status: "proposed", createdBy: "u", proposed: { status: "closed" } }] });
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(DraftInboxPage))));
    await flush();
    const comment = Array.from(host.querySelectorAll("button")).find((b) => b.textContent?.includes("添加评论"));
    const change = Array.from(host.querySelectorAll("button")).find((b) => b.textContent?.includes("退回修改"));
    expect(comment?.disabled).toBe(true);
    expect(change?.disabled).toBe(true);
    expect(host.textContent).toContain("审批历史 API 未提供");
  });

  it("Analyst 初始为空，新建后仍无伪结果且可见未保存状态", async () => {
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(AipAnalystPage))));
    expect(host.textContent).toContain("未运行查询");
    expect(host.textContent).not.toContain("Walter and Sons");
    const button = host.querySelector('[data-testid="btn-new-query"]') as HTMLButtonElement;
    await act(async () => button.click());
    expect((host.querySelector('[data-testid="sql-editor"]') as HTMLTextAreaElement).value).toBe("SELECT * FROM ");
    expect(host.textContent).toContain("未保存的本地草稿");
  });
});
