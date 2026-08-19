// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({ listInstances: vi.fn(), runtimeReadiness: vi.fn() }));
vi.mock("../../api/aipAgentControl", () => ({ aipAgentControl: sdk }));
import { CanonicalAgentsPage } from "./CanonicalAgentsPage";

const hash = "a".repeat(64);
const tenant = { orgId: "org-org", projectId: "dev-project" };
const instance = {
  tenant,
  instanceId: "ecommerce.content_officer.default",
  instanceRef: { assetType: "AgentInstance", assetId: "ecommerce.content_officer.default", revision: 1, contentHash: hash },
  template: { assetType: "AgentTemplate", assetId: "ecommerce.content_officer", revision: 1, contentHash: hash },
  status: "provisioning",
  overlay: { displayName: "内容官", allowedCapabilityIds: [] },
  version: 1,
  updatedAt: "2026-08-16T00:00:00Z",
};

const blockedRuntime = {
  tenant,
  catalog: {
    tenant,
    stats: { definitionCount: 6, installedCount: 1, runnableCount: 0, skillDefinitionCount: 37, capabilityDefinitionCount: 10 },
    items: [{
      template: {
        templateId: "ecommerce.content_officer",
        revision: 1,
        displayName: "内容官",
        roleKey: "content_officer",
        lifecycle: "published" as const,
        sourceRef: { resourceType: "SolutionPack", resourceId: "solution.ecommerce.growth", revision: "1", authority: "asset-registry" },
        sourceLicense: "internal",
        manifest: { logicIds: ["C02"], responsibility: "内容", runtimeReadiness: "blocked", blockers: ["skill_binding_readiness_stale"] },
        contentHash: hash,
      },
      instance: null,
      skills: [],
      requiredCapabilityIds: [],
      runtimeReadiness: "blocked" as const,
      blockers: ["skill_binding_readiness_stale"],
    }],
  },
  capabilityBindings: [],
  skillBindings: [],
  bindingStats: { capabilityBindingCount: 0, skillBindingCount: 0, activeCapabilityBindingCount: 0, activeSkillBindingCount: 0 },
  evaluatedAt: "2026-08-16T00:00:00Z",
};

describe("CanonicalAgentsPage", () => {
  let host: HTMLDivElement;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    sdk.listInstances.mockReset().mockResolvedValue({ tenant, items: [instance], count: 1 });
    sdk.runtimeReadiness.mockReset().mockResolvedValue(blockedRuntime);
  });

  afterEach(() => host.remove());

  it("只展示 canonical AgentInstance 并诚实显示未就绪阻断", async () => {
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><CanonicalAgentsPage /></MemoryRouter>));
    await act(async () => undefined);
    expect(host.textContent).toContain("内容官");
    expect(host.textContent).toContain("待配置");
    expect(host.textContent).toContain("技能绑定就绪快照已过期");
    expect(host.textContent).not.toContain("MOCK_AGENTS");
    expect(host.textContent).not.toContain("skill_binding_readiness_stale");
    expect(host.textContent).not.toContain("ecommerce.content_officer.default");
    expect(host.textContent).not.toContain("ecommerce.content_officer@");
    await act(async () => root.unmount());
  });

  it("目录 runnable 时显示可运行说明", async () => {
    sdk.runtimeReadiness.mockResolvedValue({
      ...blockedRuntime,
      catalog: {
        ...blockedRuntime.catalog,
        stats: { ...blockedRuntime.catalog.stats, runnableCount: 1 },
        items: [{ ...blockedRuntime.catalog.items[0], runtimeReadiness: "runnable", blockers: [] }],
      },
    });
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><CanonicalAgentsPage /></MemoryRouter>));
    await act(async () => undefined);
    expect(host.textContent).toContain("可运行（目录已就绪");
    expect(host.textContent).toContain("可运行 1/1");
    expect(host.textContent).not.toContain("Pilot");
    await act(async () => root.unmount());
  });

  it("接口失败时显示错误且不注入样例", async () => {
    sdk.listInstances.mockRejectedValueOnce(new Error("registry unavailable"));
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><CanonicalAgentsPage /></MemoryRouter>));
    await act(async () => undefined);
    expect(host.textContent).toContain("实例读取失败：registry unavailable");
    expect(host.textContent).not.toContain("内容官");
    await act(async () => root.unmount());
  });
});
