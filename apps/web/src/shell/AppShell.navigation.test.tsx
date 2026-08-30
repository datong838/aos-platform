import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setTenant } from "../api/tenant";
import { EcommerceWorkshopCatalogProvider } from "../components/workshop";
import { workshopCatalogFixture } from "../components/workshop/workshopTestFixtures";
import { isNavPage, NAV_ITEMS } from "../nav";
import { AppShell } from "./AppShell";

vi.mock("../components/ApiStatusBar", () => ({ ApiStatusBar: () => null }));
vi.mock("../components/OfflineBanner", () => ({ OfflineBanner: () => null }));
vi.mock("../components/WorkspaceSwitcher", () => ({ WorkspaceSwitcher: () => null }));
vi.mock("../components/OrgSwitcher", () => ({ OrgSwitcher: () => null }));
vi.mock("../components/PlatformBaseSwitcher", () => ({ PlatformBaseSwitcher: () => null }));
vi.mock("../components/EnvReadonlyBadge", () => ({ EnvReadonlyBadge: () => null }));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function Jump() {
  const navigate = useNavigate();
  return <button type="button" onClick={() => navigate("/aip/model-runtime")}>跳到运行就绪</button>;
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("AppShell · AIP 全菜单导航", () => {
  let host: HTMLDivElement;
  let root: Root;
  const scrollIntoView = vi.fn();

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    setTenant({ orgId: "org-org", projectId: "dev-project", workspaceName: "栖月汇" });
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    });
    Object.defineProperty(window, "requestAnimationFrame", {
      configurable: true,
      value: (callback: FrameRequestCallback) => {
        callback(0);
        return 1;
      },
    });
    Object.defineProperty(window, "cancelAnimationFrame", {
      configurable: true,
      value: vi.fn(),
    });
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    scrollIntoView.mockReset();
  });

  async function render(path: string) {
    const client = { listModules: async () => workshopCatalogFixture({ items: [] }) };
    await act(async () => root.render(
      <MemoryRouter initialEntries={[path]}>
        <EcommerceWorkshopCatalogProvider client={client}>
          <Jump />
          <Routes>
            <Route element={<AppShell />}>
              <Route path="*" element={<div>页面正文</div>} />
            </Route>
          </Routes>
        </EcommerceWorkshopCatalogProvider>
      </MemoryRouter>,
    ));
    await flush();
  }

  it("深链进入 AIP 页面时自动展开所属分组并保留全部 25 个 AIP 入口", async () => {
    localStorage.setItem("aos:nav-sections-collapsed", JSON.stringify(["模型管理"]));
    await render("/aip/model-runtime");

    const aipPages = NAV_ITEMS.filter(isNavPage).filter((item) => item.path.startsWith("/aip/") && !item.hidden);
    expect(aipPages).toHaveLength(25);
    expect(aipPages.some((item) => item.path === "/aip/doc-intelligence")).toBe(true);
    expect(host.querySelectorAll<HTMLAnchorElement>('.nav a[href^="/aip/"]')).toHaveLength(aipPages.length);
    const sectionToggle = [...host.querySelectorAll<HTMLButtonElement>(".aos-nav-section-toggle")]
      .find((button) => button.textContent?.includes("模型管理"));
    expect(sectionToggle?.getAttribute("aria-expanded")).toBe("true");
    expect(sectionToggle?.getAttribute("aria-controls")).toBeTruthy();
    expect(host.querySelector('[data-nav-id="aip-model-runtime"]')?.classList.contains("is-active")).toBe(true);
  });

  it("整体折叠时不让分组折叠状态二次隐藏入口，并为图标保留可读名称", async () => {
    localStorage.setItem("aos:sidebar-collapsed", "1");
    localStorage.setItem("aos:nav-sections-collapsed", JSON.stringify(["工作台", "构建工具", "AIP 决策引擎", "运维交付"]));
    await render("/aip/assist");

    expect(host.querySelector("aside")?.classList.contains("is-collapsed")).toBe(true);
    expect(host.querySelectorAll(".aos-nav-section-content.is-collapsed")).toHaveLength(0);
    const modelRouter = host.querySelector<HTMLAnchorElement>('[data-nav-id="aip-model-router"]');
    expect(modelRouter?.getAttribute("title")).toBe("模型路由");
    expect(modelRouter?.getAttribute("aria-label")).toBe("模型路由");
  });

  it("路由变化后把当前菜单滚入侧栏可见区且不转移正文焦点", async () => {
    await render("/aip/assist");
    const jump = [...host.querySelectorAll<HTMLButtonElement>("button")]
      .find((button) => button.textContent === "跳到运行就绪")!;
    jump.focus();
    await act(async () => jump.click());
    await flush();

    expect(host.querySelector('[data-nav-id="aip-model-runtime"]')?.classList.contains("is-active")).toBe(true);
    expect(scrollIntoView).toHaveBeenCalled();
    expect(document.activeElement).toBe(jump);
  });

  it("嵌套业务逻辑修订仍把业务逻辑菜单标记为当前页", async () => {
    await render("/aip/logic/graph-1");
    const logic = host.querySelector<HTMLAnchorElement>('[data-nav-id="aip-logic"]');
    expect(logic?.classList.contains("is-active")).toBe(true);
    expect(logic?.getAttribute("aria-current")).toBe("page");
  });
});
