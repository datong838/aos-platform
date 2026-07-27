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

  it("renders with MOCK fallback config overrides", async () => {
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
    expect(text).toContain("aip.model.default");
    expect(text).toContain("db.connection.poolSize");
    expect(text).toContain("integration.apiKey");
    expect(text).toContain("全局");
    expect(text).toContain("环境");
    expect(text).toContain("Spoke");
  });

  it("masks sensitive values by default", async () => {
    const { ConfigSecretsPage } = await import("../ConfigSecretsPage");
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(ConfigSecretsPage)));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const text = host.textContent || "";
    // Sensitive value should be masked
    expect(text).toContain("••••");
    expect(text).not.toContain("sk-aip-xxxxxxxxxxxxxxxxxxxx");
    // Non-sensitive values should be visible
    expect(text).toContain("glm-4-flash");
    expect(text).toContain("50");
  });

  it("shows maintenance window and new config button", async () => {
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
    expect(text).toContain("开始时间");
    expect(text).toContain("结束时间");
    expect(text).toContain("2026-07-28 02:00");
    expect(text).toContain("2026-07-28 04:00");
    expect(text).toContain("新增配置");

    const buttons = host.querySelectorAll("button");
    const newBtn = Array.from(buttons).find((b) =>
      b.textContent?.includes("新增配置"),
    );
    expect(newBtn).toBeTruthy();
  });
});
