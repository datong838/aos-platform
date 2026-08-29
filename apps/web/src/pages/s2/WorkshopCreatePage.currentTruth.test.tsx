// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const apiPost = vi.hoisted(() => vi.fn());
vi.mock("../../api/client", () => ({ apiPost }));

import { WorkshopCreatePage } from "./WorkshopCreatePage";

describe("WorkshopCreatePage current contract", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.clearAllMocks(); });

  async function renderAndFill() {
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/workshop/create"]}>
        <Routes>
          <Route path="/workshop/create" element={<WorkshopCreatePage />} />
          <Route path="/workshop/canvas" element={<h1>画布编辑器</h1>} />
        </Routes>
      </MemoryRouter>,
    ));
    const name = host.querySelector<HTMLInputElement>('[data-testid="create-app-name"]')!;
    await act(async () => {
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")!.set!.call(name, "库存协同台");
      name.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => host.querySelector<HTMLButtonElement>('[data-testid="create-step-nav-4"]')!.click());
  }

  it("服务端失败时留在当前页且不生成模拟应用", async () => {
    apiPost.mockRejectedValue(new Error("当前工作区无创建权限"));
    await renderAndFill();
    await act(async () => host.querySelector<HTMLButtonElement>('[data-testid="create-btn-finish"]')!.click());
    await act(async () => void await Promise.resolve());
    expect(host.textContent).toContain("创建失败：当前工作区无创建权限");
    expect(host.querySelector("h1")?.textContent).toBe("新建应用");
    expect(JSON.stringify(apiPost.mock.calls)).not.toContain("mod-mock");
  });

  it("成功时提交后端真实字段并按返回 id 进入画布", async () => {
    apiPost.mockResolvedValue({ id: "mod-real-1" });
    await renderAndFill();
    await act(async () => host.querySelector<HTMLButtonElement>('[data-testid="create-btn-finish"]')!.click());
    await act(async () => void await Promise.resolve());
    expect(apiPost).toHaveBeenCalledWith("/v1/modules", expect.objectContaining({
      name: "库存协同台", objectType: "Order", category: "供应链", widgets: ["filters", "table", "details"],
    }));
    expect(host.textContent).toContain("画布编辑器");
  });
});
