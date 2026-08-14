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

  it("只显示 API 返回的 active installed Module，当前项唯一 aria-current 且状态有文字", async () => {
    const modules = [
      workshopModuleFixture(),
      moduleWithReadiness("unknown"),
    ].map((module, index) => index === 0 ? module : {
      ...module,
      moduleId: "ecommerce.pricing",
      displayName: "价格治理驾驶舱",
      menuLabel: "价格治理驾驶舱",
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
      "统一运营驾驶舱可用",
      "价格治理驾驶舱待验证",
    ]);
    expect(links.filter((link) => link.getAttribute("aria-current") === "page")).toHaveLength(1);
    expect(host.textContent).not.toContain("达人邀约驾驶舱");
  });

  it("空安装与读取失败均诚实呈现，不注入固定八菜单", async () => {
    await act(async () => root.render(
      <MemoryRouter>
        <EcommerceWorkshopCatalogProvider client={{ listModules: async () => workshopCatalogFixture({ items: [] }) }}>
          <InstalledModuleNavigation />
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();
    expect(host.textContent).toContain("当前工作区未安装电商工作台");
    expect(host.querySelectorAll("a")).toHaveLength(0);
  });
});
