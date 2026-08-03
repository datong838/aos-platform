import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CompositionRequest } from "../../../api/assetControl/types";
import { CompositionPanel } from "./CompositionPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const HASH = `sha256:${"a".repeat(64)}` as const;
const REQUEST: CompositionRequest = {
  requested: [{ publisher: "aos", id: "commerce", version: "^1.0.0" }],
  platformApiVersion: "1.0.0",
  platformRelease: "2026.08",
  environment: "dev",
  registrySnapshotHash: HASH,
  currentInstallationRef: null,
};

describe("CompositionPanel", () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("只通过受控 callback 修改请求并触发一次 resolve", async () => {
    const onRequestChange = vi.fn();
    const onResolve = vi.fn();
    await act(async () => root.render(<CompositionPanel request={REQUEST} resolving={false} onRequestChange={onRequestChange} onResolve={onResolve} />));
    const input = host.querySelector<HTMLInputElement>('input[aria-label="Platform release"]');
    if (!input) throw new Error("release input missing");
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, "2026.09");
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(onRequestChange).toHaveBeenCalledWith({ ...REQUEST, platformRelease: "2026.09" });
    const resolve = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((item) => item.textContent?.includes("解析并生成"));
    if (!resolve) throw new Error("resolve button missing");
    await act(async () => resolve.click());
    expect(onResolve).toHaveBeenCalledTimes(1);
  });

  it("pending 与空 requested 禁止重复解析，hash 没有可编辑输入", async () => {
    const onResolve = vi.fn();
    await act(async () => root.render(<CompositionPanel request={REQUEST} resolving onRequestChange={vi.fn()} onResolve={onResolve} />));
    expect(host.querySelector<HTMLButtonElement>("button")?.disabled).toBe(true);
    expect(host.querySelector(`input[value="${HASH}"]`)).toBeNull();
    await act(async () => root.render(<CompositionPanel request={{ ...REQUEST, requested: [] }} resolving={false} onRequestChange={vi.fn()} onResolve={onResolve} />));
    expect(host.textContent).toContain("请先从 Registry 选择至少一个资产版本");
    expect(host.querySelector<HTMLButtonElement>("button")?.disabled).toBe(true);
    expect(onResolve).not.toHaveBeenCalled();
  });
});
