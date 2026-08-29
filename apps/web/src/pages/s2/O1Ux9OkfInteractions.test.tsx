// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OkfFunnelPage, OkfOverviewPage, okfFunnelStageLabel } from "./remainder";

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(), apiPost: vi.fn(), apiPut: vi.fn(), apiDelete: vi.fn(),
}));
vi.mock("../../api/client", () => apiMocks);

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const ecomOverview = {
  industry: "ecom",
  items: [
    {
      industry: "ecom", objectType: "Order", label: "微商城电商 · Order", status: "configured", revision: 0,
      columns: [], source: { available: true, count: 61, watermark: "2026-05-25T15:22:10Z" },
      coverage: { required: { mapped: 6, total: 6, percent: 100 }, optional: { mapped: 0, total: null, percent: null, status: "unknown" } },
      blockedFields: [],
    },
    {
      industry: "ecom", objectType: "Product", label: "微商城电商 · Product", status: "unconfigured", revision: 0,
      columns: [], source: { available: true, count: 57, watermark: "2026-06-22T01:05:56Z" },
      coverage: { required: { mapped: 0, total: 6, percent: 0 }, optional: { mapped: 0, total: null, percent: null, status: "unknown" } },
      blockedFields: [],
    },
  ],
  overall: {
    required: { mapped: 6, total: 12, percent: 50 }, unknown: ["Product"], excluded: [], complete: false,
    formula: "weighted",
  },
};

async function flush() {
  await act(async () => {
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
  });
}

describe("O1-UX9 · OKF 多 Object Type", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
    Object.values(apiMocks).forEach((mock) => mock.mockReset());
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/ontology/okf-mappings/ecom/types") return ecomOverview;
      if (path === "/v1/ontology/okf-mappings/ecom/types/Order") return ecomOverview.items[0];
      if (path === "/v1/ontology/okf-mappings/ecom/types/Product") return ecomOverview.items[1];
      if (path === "/v1/modules") return { items: [] };
      if (path === "/v1/ontology/object-types") return {
        items: [{ id: "Order", name: "订单" }, { id: "Product", name: "商品" }],
      };
      if (path === "/v1/funnel/Order/status") return { stage: "hydration" };
      if (path === "/v1/funnel/Product/status") return { stage: "hydration" };
      throw new Error(`unexpected ${path}`);
    });
  });

  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("overview uses weighted industry coverage and exposes each real source type", async () => {
    await act(async () => root.render(<MemoryRouter><OkfOverviewPage /></MemoryRouter>));
    await flush();
    expect(host.textContent).toContain("必填覆盖率50%");
    expect(host.textContent).toContain("微商城电商 · 订单");
    expect(host.textContent).toContain("微商城电商 · 商品");
    expect(host.textContent).toContain("当前行业范围不能宣告完整");
    expect(host.textContent).toContain("当前安装的电商行业模板");
    const orderLink = Array.from(host.querySelectorAll("a")).find((node) => node.textContent?.includes("微商城电商 · 订单"));
    expect(orderLink?.textContent).not.toContain("Order");
    expect(orderLink?.textContent).not.toContain("r0");
    expect(apiMocks.apiGet).not.toHaveBeenCalledWith("/v1/ontology/okf-mappings/env");
    expect(apiMocks.apiGet).not.toHaveBeenCalledWith("/v1/ontology/okf-mappings/bio");
  });

  it("funnel selects a concrete ecommerce object type instead of hard-binding the whole industry to Order", async () => {
    await act(async () => root.render(<MemoryRouter initialEntries={["/ontology/okf-funnel?industry=ecom&type=Order"]}><OkfFunnelPage /></MemoryRouter>));
    await flush();
    expect(host.querySelector("select[aria-label='OKF 行业']")).not.toBeNull();
    expect(host.textContent).toContain("已连接真实来源数据的业务对象");
    expect(host.textContent).toContain("微商城电商 · 商品未配置");
    expect(host.textContent).toContain("必填覆盖率100%");
    expect(host.textContent).toContain("业务漏斗阶段语义水合");
    expect(host.textContent).not.toContain("微商城电商 · Order修订");
  });

  it("translates authoritative funnel stages without inventing unknown business states", () => {
    expect(okfFunnelStageLabel("hydration")).toBe("语义水合");
    expect(okfFunnelStageLabel("unexpected-stage")).toBe("待确认");
    expect(okfFunnelStageLabel(null)).toBe("未读取");
  });

  it("clears a prior rule result when the selected business object changes", async () => {
    apiMocks.apiPost.mockResolvedValue({ ok: true, errors: [] });
    await act(async () => root.render(<MemoryRouter initialEntries={["/ontology/okf-funnel?industry=ecom&type=Order"]}><OkfFunnelPage /></MemoryRouter>));
    await flush();
    const ruleButton = Array.from(host.querySelectorAll("button")).find((node) => node.textContent === "规则检查");
    await act(async () => ruleButton?.click());
    await flush();
    expect(host.textContent).toContain("规则检查通过");
    const productButton = Array.from(host.querySelectorAll("button")).find((node) => node.textContent?.includes("微商城电商 · 商品"));
    await act(async () => productButton?.click());
    await flush();
    expect(host.textContent).not.toContain("规则检查通过");
  });
});
