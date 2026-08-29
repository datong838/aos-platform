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

  it("接口为空时展示可信空态，不注入固定发布事实", async () => {
    const { ReleasesPage } = await import("../ReleasesPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(ReleasesPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("Release 通道");
    expect(text).toContain("当前没有可核验的发布记录");
    expect(text).toContain("当前没有已登记的紧急补丁");
    expect(text).toContain("当前没有可核验的回滚记录");
    expect(text).not.toContain("2.15.0-rc.5");
    expect(text).not.toContain("CVE-2026-1842");
    expect(text).not.toContain("推送到紧急通道");
    expect(text).not.toContain("执行 Recall");
  });

  it("只提供审批入口，不提供客户端伪执行按钮", async () => {
    const { ReleasesPage } = await import("../ReleasesPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(ReleasesPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("查看或创建变更审批");
    expect(text).toContain("本页不直接推送");
    expect(text).toContain("不在历史列表直接执行");
  });
});
