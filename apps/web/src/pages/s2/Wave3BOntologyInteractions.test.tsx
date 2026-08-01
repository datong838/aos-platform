import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FunctionEditorPage } from "./FunctionEditorPage";
import { PropertyEditorPage } from "./PropertyEditorPage";
import { WikiDetailPage } from "./WikiDetailPage";

const api = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));

vi.mock("../../api/client", () => api);
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("Wave 3B · Ontology 编辑器真实失败闭环", () => {
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

  function button(label: string): HTMLButtonElement {
    const found = Array.from(host.querySelectorAll("button"))
      .find((item) => item.textContent?.includes(label));
    if (!found) throw new Error(`button not found: ${label}`);
    return found;
  }

  it("Wiki PUT 已返回但 GET schema 错配时不显示保存成功", async () => {
    const wiki = {
      id: "wiki-1", title: "Wiki", content: "body", version: 1,
      widgets: [{ id: "w1", kind: "text", name: "正文", children: [], content: "body" }],
      variables: { x: "1" }, author: "tester",
    };
    api.apiGet.mockImplementation((path: string) => {
      if (path.endsWith("/versions")) return Promise.resolve({ items: [] });
      if (api.apiPut.mock.calls.length > 0) return Promise.resolve({ ...wiki, version: 2, widgets: [] });
      return Promise.resolve(wiki);
    });
    api.apiPut.mockResolvedValue({ ...wiki, version: 2 });

    await act(async () => root.render(createElement(
      MemoryRouter, { initialEntries: ["/ontology/wiki/wiki-1"] },
      createElement(Routes, null, createElement(Route, {
        path: "/ontology/wiki/:wikiId", element: createElement(WikiDetailPage),
      })),
    )));
    await flush();
    await act(async () => button("保存").click());
    await flush();

    expect(api.apiPut).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("写入已提交但重读核验失败");
    expect(host.textContent).not.toContain("已保存并重读");
  });

  it("Property DELETE 后 GET 仍存在时不移除属性、不显示成功", async () => {
    const property = {
      id: "prop-1", name: "amount", display_name: "Amount", datatype: "double",
      nullable: true, is_primary_key: false, is_display_name: false, description: "",
    };
    api.apiGet.mockImplementation((path: string) => Promise.resolve(
      path.endsWith("/column-mapping") ? { items: [] } : { items: [property] },
    ));
    api.apiDelete.mockResolvedValue({ ok: true, id: "prop-1" });

    await act(async () => root.render(createElement(
      MemoryRouter, { initialEntries: ["/ontology/properties/order"] },
      createElement(Routes, null, createElement(Route, {
        path: "/ontology/properties/:typeId", element: createElement(PropertyEditorPage),
      })),
    )));
    await flush();
    const deleteButton = Array.from(host.querySelectorAll("button")).find((item) => item.textContent?.trim() === "✕");
    if (!deleteButton) throw new Error("delete property button not found");
    await act(async () => deleteButton.click());
    await flush();

    expect(api.apiDelete).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("删除已提交但重读核验失败");
    expect(host.textContent).toContain("amount");
    expect(host.textContent).not.toContain("已删除并重读");
  });

  it("Function live 试跑失败时不执行本地 simulate、不显示测试通过", async () => {
    api.apiGet.mockResolvedValue({ items: [{
      id: "fn-1", name: "calculate", display_name: "Calculate", description: "",
      body: "return 1", return_type: "int", status: "active", category: "business", params: [],
    }] });
    api.apiPost.mockRejectedValue(new Error("runtime unavailable"));

    await act(async () => root.render(createElement(MemoryRouter, null, createElement(FunctionEditorPage))));
    await flush();
    await act(async () => button("测试").click());
    await act(async () => button("运行测试").click());
    await flush();

    expect(api.apiPost).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("真实试跑失败：runtime unavailable");
    expect(host.textContent).not.toContain("测试通过");
    expect(host.textContent).not.toContain("演示路径）");
  });
});
