// @vitest-environment jsdom

import { createElement } from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}));

vi.mock("../api/client", () => ({
  apiGet: (path: string) => apiMocks.get(path),
  apiPost: (path: string, body: unknown) => apiMocks.post(path, body),
  apiPatch: (path: string, body: unknown) => apiMocks.patch(path, body),
}));

import { CanvasPage } from "./CanvasPage";

describe("CanvasPage · 发布入口", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    apiMocks.get.mockReset();
    apiMocks.post.mockReset();
    apiMocks.patch.mockReset();
    apiMocks.get.mockImplementation(async (path: string) => {
      if (path === "/v1/modules") {
        return {
          items: [
            {
              id: "mod-canvas",
              name: "Canvas Module",
              objectType: "WorkOrder",
              widgets: [],
            },
          ],
        };
      }
      if (path === "/v1/widget-plugins") return { palette: [] };
      if (path.includes("/variables")) return { items: [] };
      throw new Error(`unexpected GET ${path}`);
    });
    apiMocks.post.mockResolvedValue({ items: [] });
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("发布控件只导航正式 Publish 流水线并携带当前 moduleId", async () => {
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(CanvasPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    const publishLink = Array.from(host.querySelectorAll("a")).find(
      (item) => item.textContent?.trim() === "发布",
    );
    expect(publishLink?.getAttribute("href")).toBe(
      "/workshop/publish?moduleId=mod-canvas",
    );
    expect(apiMocks.patch).not.toHaveBeenCalledWith(
      expect.stringContaining("/v1/modules/"),
      expect.objectContaining({ status: "published" }),
    );
  });
});
