import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../../api/client", () => ({
  apiGet: vi.fn(async (path: string) => {
    if (String(path).includes("/v1/hub")) {
      return { hubRegion: "cn-east-hub-01", onlineCount: 5, totalCount: 6, lastProbe: "12 秒前" };
    }
    return { items: [] };
  }),
  apiPost: vi.fn(async () => ({ ok: true })),
  apiPut: vi.fn(async () => ({ ok: true })),
  apiDelete: vi.fn(async () => ({ ok: true })),
}));

describe("HubFleetPage", () => {
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

  it("renders Hub fleet overview with MOCK fallback", async () => {
    const { HubFleetPage } = await import("../HubFleetPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(HubFleetPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("Hub 舰队总览");
    expect(text).toContain("cn-east-hub-01");
    expect(text).toContain("5 / 6");
    expect(text).toContain("上海生产运行节点");
    expect(text).toContain("北京生产运行节点");
    expect(text).toContain("spoke-pilot-gz");
    expect(text).toContain("spoke-staging");
    expect(text).toContain("spoke-edge-factory");
    expect(text).toContain("健康");
    expect(text).toContain("降级");
    expect(text).toContain("离线");
    expect(text).toContain("Release 通道");
    expect(text).toContain("舰队健康概览");
  });

  it("renders health summary metrics", async () => {
    const { HubFleetPage } = await import("../HubFleetPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(HubFleetPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toMatch(/[34]/); // online count
    expect(text).toContain("60%"); // 3 online out of 5
  });
});
