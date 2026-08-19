// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({ runtimeReadiness: vi.fn(), refreshReadiness: vi.fn(), installEcommerce: vi.fn() }));
vi.mock("../../api/aipAgentControl", () => ({ aipAgentControl: sdk }));
import { CanonicalAgentRegistryPage, precheckDisabledTitle } from "./CanonicalAgentRegistryPage";

const hash = "a".repeat(64);
const tenant = { orgId: "org-org", projectId: "dev-project" };
const runtime = {
  tenant,
  catalog: { tenant, stats: { definitionCount: 6, installedCount: 1, runnableCount: 0, skillDefinitionCount: 37, capabilityDefinitionCount: 10 }, items: [{
    template: { templateId: "ecommerce.content_officer", revision: 1, displayName: "内容官", roleKey: "content_officer", lifecycle: "published", sourceRef: { resourceType: "SolutionPack", resourceId: "solution.ecommerce.growth", revision: "1.3.0", authority: "bundle" }, sourceLicense: "internal", manifest: { logicIds: ["C01"], responsibility: "内容生产", runtimeReadiness: "blocked", blockers: [] }, contentHash: hash },
    instance: { tenant, instanceId: "ecommerce.content_officer.default", instanceRef: { assetType: "AgentInstance", assetId: "ecommerce.content_officer.default", revision: 1, contentHash: hash }, template: { assetType: "AgentTemplate", assetId: "ecommerce.content_officer", revision: 1, contentHash: hash }, status: "provisioning", overlay: { displayName: "内容官", allowedCapabilityIds: [] }, version: 1, updatedAt: "2026-08-15T00:00:00Z" },
    skills: [{ skillId: "content.plan", canonicalLogicId: "C01", lifecycle: "evaluated", requiredCapabilities: ["copy.generate"], riskLevel: "medium" }], requiredCapabilityIds: ["copy.generate"], runtimeReadiness: "blocked", blockers: ["skill_revision_not_published:C01"],
  }] }, capabilityBindings: [], skillBindings: [], bindingStats: { capabilityBindingCount: 0, skillBindingCount: 0, activeCapabilityBindingCount: 0, activeSkillBindingCount: 0 }, evaluatedAt: "2026-08-15T06:00:00Z",
};

describe("precheckDisabledTitle", () => {
  it("快照过期时不误导成「必须先全量技能发布」", () => {
    expect(precheckDisabledTitle(["skill_binding_readiness_stale", "capability_binding_readiness_stale"])).toContain("重评绑定");
    expect(precheckDisabledTitle(["skill_binding_readiness_stale"])).not.toContain("需先完成技能发布、能力绑定");
  });
});

describe("CanonicalAgentRegistryPage", () => {
  let host: HTMLDivElement;
  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    sdk.runtimeReadiness.mockReset().mockResolvedValue(runtime);
    sdk.refreshReadiness.mockReset().mockResolvedValue({
      ...runtime,
      evaluatedAt: "2026-08-15T06:10:00Z",
      catalog: { ...runtime.catalog, stats: { ...runtime.catalog.stats, runnableCount: 1 } },
    });
    sdk.installEcommerce.mockReset();
  });
  afterEach(() => host.remove());
  it("展示六同事、Skill/Capability 绑定覆盖和稳定阻断原因", async () => {
    const root = createRoot(host); await act(async () => root.render(<MemoryRouter><CanonicalAgentRegistryPage /></MemoryRouter>)); await act(async () => undefined);
    expect(host.textContent).toContain("6 个角色定义"); expect(host.textContent).toContain("37 个技能定义"); expect(host.textContent).toContain("内容官"); expect(host.textContent).toContain("技能 0/1 已绑定"); expect(host.textContent).toContain("技能尚未发布"); expect(host.textContent).toContain("热点竞品");
    expect(host.textContent).not.toContain("agent_instance_not_installed");
    expect(host.textContent).not.toContain("ecommerce.content_officer@");
    expect(host.textContent).toContain("查看 1 个技能状态");
    expect(host.textContent).toContain("热点竞品与获客机会研究");
    expect(host.textContent).toContain("评测");
    expect(host.textContent).toContain("未发布 · 未绑定");
    expect(host.textContent).not.toContain("R2 口径");
    expect(host.textContent).not.toContain("evaluated→published");
    expect(host.textContent).not.toContain("Pilot");
    await act(async () => root.unmount());
  });
  it("点击刷新会调用 refreshReadiness 重评绑定", async () => {
    const root = createRoot(host); await act(async () => root.render(<MemoryRouter><CanonicalAgentRegistryPage /></MemoryRouter>)); await act(async () => undefined);
    const refreshBtn = Array.from(host.querySelectorAll("button")).find((btn) => btn.textContent === "刷新");
    expect(refreshBtn).toBeTruthy();
    await act(async () => { refreshBtn!.click(); });
    expect(sdk.refreshReadiness).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("可运行 1");
    await act(async () => root.unmount());
  });
  it("数据参谋 runnable 时展示可运行", async () => {
    sdk.runtimeReadiness.mockResolvedValue({
      ...runtime,
      catalog: {
        ...runtime.catalog,
        stats: { ...runtime.catalog.stats, installedCount: 6, runnableCount: 1 },
        items: [{
          ...runtime.catalog.items[0],
          template: { ...runtime.catalog.items[0].template, templateId: "ecommerce.data_advisor", displayName: "数据参谋", roleKey: "data_advisor", manifest: { ...runtime.catalog.items[0].template.manifest, logicIds: ["D03"], responsibility: "增长方案" } },
          instance: { ...runtime.catalog.items[0].instance!, instanceId: "ecommerce.data_advisor.default", status: "active" },
          runtimeReadiness: "runnable",
          blockers: [],
        }],
      },
    });
    const root = createRoot(host); await act(async () => root.render(<MemoryRouter><CanonicalAgentRegistryPage /></MemoryRouter>)); await act(async () => undefined);
    expect(host.textContent).toContain("可运行 1");
    expect(host.textContent).toMatch(/可运行/);
    expect(host.textContent).toContain("数据参谋");
    expect(host.textContent).not.toContain("Pilot");
    await act(async () => root.unmount());
  });
});
