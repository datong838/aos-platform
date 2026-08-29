import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../../api/client", () => ({
  apiGet: vi.fn(async (path: string) => path === "/v1/apollo/fleet"
    ? { hub: { id: "dev-hub", status: "online" }, spokes: [], channels: [{ id: "dev" }] }
    : {}),
  apiPost: vi.fn(), apiPut: vi.fn(), apiDelete: vi.fn(),
}));

describe("HubFleetPage", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });
  it("renders tenant-scoped empty fleet without sample spokes", async () => {
    const { HubFleetPage } = await import("../HubFleetPage");
    await act(async () => { root.render(createElement(MemoryRouter, null, createElement(HubFleetPage))); await Promise.resolve(); });
    const text = host.textContent || "";
    expect(text).toContain("dev-hub");
    expect(text).toContain("0 / 0");
    expect(text).toContain("尚未登记运行节点");
    expect(text).not.toContain("上海生产运行节点");
  });
});
