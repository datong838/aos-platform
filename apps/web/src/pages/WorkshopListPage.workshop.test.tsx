import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setTenant } from "../api/tenant";
import { EcommerceWorkshopCatalogProvider } from "../components/workshop";
import { workshopCatalogFixture } from "../components/workshop/workshopTestFixtures";
import { WorkshopListPage } from "./WorkshopListPage";

const apiPost = vi.hoisted(() => vi.fn());
vi.mock("../api/client", () => ({ apiPost }));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("WorkshopListPage · installed ecommerce projection", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    sessionStorage.clear();
    setTenant({ orgId: "org-org", projectId: "dev-project", workspaceName: "real" });
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("active replacement 进入已安装区，平台辅助区不再生成旧订单链接", async () => {
    await act(async () => root.render(
      <MemoryRouter>
        <EcommerceWorkshopCatalogProvider client={{ listModules: async () => workshopCatalogFixture() }}>
          <WorkshopListPage />
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();

    const installed = host.querySelector("[data-testid='installed-ecommerce-section']")!;
    expect(installed.textContent).toContain("统一运营驾驶舱");
    expect(installed.querySelector<HTMLAnchorElement>("a")?.getAttribute("href")).toBe("/workshop/operations");
    expect(host.querySelector("a[href='/workshop/orders']")).toBeNull();
    expect(host.textContent).toContain("平台辅助模块");
    expect(host.textContent).toContain("可使用");
    const audits = installed.querySelectorAll<HTMLDetailsElement>(".aos-inline-audit");
    expect(audits.length).toBeGreaterThan(0);
    expect(Array.from(audits).every((item) => !item.open)).toBe(true);

    const platformLink = host.querySelector<HTMLAnchorElement>("a[href='/workshop/inbox']")!;
    await act(async () => platformLink.click());
    expect(apiPost).not.toHaveBeenCalled();
  });

  it("未安装时不伪造八 Module，旧平台只读订单入口仍保留", async () => {
    await act(async () => root.render(
      <MemoryRouter>
        <EcommerceWorkshopCatalogProvider client={{ listModules: async () => workshopCatalogFixture({ items: [] }) }}>
          <WorkshopListPage />
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();
    expect(host.textContent).toContain("模块未安装");
    expect(host.querySelector("a[href='/workshop/orders']")).not.toBeNull();
    expect(host.textContent).not.toContain("达人邀约驾驶舱");
  });
});
