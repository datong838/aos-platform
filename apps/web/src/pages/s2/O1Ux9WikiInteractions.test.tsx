// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WikiPage } from "./ontology";
import { WikiIndexPage } from "./WikiIndexPage";

const apiMocks = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn(), apiPut: vi.fn(), apiDelete: vi.fn() }));
vi.mock("../../api/client", () => apiMocks);
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

async function flush() {
  await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); });
}

describe("O1-UX9 · Wiki 业务工作流", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => {
    host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
    Object.values(apiMocks).forEach((mock) => mock.mockReset());
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/ontology/object-types") return { items: [{ id: "Order", name: "订单" }, { id: "Product", name: "栖月汇-商品" }] };
      if (path === "/v1/analytics/ontology-rail") return { objectTypes: [{ id: "Product", name: "栖月汇-商品", kind: "object" }] };
      if (path === "/v1/wiki/Product/coverage-index?limit=200") return {
        items: [{ objectType: "Product", objectId: "niushop:1:8", displayLabel: "商品 · 栖月汇精选茶", sourceRecordLabel: "源记录 #8", summary: "", covered: false, versionCount: 0 }],
      };
      throw new Error(`unexpected ${path}`);
    });
  });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("direct Wiki entry provides type and business-object selectors without test WorkOrder residue", async () => {
    await act(async () => root.render(<MemoryRouter><WikiPage /></MemoryRouter>));
    await flush();
    expect(host.querySelector("select[aria-label='Wiki 对象类型']")).not.toBeNull();
    expect(host.querySelector("select[aria-label='Wiki 业务对象']")).not.toBeNull();
    expect(host.textContent).toContain("请选择对象类型");
    expect(host.textContent).not.toContain("wo-1001");
    expect(host.textContent).not.toContain("工单备注标题");
  });

  it("Wiki index uses production knowledge space and human-readable cards, not legacy ontology branches", async () => {
    await act(async () => root.render(<MemoryRouter><WikiIndexPage /></MemoryRouter>));
    await flush();
    const productButton = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "栖月汇-商品") as HTMLButtonElement;
    await act(async () => productButton.click());
    await flush();
    expect(apiMocks.apiGet).not.toHaveBeenCalledWith("/v1/ontology/branches");
    expect(host.textContent).toContain("生产知识空间");
    expect(host.textContent).toContain("商品 · 栖月汇精选茶");
    expect(host.textContent).toContain("源记录 #8");
    expect(host.textContent).toContain("知识缺口");
    const cardLink = Array.from(host.querySelectorAll("a")).find((node) => node.textContent?.includes("商品 · 栖月汇精选茶"));
    expect(cardLink?.textContent).toContain("栖月汇-商品 · 知识缺口");
    expect(cardLink?.textContent).not.toContain("Product");
    expect(cardLink?.textContent).not.toContain("Wiki");
  });
});
