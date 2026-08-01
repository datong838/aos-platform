import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { VariablesPage } from "./VariablesPage";

const api = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));

vi.mock("../../api/client", () => api);
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("Wave 3C W1 · Variables 交互诚实反馈", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    Object.values(api).forEach((mock) => mock.mockReset());
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    vi.restoreAllMocks();
  });

  async function flush() {
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
  }

  function button(label: string, exact = false): HTMLButtonElement {
    const found = Array.from(host.querySelectorAll("button")).find((item) =>
      exact ? item.textContent?.trim() === label : item.textContent?.includes(label),
    );
    if (!found) throw new Error(`button not found: ${label}`);
    return found;
  }

  function setInput(label: string, value: string) {
    const field = Array.from(host.querySelectorAll("label")).find((item) =>
      item.querySelector("span")?.textContent?.trim() === label,
    );
    const input = field?.querySelector("input") as HTMLInputElement | null;
    if (!input) throw new Error(`input not found: ${label}`);
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  async function renderDemo() {
    api.apiGet.mockRejectedValue(new Error("variables unavailable"));
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(VariablesPage))));
    await flush();
  }

  it("演示新建、编辑、删除每次都明确仅当前演示", async () => {
    await renderDemo();
    expect(host.querySelectorAll('[data-testid="demo-binding-source"]').length).toBeGreaterThan(0);

    await act(async () => button("新建变量").click());
    await act(async () => setInput("名称", "w3c_demo"));
    await act(async () => button("保存", true).click());
    expect(host.textContent).toContain("已在仅当前演示中新建变量，不写服务端");

    const row = Array.from(host.querySelectorAll("tr")).find((item) => item.textContent?.includes("w3c_demo"));
    const edit = row?.querySelector("button.vr-edit") as HTMLButtonElement | null;
    if (!edit) throw new Error("demo edit button not found");
    await act(async () => edit.click());
    await act(async () => setInput("名称", "w3c_demo_updated"));
    await act(async () => button("保存", true).click());
    expect(host.textContent).toContain("已在仅当前演示中编辑变量，不写服务端");

    const updatedRow = Array.from(host.querySelectorAll("tr")).find((item) => item.textContent?.includes("w3c_demo_updated"));
    const remove = updatedRow?.querySelector("button.vr-delete") as HTMLButtonElement | null;
    if (!remove) throw new Error("demo delete button not found");
    await act(async () => remove.click());
    expect(host.textContent).toContain("已在仅当前演示中删除变量，不写服务端");
    expect(api.apiPost).not.toHaveBeenCalled();
    expect(api.apiPut).not.toHaveBeenCalled();
    expect(api.apiDelete).not.toHaveBeenCalled();
  });

  it("live 写失败保留错误且不显示成功", async () => {
    api.apiGet.mockImplementation((path: string) => {
      if (path === "/v1/modules") return Promise.resolve({ items: [{ id: "m1", name: "M1" }] });
      return Promise.resolve({ items: [] });
    });
    api.apiPost.mockRejectedValue(new Error("write failed"));
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(VariablesPage))));
    await flush();

    await act(async () => button("新建变量").click());
    await act(async () => setInput("名称", "live_var"));
    await act(async () => button("保存", true).click());
    await flush();

    expect(host.textContent).toContain("write failed");
    expect(host.textContent).not.toContain("已在仅当前演示中");
  });
});
