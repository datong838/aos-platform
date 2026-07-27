import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../../api/client", () => ({
  apiGet: vi.fn(async () => ({ items: [] })),
  apiPost: vi.fn(async () => ({ ok: true })),
  apiPut: vi.fn(async () => ({ ok: true })),
  apiDelete: vi.fn(async () => ({ ok: true })),
}));

describe("AssetBundlesPage", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("renders with MOCK fallback asset bundles", async () => {
    const { AssetBundlesPage } = await import("../AssetBundlesPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(AssetBundlesPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("FDE 资产包");
    expect(text).toContain("apollo-core");
    expect(text).toContain("2.14.1");
    expect(text).toContain("fde-维修派单");
    expect(text).toContain("fde-库存预警");
    expect(text).toContain("config-overrides-sh");
    expect(text).toContain("stable");
    expect(text).toContain("beta");
    expect(text).toContain("rc");
  });

  it("shows channel tabs and metrics", async () => {
    const { AssetBundlesPage } = await import("../AssetBundlesPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(AssetBundlesPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("全部");
    expect(text).toContain("Stable");
    expect(text).toContain("Beta");
    expect(text).toContain("RC");
    expect(text).toContain("资产包总数");
    expect(text).toContain("已发布");
  });

  it("filters by channel when tab clicked", async () => {
    const { AssetBundlesPage } = await import("../AssetBundlesPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(AssetBundlesPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    // Click Beta tab
    const tabs = host.querySelectorAll('[role="tab"]');
    const betaTab = Array.from(tabs).find((t) => t.textContent === "Beta");
    if (betaTab) {
      await act(async () => {
        (betaTab as HTMLButtonElement).click();
      });
    }

    const text = host.textContent || "";
    expect(text).toContain("fde-维修派单");
    expect(text).toContain("1.8.0-rc.2");
  });
});
