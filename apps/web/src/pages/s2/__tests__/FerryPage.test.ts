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

describe("FerryPage", () => {
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

  it("renders with MOCK fallback bundles", async () => {
    const { FerryPage } = await import("../FerryPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(FerryPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("Ferry 摆渡");
    expect(text).toContain("apollo-core-2.14.1");
    expect(text).toContain("fde-维修派单-1.8.0-rc.2");
    expect(text).toContain("248 MB");
    expect(text).toContain("已签名");
    expect(text).toContain("未签名");
    expect(text).toContain("选择 Bundle");
    expect(text).toContain("校验签名");
    expect(text).toContain("导出介质");
    expect(text).toContain("目标 Spoke 导入");
  });

  it("shows bundle detail with content manifest and signature info", async () => {
    const { FerryPage } = await import("../FerryPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(FerryPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("Bundle 详情");
    expect(text).toContain("内容清单");
    expect(text).toContain("platform-core");
    expect(text).toContain("ontology-engine");
    expect(text).toContain("签名算法");
    expect(text).toContain("cosign-ed25519");
    expect(text).toContain("签名者");
    expect(text).toContain("release-bot@aos-platform");
    expect(text).toContain("目标 Spoke");
    expect(text).toContain("上海生产运行节点");
  });

  it("shows ferry submit button and metrics", async () => {
    const { FerryPage } = await import("../FerryPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(FerryPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("Ferry 提交");
    expect(text).toContain("可用 Bundle");
    expect(text).toContain("已签名");
    expect(text).toContain("待签名");
  });
});
