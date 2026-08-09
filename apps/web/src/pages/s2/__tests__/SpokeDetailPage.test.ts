import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../../api/client", () => ({
  apiGet: vi.fn(async () => ({
    items: [],
  })),
  apiPost: vi.fn(async () => ({ ok: true })),
  apiPut: vi.fn(async () => ({ ok: true })),
  apiDelete: vi.fn(async () => ({ ok: true })),
}));

describe("SpokeDetailPage", () => {
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

  it("renders Spoke detail with MOCK fallback", async () => {
    const { SpokeDetailPage } = await import("../SpokeDetailPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(SpokeDetailPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("上海生产运行节点");
    expect(text).toContain("上海生产区");
    expect(text).toContain("健康");
    expect(text).toContain("platform-2.14.1");
    expect(text).toContain("Full Foundry 运行时");
    expect(text).toContain("出站轮询");
    expect(text).toContain("Full Spoke");
    expect(text).toContain("Lite Spoke");
    expect(text).toContain("Probe 详情");
    expect(text).toContain("资源使用");
  });

  it("has all tab labels", async () => {
    const { SpokeDetailPage } = await import("../SpokeDetailPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(SpokeDetailPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("Overview");
    expect(text).toContain("Plan");
    expect(text).toContain("Plan Diff");
    expect(text).toContain("Config");
    expect(text).toContain("Maintenance Window");
  });

  it("shows deployment plans on Plan tab", async () => {
    const { SpokeDetailPage } = await import("../SpokeDetailPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(SpokeDetailPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    // Click Plan tab
    const tabs = host.querySelectorAll('[role="tab"]');
    const planTab = Array.from(tabs).find(
      (t) => t.textContent?.includes("Plan") && !t.textContent?.includes("Diff"),
    );
    if (planTab) {
      await act(async () => {
        (planTab as HTMLButtonElement).click();
      });
    }

    const text = host.textContent || "";
    expect(text).toContain("部署计划");
    expect(text).toContain("Bundle apollo-core");
    expect(text).toContain("FDE 维修派单资产包");
    expect(text).toContain("已应用");
    expect(text).toContain("待应用");
  });

  it("renders config overrides with source badges", async () => {
    const { SpokeDetailPage } = await import("../SpokeDetailPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(SpokeDetailPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    // Click Config tab
    const tabs = host.querySelectorAll('[role="tab"]');
    const configTab = Array.from(tabs).find(
      (t) => t.textContent?.includes("Config") && !t.textContent?.includes("Plan Diff"),
    );
    if (configTab) {
      await act(async () => {
        (configTab as HTMLButtonElement).click();
      });
    }

    const text = host.textContent || "";
    expect(text).toContain("log_level");
    expect(text).toContain("vault");
    expect(text).toContain("spoke");
    expect(text).toContain("hub");
  });

  it("shows maintenance window", async () => {
    const { SpokeDetailPage } = await import("../SpokeDetailPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(SpokeDetailPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    // Click Maintenance Window tab
    const tabs = host.querySelectorAll('[role="tab"]');
    const mwTab = Array.from(tabs).find((t) => t.textContent?.includes("Maintenance"));
    if (mwTab) {
      await act(async () => {
        (mwTab as HTMLButtonElement).click();
      });
    }

    const text = host.textContent || "";
    expect(text).toContain("维护窗口");
    expect(text).toContain("2026-07-28");
    expect(text).toContain("计划内维护");
  });
});
