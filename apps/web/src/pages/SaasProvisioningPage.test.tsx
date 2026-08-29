import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const { apiGet, apiPost, apiPatch } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPatch: vi.fn(),
}));
vi.mock("../api/client", () => ({ apiGet, apiPost, apiPatch }));

import { SaasProvisioningPage } from "./SaasProvisioningPage";

describe("SaasProvisioningPage", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    apiGet.mockResolvedValue({ items: [] });
    apiPost.mockResolvedValue({ ok: true });
    apiPatch.mockResolvedValue({ ok: true });
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    vi.clearAllMocks();
  });

  async function renderPage() {
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(SaasProvisioningPage))));
    await act(async () => void await Promise.resolve());
  }

  it("没有默认负责人且未核对时禁止开通", async () => {
    await renderPage();
    const owner = host.querySelector<HTMLInputElement>('input[placeholder="请输入实际负责人账号"]')!;
    const submit = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent?.includes("开通租户"))!;
    expect(owner.value).toBe("");
    expect(submit.disabled).toBe(true);
    expect(host.textContent).not.toContain("Owner");
    expect(host.textContent).not.toContain("Plan");
    expect(apiPost).not.toHaveBeenCalled();
  });

  it("配额调整先展示确认和取消，不直接写入", async () => {
    apiGet.mockResolvedValue({ items: [{ orgId: "org-one", orgName: "测试组织", plan: "starter", status: "active", ownerSubject: "user:owner", quota: { maxWorkspaces: 5, maxMembers: 10, maxStorageGb: 20 } }] });
    await renderPage();
    const open = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "上调工作区配额")!;
    await act(async () => open.click());
    expect(host.textContent).toContain("确认上调 5 个工作区");
    expect(host.textContent).toContain("取消");
    expect(apiPatch).not.toHaveBeenCalled();
  });
});
