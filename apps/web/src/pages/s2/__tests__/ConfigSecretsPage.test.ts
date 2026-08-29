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

describe("ConfigSecretsPage", () => {
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

  it("权威为空时只展示配置元数据可信空态", async () => {
    const { ConfigSecretsPage } = await import("../ConfigSecretsPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(ConfigSecretsPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("配置与密钥");
    expect(text).toContain("当前没有可审计配置项");
    expect(text).toContain("不会生成模型、连接池、密钥或维护窗口示例");
    expect(text).not.toContain("aip.model.default");
    expect(text).not.toContain("integration.apiKey");
  });

  it("页面不读取或显示密钥正文", async () => {
    const { ConfigSecretsPage } = await import("../ConfigSecretsPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(ConfigSecretsPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("页面永不读取或显示密钥正文");
    expect(text).not.toContain("vault:secret/");
    expect(text).not.toContain("sk-");
  });

  it("未登记维护窗口时明确空态且仅允许走变更审批", async () => {
    const { ConfigSecretsPage } = await import("../ConfigSecretsPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(ConfigSecretsPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    expect(text).toContain("维护窗口");
    expect(text).toContain("尚未登记");
    expect(text).toContain("创建配置变更");
    expect(text).not.toContain("2026-07-28");
  });
});
