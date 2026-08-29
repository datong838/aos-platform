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

  it("权威为空时只展示可信空态，不生成示例变更单", async () => {
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
    expect(text).toContain("当前工作区没有变更单");
    expect(text).toContain("页面不会生成示例审批记录");
    expect(text).not.toContain("CHG-2026");
  });

  it("空态不暴露虚构审批人与审批流", async () => {
    const { ChangeOrdersPage } = await import("../ChangeOrdersPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(ChangeOrdersPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).not.toContain("张运维");
    expect(text).not.toContain("李安全");
    expect(text).not.toContain("王总监");
  });

  it("没有待审批权威记录时不提供决策按钮", async () => {
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
    expect(approveBtn).toBeFalsy();
    expect(rejectBtn).toBeFalsy();
  });
});
