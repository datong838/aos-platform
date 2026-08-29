import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react";
import { MemoryRouter } from "react-router-dom";

const apiGet = vi.fn(async () => ({}));
vi.mock("../../../api/client", () => ({ apiGet, apiPost: vi.fn(), apiPut: vi.fn(), apiDelete: vi.fn() }));

describe("SpokeDetailPage", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { apiGet.mockClear(); host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });
  it("requires exact fleet selection and does not request a default production spoke", async () => {
    const { SpokeDetailPage } = await import("../SpokeDetailPage");
    await act(async () => { root.render(createElement(MemoryRouter, null, createElement(SpokeDetailPage))); await Promise.resolve(); });
    expect(host.textContent).toContain("请先从 Hub 舰队选择");
    expect(host.textContent).not.toContain("上海生产运行节点");
    expect(apiGet).not.toHaveBeenCalled();
  });
});
