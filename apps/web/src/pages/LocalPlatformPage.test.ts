import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react";
import { MemoryRouter } from "react-router-dom";
import { LOCAL_PLATFORM_NAME } from "../lib/productCopy";

const probeApiHealth = vi.fn(async () => ({ ok: true, detail: "ok" }));
const apiGet = vi.fn(async (path: string) => {
  if (path.includes("/hub")) {
    return {
      ok: true,
      endpoint: "https://registry-1.docker.io/v2/",
      message: "可达",
      hint: "Win: scripts/demo/start-local.ps1 · mac/Linux: start-local.sh",
      latencyMs: 120,
    };
  }
  return {
    ok: true,
    items: [
      { id: "pg", name: "PostgreSQL", endpoint: "127.0.0.1:5433", ok: true },
      { id: "minio", name: "MinIO", endpoint: "127.0.0.1:9000", ok: true },
    ],
    ensureAllowed: true,
  };
});
const apiPost = vi.fn(async () => ({
  ok: true,
  action: "already_up",
  message: "依赖已就绪",
  items: [
    { id: "pg", name: "PostgreSQL", endpoint: "127.0.0.1:5433", ok: true },
    { id: "minio", name: "MinIO", endpoint: "127.0.0.1:9000", ok: true },
  ],
}));

vi.mock("../api/client", () => ({
  probeApiHealth: (...args: unknown[]) => probeApiHealth(...args),
  apiGet: (...args: unknown[]) => apiGet(...args),
  apiPost: (...args: unknown[]) => apiPost(...args),
}));

vi.mock("../api/apiBase", () => ({
  getApiBase: () => "http://127.0.0.1:8080",
}));

describe("TWC.10 / 165 LocalPlatformPage", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    probeApiHealth.mockClear();
    apiGet.mockClear();
    apiPost.mockClear();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    host.remove();
  });

  it("shows 本机探活 under 运维交付 and real deps status", async () => {
    const { LocalPlatformPage } = await import("./LocalPlatformPage");
    await act(async () => {
      root.render(
        createElement(MemoryRouter, null, createElement(LocalPlatformPage)),
      );
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    const text = host.textContent || "";
    expect(text).toContain(LOCAL_PLATFORM_NAME);
    expect(text).toContain("运维交付");
    expect(text).toContain("可达");
    expect(text).toContain("依赖已就绪");
    expect(text).toContain("Docker Hub");
    expect(text).toContain("start-local.ps1");
    expect(text).not.toContain("禁止演示临时候补");
    expect(text).not.toContain("不是 Apollo");
    expect(text).not.toContain("摘要探活不在本页伪造");
    expect(text).not.toMatch(/仅为演示|演示专用|彩排按钮/);
    expect(host.querySelector('[data-ui="UI-11"]')).toBeTruthy();
    expect(
      host.querySelector('[data-testid="local-platform-redetect"]'),
    ).toBeTruthy();
    expect(
      host.querySelector('[data-testid="local-platform-ops-guide"]'),
    ).toBeTruthy();
    expect(
      host.querySelector('[data-testid="local-platform-hub-row"]'),
    ).toBeTruthy();
    expect(apiGet).toHaveBeenCalled();
    expect(apiGet.mock.calls.some((c) => String(c[0]).includes("/hub"))).toBe(
      true,
    );
    expect(apiPost).not.toHaveBeenCalled();
  });

  it("auto-ensures deps when probe reports down", async () => {
    apiGet.mockImplementation(async (path: string) => {
      if (String(path).includes("/hub")) {
        return {
          ok: false,
          message: "不可达 · timeout",
          hint: "Hub 仅影响拉新镜像。栈已绿可忽略。缺镜像：mac/Linux → start-local-native.sh；Win → start-local.ps1",
        };
      }
      return {
        ok: false,
        items: [
          { id: "pg", name: "PostgreSQL", endpoint: "127.0.0.1:5433", ok: false },
          { id: "minio", name: "MinIO", endpoint: "127.0.0.1:9000", ok: false },
        ],
        ensureAllowed: true,
      };
    });
    apiPost.mockResolvedValueOnce({
      ok: true,
      action: "started",
      message: "依赖已自动拉起并就绪",
      items: [
        { id: "pg", name: "PostgreSQL", endpoint: "127.0.0.1:5433", ok: true },
        { id: "minio", name: "MinIO", endpoint: "127.0.0.1:9000", ok: true },
      ],
    });
    const { LocalPlatformPage } = await import("./LocalPlatformPage");
    await act(async () => {
      root.render(
        createElement(MemoryRouter, null, createElement(LocalPlatformPage)),
      );
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(apiPost).toHaveBeenCalled();
    expect(host.textContent || "").toContain("依赖已自动拉起并就绪");
    expect(host.textContent || "").toContain("栈已绿可忽略");
  });
});
