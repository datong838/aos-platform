// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FunnelPage } from "./ontology";

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));

vi.mock("../../api/client", () => apiMocks);

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("O1-UX9 · Funnel 状态与类型选择", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    Object.values(apiMocks).forEach((mock) => mock.mockReset());
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/ontology/object-types") {
        return { items: [{ id: "Order", name: "订单" }, { id: "Product", name: "商品" }] };
      }
      if (path.endsWith("/status")) return { objectType: "Order", stage: "hydration", detail: { failures: [] } };
      if (path.endsWith("/worker")) return { stages: [] };
      throw new Error(`unexpected ${path}`);
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("direct entry renders a real type selector and never calls the idle state loading", async () => {
    await act(async () => root.render(<MemoryRouter initialEntries={["/ontology/funnel"]}><FunnelPage /></MemoryRouter>));
    await flush();

    expect(host.querySelector("select[aria-label='选择业务漏斗对象类型']")).not.toBeNull();
    expect(host.textContent).toContain("请选择对象类型");
    expect(host.textContent).not.toContain("加载流水线…");
  });

  it("selected type with an empty authoritative stage list renders an empty state, not loading", async () => {
    await act(async () => root.render(<MemoryRouter initialEntries={["/ontology/funnel?type=Order"]}><FunnelPage /></MemoryRouter>));
    await flush();

    expect(host.textContent).toContain("当前对象类型暂无阶段状态");
    expect(host.textContent).not.toContain("加载流水线…");
  });
});
