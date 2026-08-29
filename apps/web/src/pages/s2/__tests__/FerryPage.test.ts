import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../../api/client", () => ({
  apiGet: vi.fn(async (path: string) => path.endsWith("/status")
    ? { exportImport: "200", skopeo: true, skopeoMode: "docker", cosign: true, cosignCliMode: "docker" }
    : { items: [] }),
  apiPost: vi.fn(), apiPut: vi.fn(), apiDelete: vi.fn(),
}));

describe("FerryPage", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });
  it("shows current readiness and honest empty assets without submit action", async () => {
    const { FerryPage } = await import("../FerryPage");
    await act(async () => { root.render(createElement(MemoryRouter, null, createElement(FerryPage))); await Promise.resolve(); });
    const text = host.textContent || "";
    expect(text).toContain("导出与导入合同");
    expect(text).toContain("当前没有已登记资产包");
    expect(text).not.toContain("apollo-core-2.14.1");
    expect(text).not.toContain("Ferry 提交");
  });
});
