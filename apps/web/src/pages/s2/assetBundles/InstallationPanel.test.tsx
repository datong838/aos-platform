import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { InstallationListResponse } from "../../../api/assetControl/types";
import type { AssetReadState } from "./model";
import { InstallationPanel, type InstallationPanelProps } from "./InstallationPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const RESPONSE: InstallationListResponse = {
  items: [{
    installationId: "22222222-2222-4222-8222-222222222222",
    displayName: "Commerce installation",
    state: "active",
    currentRevision: 6,
    activeRevision: 6,
    previousActiveRevision: 5,
    etagVersion: 6,
    createdAt: "2026-08-03T08:00:00Z",
    updatedAt: "2026-08-03T09:00:00Z",
  }],
  total: 45,
  limit: 20,
  offset: 20,
};

function readState(overrides: Partial<AssetReadState<InstallationListResponse>> = {}): AssetReadState<InstallationListResponse> {
  return { data: RESPONSE, status: "ready", error: null, refreshing: false, stale: false, reload: vi.fn(), ...overrides };
}

function button(host: HTMLElement, label: string): HTMLButtonElement {
  const match = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((item) => item.textContent?.includes(label));
  if (!match) throw new Error(`button not found: ${label}`);
  return match;
}

describe("InstallationPanel", () => {
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

  async function render(props: Partial<InstallationPanelProps> = {}) {
    await act(async () => root.render(
      <InstallationPanel
        state={readState()}
        request={{ limit: 20, offset: 20 }}
        selectedInstallationId={null}
        onStateChange={vi.fn()}
        onPageChange={vi.fn()}
        onSelect={vi.fn()}
        {...props}
      />,
    ));
  }

  it("展示服务端列表事实并通过 callback 选择详情和状态", async () => {
    const onSelect = vi.fn();
    const onStateChange = vi.fn();
    await render({ onSelect, onStateChange });

    expect(host.textContent).toContain("Commerce installation");
    expect(host.textContent).toContain("active");
    expect(host.textContent).toContain("6 / 5");
    await act(async () => button(host, "查看事件").click());
    expect(onSelect).toHaveBeenCalledWith("22222222-2222-4222-8222-222222222222");

    const select = host.querySelector<HTMLSelectElement>('select[aria-label="安装状态筛选"]');
    if (!select) throw new Error("state select not found");
    await act(async () => {
      select.value = "submitted";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(onStateChange).toHaveBeenCalledWith("submitted");
  });

  it("严格依据服务端 total、limit、offset 翻页", async () => {
    const onPageChange = vi.fn();
    await render({ onPageChange });

    expect(host.textContent).toContain("第 21–21 条 / 共 45 条 · limit 20 · offset 20");
    await act(async () => button(host, "上一页").click());
    await act(async () => button(host, "下一页").click());
    expect(onPageChange).toHaveBeenNthCalledWith(1, 0);
    expect(onPageChange).toHaveBeenNthCalledWith(2, 40);
  });

  it("空列表与旧数据均明确呈现且不产生 mutation 入口", async () => {
    await render({ state: readState({ data: { items: [], total: 0, limit: 20, offset: 0 }, status: "empty" }) });
    expect(host.textContent).toContain("暂无安装记录");
    await render({ state: readState({ stale: true }) });
    expect(host.textContent).toContain("旧数据");
    expect(host.textContent).not.toMatch(/创建|提交|审批|回滚/);
  });
});
