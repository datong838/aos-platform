import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { normalizeAssetControlError } from "../../../api/assetControl/errors";
import type {
  RegistryBundleDetail,
  RegistryVersionDetail,
} from "../../../api/assetControl/registry";
import {
  REGISTRY_BUNDLE_DETAIL_FIXTURE,
  REGISTRY_BUNDLE_LIST_FIXTURE,
  REGISTRY_VERSION_DETAIL_FIXTURE,
} from "../../../api/assetControl/registryFixtures";
import type { AssetReadState } from "./model";
import { assetBusinessName, RegistryPanel, type RegistryPanelProps } from "./RegistryPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function readState(overrides: Partial<AssetReadState<typeof REGISTRY_BUNDLE_LIST_FIXTURE>> = {}): AssetReadState<typeof REGISTRY_BUNDLE_LIST_FIXTURE> {
  return {
    data: REGISTRY_BUNDLE_LIST_FIXTURE,
    status: "ready",
    error: null,
    refreshing: false,
    stale: false,
    reload: vi.fn(),
    ...overrides,
  };
}

function detailState(overrides: Partial<AssetReadState<RegistryBundleDetail>> = {}): AssetReadState<RegistryBundleDetail> {
  return { data: REGISTRY_BUNDLE_DETAIL_FIXTURE, status: "ready", error: null, refreshing: false, stale: false, reload: vi.fn(), ...overrides };
}

function versionState(overrides: Partial<AssetReadState<RegistryVersionDetail>> = {}): AssetReadState<RegistryVersionDetail> {
  return { data: REGISTRY_VERSION_DETAIL_FIXTURE, status: "ready", error: null, refreshing: false, stale: false, reload: vi.fn(), ...overrides };
}

function button(host: HTMLElement, label: string): HTMLButtonElement {
  const match = Array.from(host.querySelectorAll<HTMLButtonElement>("button"))
    .find((item) => item.textContent?.includes(label));
  if (!match) throw new Error(`button not found: ${label}`);
  return match;
}

describe("RegistryPanel", () => {
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

  async function render(props: Partial<RegistryPanelProps> = {}) {
    await act(async () => root.render(
      <RegistryPanel state={readState()} selected={null} onSelect={vi.fn()} {...props} />,
    ));
  }

  it("资产主名清理开发编号但保留业务含义", () => {
    expect(assetBusinessName("电商增长方案包（D3：W03 客户与私域运营台 + L05 分润异常检测）"))
      .toBe("电商增长方案包（客户与私域运营台与分润异常检测）");
  });

  it("展示真实 Registry 字段并以 publisher 与 bundleId 受控选择", async () => {
    const onSelect = vi.fn();
    await render({ onSelect });

    expect(host.textContent).toContain("aos");
    expect(host.textContent).toContain("solution.example");
    expect(host.textContent).toContain("Example Solution");
    expect(host.textContent).toContain("SolutionPack");
    expect(host.textContent).not.toContain("Mock");

    await act(async () => button(host, "查看详情").click());
    expect(onSelect).toHaveBeenCalledWith({ publisher: "aos", bundleId: "solution.example" });
  });

  it("明确区分 loading、empty、403、404、error 与 stale 并支持重试", async () => {
    const cases = [
      ["loading", "正在读取资产 Registry"],
      ["empty", "Registry 暂无资产包"],
      ["forbidden", "无权查看资产 Registry"],
      ["not_visible_or_missing", "资源不可见或不存在"],
      ["error", "资产 Registry 读取失败"],
    ] as const;

    for (const [status, text] of cases) {
      const reload = vi.fn();
      const error = status === "error"
        ? normalizeAssetControlError({ status: 500, body: { code: "INTERNAL_ERROR", message: "boom", details: null, traceId: "t-1" } })
        : null;
      await render({ state: readState({ status, error, reload }) });
      expect(host.textContent).toContain(text);
      if (status === "forbidden" || status === "not_visible_or_missing") {
        expect(host.textContent).not.toContain("Example Solution");
      }
      if (status !== "loading") {
        await act(async () => button(host, "重试读取").click());
        expect(reload).toHaveBeenCalledTimes(1);
      }
    }

    const reload = vi.fn();
    await render({ state: readState({ stale: true, reload }) });
    expect(host.textContent).toContain("数据可能已过期");
    expect(host.textContent).toContain("Example Solution");
  });

  it("展示真实 Bundle 版本并通过完整坐标选择版本", async () => {
    const onSelectVersion = vi.fn();
    await render({
      selected: { publisher: "aos", bundleId: "solution.example" },
      detailState: detailState(),
      selectedVersion: null,
      onSelectVersion,
    });

    expect(host.textContent).toContain("Bundle 详情");
    expect(host.textContent).toContain("1.0.0");
    expect(host.textContent).toContain("published");
    expect(host.textContent).toContain("Ed25519 · test-key");
    expect(host.textContent).toContain(REGISTRY_BUNDLE_DETAIL_FIXTURE.versions[0].contentHash);
    await act(async () => button(host, "查看版本事实").click());
    expect(onSelectVersion).toHaveBeenCalledWith({ publisher: "aos", bundleId: "solution.example", version: "1.0.0" });
  });

  it("展示版本 contentHash、依赖、artifacts、evidence 与生命周期事件", async () => {
    await render({
      selected: { publisher: "aos", bundleId: "solution.example" },
      detailState: detailState(),
      selectedVersion: { publisher: "aos", bundleId: "solution.example", version: "1.0.0" },
      versionState: versionState(),
      onSelectVersion: vi.fn(),
    });

    expect(host.textContent).toContain("版本只读事实");
    expect(host.textContent).toContain(REGISTRY_VERSION_DETAIL_FIXTURE.contentHash);
    expect(host.textContent).toContain("domain.orders");
    expect(host.textContent).toContain("bundle.yaml");
    expect(host.textContent).toContain("application/yaml");
    expect(host.textContent).toContain("manifest_validation · valid");
    expect(host.textContent).toContain("draft → validated");
    expect(host.textContent).toContain("validated → published");
    expect(host.textContent).not.toMatch(/channel|components|changelog/i);
  });

  it("详情与版本覆盖 loading、403、404、error、stale 且权限失败不泄漏残留数据", async () => {
    const selected = { publisher: "aos", bundleId: "solution.example" } as const;
    const selectedVersion = { ...selected, version: "1.0.0" } as const;
    const statuses = ["loading", "forbidden", "not_visible_or_missing", "error"] as const;
    for (const status of statuses) {
      const error = status === "error"
        ? normalizeAssetControlError({ status: 500, body: { code: "INTERNAL_ERROR", message: "detail boom", details: null, traceId: "t-2" } })
        : null;
      await render({ selected, detailState: detailState({ status, error }), selectedVersion: null });
      if (status === "loading") expect(host.textContent).toContain("正在读取Bundle 详情");
      if (status === "forbidden") expect(host.textContent).toContain("无权查看Bundle 详情");
      if (status === "not_visible_or_missing") expect(host.textContent).toContain("Bundle 详情不可见或不存在");
      if (status === "error") expect(host.textContent).toContain("Bundle 详情读取失败");
      if (status === "forbidden" || status === "not_visible_or_missing") expect(host.textContent).not.toContain("Ed25519 · test-key");
    }

    await render({ selected, detailState: detailState(), selectedVersion, versionState: versionState({ status: "forbidden" }), onSelectVersion: vi.fn() });
    expect(host.textContent).toContain("无权查看版本详情");
    expect(host.textContent).not.toContain("manifest_validation · valid");

    await render({ selected, detailState: detailState({ stale: true }), selectedVersion, versionState: versionState({ stale: true }), onSelectVersion: vi.fn() });
    expect(host.textContent).toContain("当前Bundle 详情是旧数据");
    expect(host.textContent).toContain("当前版本详情是旧数据");
    expect(host.textContent).toContain("manifest_validation · valid");
  });
});
