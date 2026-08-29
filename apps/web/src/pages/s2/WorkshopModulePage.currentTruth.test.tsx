// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const api = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn(), apiDelete: vi.fn() }));
vi.mock("../../api/client", () => api);
import { WorkshopModulePage } from "./WorkshopModulePage";

describe("WorkshopModulePage current truth", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => {
    api.apiGet.mockResolvedValue({ items: [{ id: "mod-1", name: "库存协同台", description: "库存核验", category: "供应链", status: "draft", widgets: ["table", "filters"] }] });
    host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.clearAllMocks(); });

  it("按真实回包展示分类与组件数且发布先确认", async () => {
    await act(async () => root.render(<MemoryRouter><WorkshopModulePage /></MemoryRouter>));
    await act(async () => void await Promise.resolve());
    expect(host.textContent).toContain("供应链");
    expect(host.textContent).toContain("组件数");
    expect(host.textContent).toContain("2");
    expect(host.textContent).toContain("事件数");
    expect(host.textContent).toContain("未读取");
    const publish = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "发布")!;
    await act(async () => publish.click());
    expect(host.textContent).toContain("确认发布");
    expect(api.apiPost).not.toHaveBeenCalled();
    await act(async () => Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "取消")!.click());
    expect(api.apiPost).not.toHaveBeenCalled();
  });
});
