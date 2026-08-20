// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AipOperationalProjectionStrip } from "./AipOperationalProjectionStrip";

const H = "a".repeat(64);
const payload = { tenant: { orgId: "org-org", projectId: "dev-project" }, roles: { definition: 6, bound: 6, enabled: 6, runnable: 6 }, capabilities: { definition: 10, bound: 10, enabled: 10, runnable: 10 }, tools: { definition: 20, bound: 10, enabled: 10, runnable: 8 }, evalGates: { definition: 3, bound: 3, enabled: 3, runnable: 3 }, routes: { definition: 3, bound: 3, enabled: 3, runnable: 3 }, overallReadiness: "ready", blockerCodes: [], sources: { agentReadinessAt: "2026-08-21T01:00:00Z", modelRuntimeAt: "2026-08-21T01:00:01Z" }, snapshotHash: H, generatedAt: "2026-08-21T01:00:02Z" };

afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); localStorage.clear(); document.body.innerHTML = ""; });

describe("AipOperationalProjectionStrip", () => {
  it("加载期不把未知投影为 0", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));
    const host = document.createElement("div"); document.body.append(host); const root = createRoot(host);
    await act(async () => root.render(<AipOperationalProjectionStrip />));
    expect(host.textContent).toContain("正在读取"); expect(host.textContent).not.toContain("0/0");
    await act(async () => root.unmount());
  });
  it("显示同一快照的五类四态数", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
    const host = document.createElement("div"); document.body.append(host); const root = createRoot(host);
    await act(async () => root.render(<AipOperationalProjectionStrip />)); await act(async () => undefined);
    expect(host.textContent).toContain("数字同事"); expect(host.textContent).toContain("6/6 可派发"); expect(host.textContent).toContain("8/20 可派发");
    await act(async () => root.unmount());
  });
  it("读取失败显示不可用而非零数", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const host = document.createElement("div"); document.body.append(host); const root = createRoot(host);
    await act(async () => root.render(<AipOperationalProjectionStrip />)); await act(async () => undefined);
    expect(host.textContent).toContain("不可用"); expect(host.textContent).not.toContain("0/0");
    await act(async () => root.unmount());
  });
});
