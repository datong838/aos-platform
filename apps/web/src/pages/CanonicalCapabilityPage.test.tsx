// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({ listCapabilities: vi.fn(), runtimeReadiness: vi.fn() }));
vi.mock("../api/aipAgentControl", () => ({ aipAgentControl: sdk }));
import { CanonicalCapabilityPage } from "./CanonicalCapabilityPage";

const tenant = { orgId: "org-org", projectId: "dev-project" };
describe("CanonicalCapabilityPage", () => {
  let host: HTMLDivElement;
  beforeEach(() => {
    host = document.createElement("div"); document.body.appendChild(host);
    sdk.listCapabilities.mockResolvedValue({ tenant, count: 1, availableCount: 0, items: [{ capabilityId: "copy.generate", revision: 1, displayName: "文案生成", lifecycle: "published", aliases: [], riskLevel: "medium", readiness: "blocked", readinessReasons: ["provider_missing"], contentHash: "a".repeat(64) }] });
    sdk.runtimeReadiness.mockResolvedValue({ tenant, catalog: { tenant, items: [], stats: { definitionCount: 6, installedCount: 0, runnableCount: 0, skillDefinitionCount: 37, capabilityDefinitionCount: 10 } }, capabilityBindings: [], skillBindings: [], bindingStats: { capabilityBindingCount: 0, skillBindingCount: 0, activeCapabilityBindingCount: 0, activeSkillBindingCount: 0 }, evaluatedAt: "2026-08-15T06:00:00Z" });
  });
  afterEach(() => host.remove());
  it("显示组织绑定空态并禁用没有依赖快照的操作", async () => {
    const root = createRoot(host); await act(async () => root.render(<MemoryRouter><CanonicalCapabilityPage /></MemoryRouter>)); await act(async () => undefined);
    expect(host.textContent).toContain("文案生成"); expect(host.textContent).toContain("组织绑定 0");
    expect(host.textContent).toContain("未绑定");
    expect(host.textContent).toContain("去目录绑定");
    for (const dimension of ["Provider", "Route", "Eval", "License", "Data", "Tool", "Budget"]) expect(host.textContent).toContain(`${dimension} —`);
    const action = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("预检")) as HTMLButtonElement;
    expect(action.disabled).toBe(true);
    await act(async () => root.unmount());
  });
});
