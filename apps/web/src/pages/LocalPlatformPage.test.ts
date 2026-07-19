import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react";
import { MemoryRouter } from "react-router-dom";
import { LOCAL_PLATFORM_NAME } from "../lib/productCopy";

vi.mock("../api/client", () => ({
  probeApiHealth: vi.fn(async () => ({ ok: true, detail: "ok" })),
}));

vi.mock("../api/apiBase", () => ({
  getApiBase: () => "http://127.0.0.1:8080",
}));

describe("TWC.10 LocalPlatformPage UI-11", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    host.remove();
  });

  it("shows 本机平台, redetect, docs72 panel", async () => {
    const { LocalPlatformPage } = await import("./LocalPlatformPage");
    await act(async () => {
      root.render(
        createElement(
          MemoryRouter,
          null,
          createElement(LocalPlatformPage),
        ),
      );
    });
    await act(async () => {
      await Promise.resolve();
    });
    const text = host.textContent || "";
    expect(text).toContain(LOCAL_PLATFORM_NAME);
    expect(text).toContain("可达");
    expect(host.querySelector('[data-ui="UI-11"]')).toBeTruthy();
    expect(
      host.querySelector('[data-testid="local-platform-redetect"]'),
    ).toBeTruthy();
    expect(
      host.querySelector('[data-testid="local-platform-docs72"]'),
    ).toBeTruthy();
  });
});
