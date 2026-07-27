import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../../api/client", () => ({
  apiGet: vi.fn(async () => ({
    stages: [],
    hotfix: [],
    recalls: [],
  })),
  apiPost: vi.fn(async () => ({ ok: true })),
  apiPut: vi.fn(async () => ({ ok: true })),
  apiDelete: vi.fn(async () => ({ ok: true })),
}));

describe("ReleasesPage", () => {
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

  it("renders Release Channel with MOCK fallback", async () => {
    const { ReleasesPage } = await import("../ReleasesPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(ReleasesPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("Release Channel 管道");
    expect(text).toContain("2.15.0-rc.5");
    expect(text).toContain("2.14.2-beta.1");
    expect(text).toContain("2.14.1");
    expect(text).toContain("CVE-2026-1842");
    expect(text).toContain("推送到紧急通道");
    expect(text).toContain("执行 Recall");
    expect(text).toContain("Recall 回滚");
    expect(text).toContain("Hotfix");
  });

  it("shows pipeline stages correctly", async () => {
    const { ReleasesPage } = await import("../ReleasesPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(ReleasesPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    // rc → beta → stable
    expect(text).toMatch(/rc/);
    expect(text).toMatch(/beta/);
    expect(text).toMatch(/stable/);
    // Push percentages
    expect(text).toContain("100%");
    expect(text).toContain("40%");
    expect(text).toContain("20%");
  });
});
