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

describe("ChangeOrdersPage", () => {
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

  it("renders with MOCK fallback change orders", async () => {
    const { ChangeOrdersPage } = await import("../ChangeOrdersPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(ChangeOrdersPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("变更审批");
    expect(text).toContain("CHG-2026-0412");
    expect(text).toContain("CHG-2026-0408");
    expect(text).toContain("CHG-2026-0395");
    expect(text).toContain("待审批");
    expect(text).toContain("已通过");
    expect(text).toContain("已驳回");
    expect(text).toContain("资产包升级");
    expect(text).toContain("配置变更");
    expect(text).toContain("新模块部署");
  });

  it("shows change order detail with approval pipeline", async () => {
    const { ChangeOrdersPage } = await import("../ChangeOrdersPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(ChangeOrdersPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("审批流");
    expect(text).toContain("提交");
    expect(text).toContain("安全评审");
    expect(text).toContain("变更委员会");
    expect(text).toContain("张运维");
    expect(text).toContain("李安全");
    expect(text).toContain("王总监");
    expect(text).toContain("影响范围");
    expect(text).toContain("计划窗口");
  });

  it("shows approve and reject buttons for pending order", async () => {
    const { ChangeOrdersPage } = await import("../ChangeOrdersPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(ChangeOrdersPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const buttons = host.querySelectorAll("button");
    const approveBtn = Array.from(buttons).find((b) => b.textContent === "批准");
    const rejectBtn = Array.from(buttons).find((b) => b.textContent === "驳回");
    expect(approveBtn).toBeTruthy();
    expect(rejectBtn).toBeTruthy();
  });
});
