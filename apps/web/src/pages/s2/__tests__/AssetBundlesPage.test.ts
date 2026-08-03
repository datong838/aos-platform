import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { INSTALLATION_DETAIL_FIXTURE, INSTALLATION_LIST_FIXTURE } from "../../../api/assetControl/installationFixtures";
import { REGISTRY_BUNDLE_LIST_FIXTURE } from "../../../api/assetControl/registryFixtures";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const hooks = vi.hoisted(() => ({
  registryStatus: "ready" as const,
}));

const reload = vi.fn();

vi.mock("../assetBundles/readHooks", () => ({
  useRegistryBundles: () => ({
    data: hooks.registryStatus === "ready" ? REGISTRY_BUNDLE_LIST_FIXTURE : [],
    status: hooks.registryStatus,
    error: null,
    refreshing: false,
    stale: false,
    reload,
  }),
  useRegistryBundle: () => ({
    data: null,
    status: "idle",
    error: null,
    refreshing: false,
    stale: false,
    reload,
  }),
  useRegistryVersion: () => ({
    data: null,
    status: "idle",
    error: null,
    refreshing: false,
    stale: false,
    reload,
  }),
  useInstallations: () => ({
    data: INSTALLATION_LIST_FIXTURE,
    status: "ready",
    error: null,
    refreshing: false,
    stale: false,
    reload,
  }),
  useInstallation: (installationId: string | null) => ({
    data: installationId ? INSTALLATION_DETAIL_FIXTURE : null,
    status: installationId ? "ready" : "idle",
    error: null,
    refreshing: false,
    stale: false,
    reload,
  }),
}));

describe("M3-2 AssetBundlesPage integration", () => {
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
    vi.clearAllMocks();
  });

  async function renderPage() {
    const { AssetBundlesPage } = await import("../AssetBundlesPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(AssetBundlesPage)));
    });
  }

  it("renders canonical Registry facts without the legacy demo bundles", async () => {
    await renderPage();
    const text = host.textContent ?? "";

    expect(text).toContain("FDE 资产包");
    expect(text).toContain(REGISTRY_BUNDLE_LIST_FIXTURE[0].bundleId);
    expect(text).toContain("不使用演示数据兜底");
    expect(text).not.toContain("apollo-core");
    expect(text).not.toContain("fde-维修派单");
  });

  it("switches to server-paged installations and opens the event timeline", async () => {
    await renderPage();
    const installationTab = Array.from(host.querySelectorAll('[role="tab"]')).find(
      (node) => node.textContent === "安装管理（只读）",
    ) as HTMLButtonElement;
    await act(async () => installationTab.click());

    expect(host.textContent).toContain(INSTALLATION_LIST_FIXTURE.items[0].displayName);
    const open = Array.from(host.querySelectorAll("button")).find(
      (node) => node.textContent === "查看事件",
    ) as HTMLButtonElement;
    await act(async () => open.click());

    const text = host.textContent ?? "";
    expect(text).toContain("安装详情与事件时间线");
    expect(text).toContain(INSTALLATION_DETAIL_FIXTURE.installationId);
    expect(text).toContain("不提供历史 revision 完整快照");
    expect(text).not.toContain("批准安装");
  });
});
