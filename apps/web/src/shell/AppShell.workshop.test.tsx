import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setTenant } from "../api/tenant";
import { EcommerceWorkshopCatalogProvider } from "../components/workshop";
import { workshopCatalogFixture } from "../components/workshop/workshopTestFixtures";
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

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
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
});
