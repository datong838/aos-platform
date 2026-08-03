import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { assetControlClient } from "../../../api/assetControl/client";
import { STORED_COMPOSITION_LOCK_FIXTURE } from "../../../api/assetControl/compositionFixtures";
import { INSTALLATION_DETAIL_FIXTURE, INSTALLATION_DRAFT_FIXTURE, INSTALLATION_LIST_FIXTURE } from "../../../api/assetControl/installationFixtures";
import { REGISTRY_BUNDLE_DETAIL_FIXTURE, REGISTRY_BUNDLE_LIST_FIXTURE, REGISTRY_VERSION_DETAIL_FIXTURE } from "../../../api/assetControl/registryFixtures";

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
  useRegistryBundle: (selection: unknown) => ({
    data: selection ? REGISTRY_BUNDLE_DETAIL_FIXTURE : null,
    status: selection ? "ready" : "idle",
    error: null,
    refreshing: false,
    stale: false,
    reload,
  }),
  useRegistryVersion: (selection: unknown) => ({
    data: selection ? REGISTRY_VERSION_DETAIL_FIXTURE : null,
    status: selection ? "ready" : "idle",
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

describe("M3-3 AssetBundlesPage integration", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    vi.spyOn(assetControlClient, "resolveComposition").mockResolvedValue(
      STORED_COMPOSITION_LOCK_FIXTURE,
    );
    vi.spyOn(assetControlClient, "getCompositionLock").mockResolvedValue(
      STORED_COMPOSITION_LOCK_FIXTURE,
    );
    vi.spyOn(assetControlClient, "createInstallation").mockResolvedValue(
      INSTALLATION_DRAFT_FIXTURE,
    );
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

  it("resolves, reconciles and creates only a draft from the selected published version", async () => {
    await renderPage();
    const buttons = () => Array.from(host.querySelectorAll("button"));
    const openBundle = buttons().find((node) => node.textContent === "查看详情") as HTMLButtonElement;
    await act(async () => openBundle.click());
    const openVersion = buttons().find((node) => node.textContent === "查看版本事实") as HTMLButtonElement;
    await act(async () => openVersion.click());
    const compositionTab = Array.from(host.querySelectorAll('[role="tab"]')).find(
      (node) => node.textContent === "组合预检与创建",
    ) as HTMLButtonElement;
    await act(async () => compositionTab.click());

    const resolve = buttons().find(
      (node) => node.textContent === "解析并生成不可变 Lock",
    ) as HTMLButtonElement;
    await act(async () => resolve.click());

    expect(assetControlClient.resolveComposition).toHaveBeenCalledTimes(1);
    expect(assetControlClient.getCompositionLock).toHaveBeenCalledWith(
      STORED_COMPOSITION_LOCK_FIXTURE.compositionId,
      STORED_COMPOSITION_LOCK_FIXTURE.revision,
    );
    expect(host.textContent).toContain("服务端 Diff（只读）");

    const displayName = host.querySelector(
      'input[aria-label="Installation display name"]',
    ) as HTMLInputElement;
    await act(async () => {
      const setValue = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )?.set;
      setValue?.call(displayName, "Commerce draft");
      displayName.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const create = buttons().find((node) => node.textContent === "创建 Draft") as HTMLButtonElement;
    await act(async () => create.click());

    expect(assetControlClient.createInstallation).toHaveBeenCalledWith(
      {
        compositionId: STORED_COMPOSITION_LOCK_FIXTURE.compositionId,
        lockRevision: STORED_COMPOSITION_LOCK_FIXTURE.revision,
        overlayRevision: "overlay-1",
        displayName: "Commerce draft",
      },
      expect.objectContaining({ idempotencyKey: expect.any(String) }),
    );
    expect(host.textContent).not.toContain("批准安装");
    expect(host.textContent).not.toContain("Apply Installation");
  });
});
