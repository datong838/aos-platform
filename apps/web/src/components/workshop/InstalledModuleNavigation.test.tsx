import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { setTenant } from "../../api/tenant";
import { EcommerceWorkshopClientError } from "../../api/ecommerceWorkshop";
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

  it("仅按安装目录显示动态模块，当前项唯一", async () => {
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
      "统一运营驾驶舱",
      "价格策略实验室",
    ]);
    expect(host.querySelector(".ecommerce-workshop-readiness-status")).toBeNull();
    expect(links.filter((link) => link.getAttribute("aria-current") === "page")).toHaveLength(1);
    expect(host.querySelectorAll('[data-workshop-module-id="ecommerce.operations"]')).toHaveLength(1);
  });

  it("空安装目录不伪造产品入口", async () => {
    await act(async () => root.render(
      <MemoryRouter>
        <EcommerceWorkshopCatalogProvider client={{ listModules: async () => workshopCatalogFixture({ items: [] }) }}>
          <InstalledModuleNavigation />
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();
    expect(host.querySelectorAll("a")).toHaveLength(0);
    expect(host.textContent).not.toContain("未安装");
    expect(host.textContent).toContain("暂无可见工作台入口");
    expect(host.querySelector("button")?.textContent).toBe("重新读取目录");
  });

  it("开发免登录时目录连接失败仍显示八个明确标注的预览入口", async () => {
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
    expect(host.querySelectorAll("a[data-workshop-preview='true']")).toHaveLength(8);
    expect(host.textContent).not.toContain("未安装");
    expect(host.textContent).not.toContain("已就绪");
    expect(host.textContent).toContain("开发预览入口");
  });

  it("旧冻结 API 返回 404/503 时仍显示八工作台开发预览，但 403 不降级", async () => {
    const error = (status: number) => new EcommerceWorkshopClientError("catalog unavailable", {
      status,
      operationId: "ecommerceWorkshopModulesList",
      body: { code: status === 403 ? "FORBIDDEN" : "NOT_FOUND", message: "unavailable", details: null, traceId: "trace" },
    });
    await act(async () => root.render(
      <MemoryRouter>
        <EcommerceWorkshopCatalogProvider client={{ listModules: async () => { throw error(404); } }}>
          <InstalledModuleNavigation />
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();
    expect(host.querySelectorAll("a[data-workshop-preview='true']")).toHaveLength(8);

    await act(async () => root.unmount());
    root = createRoot(host);
    await act(async () => root.render(
      <MemoryRouter>
        <EcommerceWorkshopCatalogProvider client={{ listModules: async () => { throw error(503); } }}>
          <InstalledModuleNavigation />
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();
    expect(host.querySelectorAll("a[data-workshop-preview='true']")).toHaveLength(8);

    await act(async () => root.unmount());
    root = createRoot(host);
    await act(async () => root.render(
      <MemoryRouter>
        <EcommerceWorkshopCatalogProvider client={{ listModules: async () => { throw error(403); } }}>
          <InstalledModuleNavigation />
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();
    expect(host.querySelectorAll("a[data-workshop-preview='true']")).toHaveLength(0);
    expect(host.textContent).toContain("没有读取工作台目录的权限");
  });

  it("开发期无登录且 API 禁用 dev token 时显示八个明确标注的预览入口", async () => {
    const unauthorized = new EcommerceWorkshopClientError("dev token disabled", {
      status: 401,
      operationId: "ecommerceWorkshopModulesList",
      body: { code: "AUTH_DEV_DISABLED", message: "disabled", details: null, traceId: "trace-dev" },
    });
    await act(async () => root.render(
      <MemoryRouter>
        <EcommerceWorkshopCatalogProvider client={{ listModules: async () => { throw unauthorized; } }}>
          <InstalledModuleNavigation />
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();

    expect(host.querySelectorAll("a[data-workshop-preview='true']")).toHaveLength(8);
    expect(host.textContent).toContain("开发预览入口");
    expect(host.textContent).not.toContain("已安装");
  });

  it("空目录可重读恢复真实入口", async () => {
    let reads = 0;
    const client = { listModules: async () => workshopCatalogFixture({ items: ++reads === 1 ? [] : [workshopModuleFixture()] }) };
    await act(async () => root.render(<MemoryRouter><EcommerceWorkshopCatalogProvider client={client}><InstalledModuleNavigation /></EcommerceWorkshopCatalogProvider></MemoryRouter>));
    await flush();
    expect(host.querySelector("button")).not.toBeNull();
    await act(async () => host.querySelector<HTMLButtonElement>("button")!.click());
    await flush();
    expect(reads).toBe(2);
    expect(host.querySelectorAll("a")).toHaveLength(1);
    expect(host.textContent).not.toContain("暂无可见工作台入口");
  });
});
