import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { normalizeAssetControlError } from "../../../api/assetControl/errors";
import { REGISTRY_BUNDLE_LIST_FIXTURE } from "../../../api/assetControl/registryFixtures";
import type { AssetReadState } from "./model";
import { RegistryPanel, type RegistryPanelProps } from "./RegistryPanel";

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
});
