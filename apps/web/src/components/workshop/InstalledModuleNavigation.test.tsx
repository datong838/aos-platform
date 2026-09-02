import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { setTenant } from "../../api/tenant";
import { EcommerceWorkshopCatalogProvider } from "./EcommerceWorkshopCatalogContext";
import { InstalledModuleNavigation } from "./InstalledModuleNavigation";
import { moduleWithReadiness, workshopCatalogFixture, workshopModuleFixture } from "./workshopTestFixtures";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("InstalledModuleNavigation", () => {
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

  it("恒定显示八个产品工作台，去重并追加 API 动态模块，当前项唯一", async () => {
    const modules = [
      workshopModuleFixture(),
      moduleWithReadiness("unknown"),
    ].map((module, index) => index === 0 ? module : {
      ...module,
      moduleId: "ecommerce.pricing",
      displayName: "价格策略实验室",
      menuLabel: "价格策略实验室",
      route: "/workshop/pricing-governance",
      order: 70,
      moduleRef: {
        ...module.moduleRef,
        moduleArtifactRef: "bundle://catalog/solutions/ecommerce/content/workshops/ecommerce.pricing.json",
      },
      legacyRoutes: ["/s2/price-governance"],
    });
    const client = { listModules: async () => workshopCatalogFixture({ items: modules }) };

    await act(async () => root.render(
      <MemoryRouter initialEntries={["/workshop/operations"]}>
        <EcommerceWorkshopCatalogProvider client={client}>
          <InstalledModuleNavigation />
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();

    const links = [...host.querySelectorAll<HTMLAnchorElement>("a")];
    expect(links.map((link) => link.textContent?.replace(/\s+/g, "").trim())).toEqual([
      "日常任务总控大屏",
      "内容与活动工作台",
      "统一运营驾驶舱",
      "达人邀约驾驶舱",
      "多媒体内容生产",
      "经营参谋·增长指挥中心",
      "价格治理驾驶舱",
      "客户关系工作台",
      "价格策略实验室",
    ]);
    expect(host.querySelector(".ecommerce-workshop-readiness-status")).toBeNull();
    expect(links.filter((link) => link.getAttribute("aria-current") === "page")).toHaveLength(1);
    expect(host.querySelectorAll('[data-workshop-module-id="ecommerce.operations"]')).toHaveLength(1);
  });

  it("空安装目录不会让八个产品主入口消失", async () => {
    await act(async () => root.render(
      <MemoryRouter>
        <EcommerceWorkshopCatalogProvider client={{ listModules: async () => workshopCatalogFixture({ items: [] }) }}>
          <InstalledModuleNavigation />
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();
    expect(host.querySelectorAll("a")).toHaveLength(8);
    expect(host.textContent).not.toContain("未安装");
  });

  it("目录读取失败时仍保留八个产品主入口且不伪造安装状态", async () => {
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/workshop/customer"]}>
        <EcommerceWorkshopCatalogProvider client={{ listModules: async () => { throw new Error("catalog unavailable"); } }}>
          <InstalledModuleNavigation />
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();

    const links = [...host.querySelectorAll<HTMLAnchorElement>("a")];
    expect(links).toHaveLength(8);
    expect(links.filter((link) => link.getAttribute("aria-current") === "page")).toHaveLength(1);
    expect(host.querySelector('[aria-current="page"]')?.textContent).toContain("客户关系工作台");
    expect(host.textContent).not.toContain("未安装");
    expect(host.textContent).not.toContain("已就绪");
  });
});
