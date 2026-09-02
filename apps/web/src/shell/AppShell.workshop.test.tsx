import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setTenant } from "../api/tenant";
import { EcommerceWorkshopCatalogProvider } from "../components/workshop";
import { workshopCatalogFixture, workshopModuleFixture } from "../components/workshop/workshopTestFixtures";
import { EcommerceWorkshopEntryRoute } from "../pages/s2/ecommerce/routes";
import { AppShell } from "./AppShell";

vi.mock("../components/ApiStatusBar", () => ({ ApiStatusBar: () => null }));
vi.mock("../components/OfflineBanner", () => ({ OfflineBanner: () => null }));
vi.mock("../components/WorkspaceSwitcher", () => ({ WorkspaceSwitcher: () => null }));
vi.mock("../components/OrgSwitcher", () => ({ OrgSwitcher: () => null }));
vi.mock("../components/PlatformBaseSwitcher", () => ({ PlatformBaseSwitcher: () => null }));
vi.mock("../components/EnvReadonlyBadge", () => ({ EnvReadonlyBadge: () => null }));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

function NavigationProbe() {
  const navigate = useNavigate();
  return <>
    <button type="button" data-testid="go-content" onClick={() => navigate("/workshop/content-campaign")}>go content</button>
    <button type="button" data-testid="go-customer" onClick={() => navigate("/workshop/customer")}>go customer</button>
    <button type="button" data-testid="go-operations" onClick={() => navigate("/workshop/operations")}>go operations</button>
  </>;
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

const PRIMARY_WORKSHOP_CASES = [
  ["/workshop/cockpit", "ecommerce.task-cockpit", "日常任务总控大屏"],
  ["/workshop/content-campaign", "ecommerce.content-campaign", "内容与活动工作台"],
  ["/workshop/operations", "ecommerce.operations", "统一运营驾驶舱"],
  ["/workshop/creator-growth", "ecommerce.creator-growth", "达人邀约驾驶舱"],
  ["/workshop/media-studio", "ecommerce.media-studio", "多媒体内容生产"],
  ["/workshop/analyst", "ecommerce.analyst", "经营参谋 · 增长指挥中心"],
  ["/workshop/price-governance", "ecommerce.price-governance", "价格治理驾驶舱"],
  ["/workshop/customer", "ecommerce.customer", "客户关系工作台"],
] as const;

function primaryWorkshopCatalog() {
  return workshopCatalogFixture({
    items: PRIMARY_WORKSHOP_CASES.map(([route, moduleId, label], index) => workshopModuleFixture({
      route,
      moduleId,
      displayName: label,
      menuLabel: label,
      order: index + 1,
      legacyRoutes: [],
    })),
  });
}

describe("AppShell · ecommerce Workshop route and focus", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    setTenant({ orgId: "org-org", projectId: "dev-project", workspaceName: "real" });
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: false,
        media: "(prefers-color-scheme: dark)",
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
    Object.defineProperty(window, "requestAnimationFrame", {
      configurable: true,
      writable: true,
      value: (callback: FrameRequestCallback) => {
        callback(0);
        return 1;
      },
    });
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("replacement active 后旧订单入口 replace 到 canonical 且全壳只有一个 active", async () => {
    const client = { listModules: async () => workshopCatalogFixture() };
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/workshop/orders"]}>
        <EcommerceWorkshopCatalogProvider client={client}>
          <LocationProbe />
          <Routes>
            <Route element={<AppShell />}>
              <Route path="workshop/:workshopModule/*" element={<EcommerceWorkshopEntryRoute />} />
            </Route>
          </Routes>
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();

    expect(host.querySelector("[data-testid='location']")?.textContent).toBe("/workshop/operations");
    expect(host.textContent).not.toContain("订单管理");
    const currentLinks = [...host.querySelectorAll<HTMLAnchorElement>("a[aria-current='page']")];
    expect(currentLinks).toHaveLength(1);
    expect(currentLinks[0].textContent).toContain("统一运营驾驶舱");
    expect(host.querySelectorAll("h1")).toHaveLength(1);
    expect(host.querySelectorAll("main")).toHaveLength(1);
  });

  it("没有 active replacement 与显式退役 Receipt 时继续保留旧只读入口", async () => {
    const client = { listModules: async () => workshopCatalogFixture({ items: [] }) };
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/workshop/orders"]}>
        <EcommerceWorkshopCatalogProvider client={client}>
          <LocationProbe />
          <Routes>
            <Route element={<AppShell />}>
              <Route path="workshop/:workshopModule/*" element={<EcommerceWorkshopEntryRoute />} />
            </Route>
          </Routes>
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();

    expect(host.querySelector("[data-testid='location']")?.textContent).toBe("/workshop/orders");
    expect(host.textContent).toContain("订单管理");
  });

  it("canonical 深层路径保持在同一 Module Shell 与唯一 active 导航中", async () => {
    const client = { listModules: async () => workshopCatalogFixture() };
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/workshop/operations/orders/late"]}>
        <EcommerceWorkshopCatalogProvider client={client}>
          <LocationProbe />
          <Routes>
            <Route element={<AppShell />}>
              <Route path="workshop/:workshopModule/*" element={<EcommerceWorkshopEntryRoute />} />
            </Route>
          </Routes>
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();

    expect(host.querySelector("[data-testid='location']")?.textContent).toBe(
      "/workshop/operations/orders/late",
    );
    expect(host.querySelectorAll("h1")).toHaveLength(1);
    const currentLinks = [...host.querySelectorAll<HTMLAnchorElement>("a[aria-current='page']")];
    expect(currentLinks).toHaveLength(1);
    expect(currentLinks[0].textContent).toContain("统一运营驾驶舱");
  });

  it("八个主工作台路由与 Buddy 共享 canonical 全量侧栏，经营参谋保留独立页面作用域", async () => {
    const client = { listModules: async () => primaryWorkshopCatalog() };
    await act(async () => root.render(
      <MemoryRouter key="analyst" initialEntries={["/workshop/analyst"]}>
        <EcommerceWorkshopCatalogProvider client={client}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="workshop/:workshopModule/*" element={<EcommerceWorkshopEntryRoute />} />
            </Route>
          </Routes>
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();

    expect(host.querySelector(".p-app")?.classList.contains("is-analyst-visual")).toBe(true);
    expect(host.querySelector(".analyst-exact-side-nav")).toBeNull();
    expect(host.querySelector(".analyst-exact-global")).toBeNull();
    expect(host.querySelectorAll(".nav .aos-nav-link").length).toBeGreaterThan(60);
    expect(host.querySelector('.nav a[href="/aip/model-router"]')).not.toBeNull();
    expect(host.querySelector('.nav a[aria-current="page"]')?.textContent).toContain("经营参谋 · 增长指挥中心");
    expect(host.querySelector(".brand-block")).toBeNull();
    expect(host.querySelector(".analyst-exact-header-left h1")?.textContent).toBe("经营参谋 · 增长指挥中心");
    expect(host.querySelector<HTMLSelectElement>('.analyst-exact-header-right select[aria-label="渠道视角"]')?.disabled).toBe(false);
    expect(host.querySelector(".analyst-exact-owner")?.textContent).toBe("经营参谋（负责人未绑定）");
    expect(host.querySelector(".analyst-exact-owner")?.getAttribute("title")).toBe("经营参谋（负责人未绑定）");
    const planButton = Array.from(host.querySelectorAll<HTMLButtonElement>(".analyst-exact-header-right button")).find((item) => item.textContent === "查看今日方案");
    expect(planButton).toBeDefined();

    await act(async () => root.render(
      <MemoryRouter key="operations" initialEntries={["/workshop/operations"]}>
        <EcommerceWorkshopCatalogProvider client={client}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="workshop/:workshopModule/*" element={<EcommerceWorkshopEntryRoute />} />
            </Route>
          </Routes>
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();

    expect(host.querySelector(".p-app")?.classList.contains("is-analyst-visual")).toBe(false);
    expect(host.querySelector(".analyst-exact-side-nav")).toBeNull();
    expect(host.querySelectorAll(".nav .aos-nav-link").length).toBeGreaterThan(60);
    expect(host.querySelector('.nav a[href="/aip/model-router"]')).not.toBeNull();
    expect(host.querySelector('.nav a[aria-current="page"]')?.textContent).toContain("统一运营驾驶舱");
    expect(host.querySelector(".brand-block")).toBeNull();
    expect(host.querySelector<HTMLInputElement>('.workshop-visual-header-search input')?.placeholder).toBe("搜索订单号、SKU、告警关键词…");
    const visualHeaderActions = [...host.querySelectorAll<HTMLButtonElement>(".workshop-visual-header-actions button")];
    expect(visualHeaderActions.map((button) => button.textContent)).toEqual(["筛选", "＋ 新建处理"]);
    expect(visualHeaderActions[0]?.disabled).toBe(false);
    expect(visualHeaderActions[1]?.disabled).toBe(true);
    await act(async () => visualHeaderActions[0]?.click());
    expect(document.activeElement).toBe(host.querySelector(".workshop-visual-header-search input"));
    expect(visualHeaderActions[1]?.title).toContain("正式业务数据与内部工作流");
    expect(host.querySelector(".workshop-header-action-notice")).toBeNull();
  });

  it("八个主工作台逐页保留相同完整导航、唯一当前项与底部模型管理入口", async () => {
    const client = { listModules: async () => primaryWorkshopCatalog() };
    const cases = PRIMARY_WORKSHOP_CASES.map(([path, , label]) => [path, label] as const);
    let canonicalLinkCount: number | null = null;

    for (const [path, label] of cases) {
      await act(async () => root.render(
        <MemoryRouter key={path} initialEntries={[path]}>
          <EcommerceWorkshopCatalogProvider client={client}>
            <Routes><Route element={<AppShell />}><Route path="workshop/:workshopModule/*" element={<EcommerceWorkshopEntryRoute />} /></Route></Routes>
          </EcommerceWorkshopCatalogProvider>
        </MemoryRouter>,
      ));
      await flush();

      const links = [...host.querySelectorAll<HTMLAnchorElement>(".nav .aos-nav-link")];
      canonicalLinkCount ??= links.length;
      expect(links.length, path).toBe(canonicalLinkCount);
      expect(links.length, path).toBeGreaterThan(60);
      expect(host.querySelectorAll(".nav .aos-nav-link.is-active"), path).toHaveLength(1);
      expect(host.querySelector(".nav .aos-nav-link.is-active")?.textContent, path).toContain(label);
      expect(host.querySelector('.nav a[href="/workshop/buddy"]'), path).not.toBeNull();
      expect(host.querySelector('.nav a[href="/aip/model-runtime"]'), path).not.toBeNull();
      expect(host.querySelector(".analyst-exact-side-nav"), path).toBeNull();
    }
  });

  it("任务总控路由启用独立视觉壳并保留搜索与日历入口", async () => {
    const client = { listModules: async () => primaryWorkshopCatalog() };
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/workshop/cockpit"]}>
        <EcommerceWorkshopCatalogProvider client={client}>
          <Routes><Route element={<AppShell />}><Route path="workshop/:workshopModule/*" element={<EcommerceWorkshopEntryRoute />} /></Route></Routes>
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();
    expect(host.querySelector(".p-app")?.classList.contains("is-task-cockpit-visual")).toBe(true);
    expect(host.querySelector(".p-app")?.classList.contains("is-workshop-primary-visual")).toBe(true);
    expect(host.querySelector(".analyst-exact-side-nav")).toBeNull();
    expect(host.querySelectorAll(".nav .aos-nav-link").length).toBeGreaterThan(60);
    expect(host.querySelector('.nav a[aria-current="page"]')?.textContent).toContain("日常任务总控大屏");
    expect(host.querySelector<HTMLInputElement>('.task-cockpit-exact-header-search input')?.placeholder).toBe("搜索任务、同事、关键词…");
    expect(host.querySelector(".task-cockpit-exact-header-right button")?.textContent).toContain("日历视图");
  });

  it("六个业务工作台使用各自视觉稿顶部语义且动作可用态与真实行为一致", async () => {
    const cases = [
      ["/workshop/operations", "ecommerce.operations", "统一运营驾驶舱", "搜索订单号、SKU、告警关键词…"],
      ["/workshop/content-campaign", "ecommerce.content-campaign", "内容与活动工作台", "搜索活动、内容、商品…"],
      ["/workshop/creator-growth", "ecommerce.creator-growth", "达人邀约驾驶舱", "搜索达人、机构、邀约记录…"],
      ["/workshop/media-studio", "ecommerce.media-studio", "多媒体内容生产", "搜索文案、视频、直播任务…"],
      ["/workshop/price-governance", "ecommerce.price-governance", "价格治理驾驶舱", null],
      ["/workshop/customer", "ecommerce.customer", "客户关系工作台", null],
    ] as const;
    for (const [path, moduleId, title, placeholder] of cases) {
      const client = {
        listModules: async () => workshopCatalogFixture({
          items: [workshopModuleFixture({
            moduleId,
            route: path,
            displayName: title,
            menuLabel: title,
            legacyRoutes: [],
          })],
        }),
      };
      await act(async () => root.render(
        <MemoryRouter key={path} initialEntries={[path]}>
          <EcommerceWorkshopCatalogProvider client={client}>
            <Routes><Route element={<AppShell />}><Route path="workshop/:workshopModule/*" element={<EcommerceWorkshopEntryRoute />} /></Route></Routes>
          </EcommerceWorkshopCatalogProvider>
        </MemoryRouter>,
      ));
      await flush();
      expect(host.querySelector("[data-module-id]")?.getAttribute("data-module-id")).toBe(moduleId);
      expect(host.querySelector(".workshop-visual-header-left")?.textContent).toContain(title);
      expect(host.querySelectorAll("h1"), path).toHaveLength(1);
      expect(host.querySelector<HTMLInputElement>(".workshop-visual-header-search input")?.placeholder ?? null).toBe(placeholder);
      const actions = [...host.querySelectorAll<HTMLButtonElement>(".workshop-visual-header-actions button")];
      expect(actions).toHaveLength(2);
      const executable = actions.filter((button) => button.textContent === "筛选" || button.textContent === "查看内容计划");
      expect(executable.every((button) => !button.disabled)).toBe(true);
      expect(actions.filter((button) => !executable.includes(button)).every((button) => button.disabled)).toBe(true);
      expect(host.querySelector('.workshop-header-action-notice')).toBeNull();
    }
  });

  it("侧栏折叠可恢复，专注模式进入与退出不丢失上下文和焦点", async () => {
    const client = { listModules: async () => workshopCatalogFixture() };
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/workshop/operations"]}>
        <EcommerceWorkshopCatalogProvider client={client}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="workshop/:workshopModule/*" element={<EcommerceWorkshopEntryRoute />} />
            </Route>
          </Routes>
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();

    const asideToggle = host.querySelector<HTMLButtonElement>(".aside-toggle")!;
    expect(asideToggle.getAttribute("aria-expanded")).toBe("true");
    await act(async () => asideToggle.click());
    expect(asideToggle.getAttribute("aria-expanded")).toBe("false");
    expect(localStorage.getItem("aos:sidebar-collapsed")).toBe("1");

    const focus = [...host.querySelectorAll<HTMLButtonElement>("button")]
      .find((button) => button.textContent === "专注模式")!;
    await act(async () => focus.click());
    expect(host.querySelector(".p-app")?.classList.contains("is-workshop-focus")).toBe(true);
    expect(host.textContent).toContain("solution.ecommerce.operations-base@1.0.0");

    const exit = [...host.querySelectorAll<HTMLButtonElement>("button")]
      .find((button) => button.textContent === "退出专注")!;
    await act(async () => exit.click());
    expect(host.querySelector(".p-app")?.classList.contains("is-workshop-focus")).toBe(false);
    expect(document.activeElement).toBe(exit);
    expect(host.querySelector("aside")?.classList.contains("is-collapsed")).toBe(true);
  });

  it("主工作台路由切换时复位共享内容容器滚动位置", async () => {
    const client = {
      listModules: async () => workshopCatalogFixture({
        items: [
          workshopModuleFixture(),
          workshopModuleFixture({
            moduleId: "ecommerce.content-campaign",
            route: "/workshop/content-campaign",
            displayName: "内容与活动工作台",
            menuLabel: "内容与活动工作台",
            legacyRoutes: [],
          }),
        ],
      }),
    };
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/workshop/operations"]}>
        <EcommerceWorkshopCatalogProvider client={client}>
          <NavigationProbe />
          <Routes>
            <Route element={<AppShell />}>
              <Route path="workshop/:workshopModule/*" element={<EcommerceWorkshopEntryRoute />} />
            </Route>
          </Routes>
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();

    const content = host.querySelector<HTMLDivElement>(".content")!;
    content.scrollTop = 115.5;
    content.scrollLeft = 24;
    expect(content.scrollTop).toBe(115.5);
    expect(content.scrollLeft).toBe(24);

    await act(async () => host.querySelector<HTMLButtonElement>("[data-testid='go-content']")!.click());
    await flush();

    expect(content.scrollTop).toBe(0);
    expect(content.scrollLeft).toBe(0);
    expect(host.querySelector('.nav a[aria-current="page"]')?.textContent).toContain("内容与活动工作台");
  });

  it("尚未接通正式内部工作流的页头动作使用原生禁用语义且不产生伪结果", async () => {
    const client = {
      listModules: async () => workshopCatalogFixture({
        items: [
          workshopModuleFixture({
            moduleId: "ecommerce.price-governance",
            route: "/workshop/price-governance",
            displayName: "价格治理驾驶舱",
            menuLabel: "价格治理驾驶舱",
            legacyRoutes: [],
          }),
          workshopModuleFixture({
            moduleId: "ecommerce.customer",
            route: "/workshop/customer",
            displayName: "客户关系工作台",
            menuLabel: "客户关系工作台",
            legacyRoutes: [],
          }),
        ],
      }),
    };
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/workshop/price-governance"]}>
        <EcommerceWorkshopCatalogProvider client={client}>
          <NavigationProbe />
          <Routes>
            <Route element={<AppShell />}>
              <Route path="workshop/:workshopModule/*" element={<EcommerceWorkshopEntryRoute />} />
            </Route>
          </Routes>
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();

    const newStrategy = [...host.querySelectorAll<HTMLButtonElement>(".workshop-visual-header-actions button")]
      .find((button) => button.textContent === "＋ 新建监测策略")!;
    expect(newStrategy.disabled).toBe(true);
    expect(newStrategy.title).toContain("正式业务数据与内部工作流");
    expect(host.querySelector(".workshop-header-action-notice")).toBeNull();

    await act(async () => host.querySelector<HTMLButtonElement>("[data-testid='go-customer']")!.click());
    await flush();
    expect(host.querySelector(".workshop-header-action-notice")).toBeNull();
    expect(host.querySelector(".workshop-visual-header-left")?.textContent).toContain("客户关系工作台");

    const newContact = [...host.querySelectorAll<HTMLButtonElement>(".workshop-visual-header-actions button")]
      .find((button) => button.textContent === "＋ 新建触达任务")!;
    expect(newContact.disabled).toBe(true);
    expect(host.querySelector(".workshop-header-action-notice")).toBeNull();
  });

  it("全局导航图标聚焦当前搜索并进入既有安全路由", async () => {
    const client = { listModules: async () => workshopCatalogFixture() };
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/workshop/operations"]}>
        <EcommerceWorkshopCatalogProvider client={client}>
          <NavigationProbe />
          <LocationProbe />
          <Routes>
            <Route element={<AppShell />}>
              <Route path="*" element={<div />} />
            </Route>
          </Routes>
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();

    const globalNav = host.querySelector<HTMLElement>('nav[aria-label="全局导航"]')!;
    await act(async () => globalNav.querySelector<HTMLButtonElement>('button[title="搜索"]')!.click());
    expect(document.activeElement).toBe(host.querySelector(".workshop-visual-header-search input"));
    expect(host.querySelector("[data-testid='location']")?.textContent).toBe("/workshop/operations");

    const destinations = [
      ["通知", "/workshop/inbox"],
      ["历史", "/aip/lineage"],
      ["项目", "/workshop"],
      ["应用", "/workshop"],
      ["数据", "/data"],
      ["帮助", "/settings/ops-start-guide"],
    ] as const;
    for (const [title, path] of destinations) {
      await act(async () => host.querySelector<HTMLButtonElement>("[data-testid='go-operations']")!.click());
      await flush();
      const button = host.querySelector<HTMLButtonElement>(`nav[aria-label="全局导航"] button[title="${title}"]`)!;
      await act(async () => button.click());
      await flush();
      expect(host.querySelector("[data-testid='location']")?.textContent).toBe(path);
    }
  });
});
