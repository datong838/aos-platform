// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({ listCapabilities: vi.fn(), runtimeReadiness: vi.fn() }));
vi.mock("../api/aipAgentControl", () => ({ aipAgentControl: sdk }));
vi.mock("../components/aip/AipOperationalProjectionStrip", () => ({
  AipOperationalProjectionStrip: () => null,
}));
import { CanonicalCapabilityPage, orgBindingStatusLabel } from "./CanonicalCapabilityPage";

const tenant = { orgId: "org-org", projectId: "dev-project" };
describe("CanonicalCapabilityPage", () => {
  let host: HTMLDivElement;
  beforeEach(() => {
    host = document.createElement("div"); document.body.appendChild(host);
    sdk.listCapabilities.mockResolvedValue({ tenant, count: 1, availableCount: 0, items: [{ capabilityId: "copy.generate", revision: 1, displayName: "文案生成", lifecycle: "published", aliases: [], inputSchemaRef: { assetId: "CopyGenerationRequest" }, outputSchemaRef: { assetId: "ContentVariantListRef" }, requiredDataRefs: [], requiredToolRefs: [], requiredCapabilityRefs: [], evalPackRef: null, riskLevel: "medium", readiness: "blocked", readinessReasons: ["provider_missing"], contentHash: "a".repeat(64) }] });
    sdk.runtimeReadiness.mockResolvedValue({ tenant, catalog: { tenant, items: [], stats: { definitionCount: 6, installedCount: 0, runnableCount: 0, skillDefinitionCount: 37, capabilityDefinitionCount: 10 } }, capabilityBindings: [], skillBindings: [], bindingStats: { capabilityBindingCount: 0, skillBindingCount: 0, activeCapabilityBindingCount: 0, activeSkillBindingCount: 0 }, evaluatedAt: "2026-08-15T06:00:00Z" });
  });
  afterEach(() => host.remove());

  it("orgBindingStatusLabel：有绑定时绝不返回未绑定", () => {
    expect(orgBindingStatusLabel(0, 0)).toBe("未绑定");
    expect(orgBindingStatusLabel(1, 1)).not.toContain("未绑定");
    expect(orgBindingStatusLabel(1, 0)).not.toContain("未绑定");
  });

  it("显示组织绑定空态并引导到可完成的绑定流程", async () => {
    const root = createRoot(host); await act(async () => root.render(<MemoryRouter><CanonicalCapabilityPage /></MemoryRouter>)); await act(async () => undefined);
    expect(host.textContent).toContain("文案生成"); expect(host.textContent).toMatch(/组织绑定\s*0/);
    expect(host.textContent).toContain("组织绑定：未绑定");
    expect(host.textContent).toContain("定义就绪");
    expect(host.textContent).toContain("组织绑定侧");
    expect(host.textContent).toContain("定义层");
    expect(host.textContent).toContain("去目录绑定");
    expect(host.textContent).toContain("CopyGenerationRequest");
    expect(host.textContent).toContain("ContentVariantListRef");
    expect(host.textContent).toMatch(/已激活\s*0/);
    expect(host.textContent).not.toContain("copy.generate@");
    expect(host.textContent).not.toContain("Capability");
    for (const dimension of ["供应商", "路由", "评测门", "许可", "数据依赖", "工具依赖", "预算策略"]) expect(host.textContent).toContain(`${dimension} —`);
    expect(host.textContent).not.toContain("Provider —");
    const action = Array.from(host.querySelectorAll("a")).find((link) => link.textContent?.includes("补齐预检条件"));
    expect(action?.getAttribute("href")).toBe("/aip/agent-registry?capabilityId=copy.generate&revision=1");
    expect(host.textContent).toContain("进入激活确认");
    await act(async () => root.unmount());
  });

  it("运行条件按钮可展开精确版本、快照与四类反向追溯入口", async () => {
    sdk.runtimeReadiness.mockResolvedValue({
      tenant,
      catalog: { tenant, items: [{ template: { displayName: "内容官" }, requiredCapabilityIds: ["copy.generate"], skills: [] }], stats: { definitionCount: 6, installedCount: 1, runnableCount: 1, skillDefinitionCount: 37, capabilityDefinitionCount: 10 } },
      capabilityBindings: [{
        bindingId: "copy-r1", status: "active", version: 1,
        capability: { assetId: "copy.generate", revision: 1 },
        dependencies: { providerRef: { assetId: "provider-1" }, modelRouteRef: { assetId: "route-1" }, evalGateRef: { assetId: "eval-1" }, licenseEvidenceRefs: [{ resourceId: "license-1" }], dataDependencyRefs: [{ assetId: "data-1" }], toolDependencyRefs: [{ assetId: "tool-1" }], budgetPolicyRef: { assetId: "budget-1" } },
        readinessReasons: [], dependencySnapshotHash: "h".repeat(64), readinessExpiresAt: "2099-01-01T00:00:00Z",
      }],
      skillBindings: [], bindingStats: { capabilityBindingCount: 1, skillBindingCount: 0, activeCapabilityBindingCount: 1, activeSkillBindingCount: 0 }, evaluatedAt: "2026-08-19T06:00:00Z",
    });
    const root = createRoot(host); await act(async () => root.render(<MemoryRouter><CanonicalCapabilityPage /></MemoryRouter>)); await act(async () => undefined);
    expect(host.textContent).toContain("内容官");
    const button = Array.from(host.querySelectorAll("button")).find(item => item.textContent === "核对运行条件") as HTMLButtonElement;
    await act(async () => button.click());
    expect(host.textContent).toContain("copy.generate · v1");
    expect(host.textContent).toContain("依赖快照：有效");
    for (const label of ["查看使用该能力的数字同事", "查看业务逻辑", "查看工具依赖", "查看工作台贡献"]) expect(host.textContent).toContain(label);
    await act(async () => root.unmount());
  });

  it("已有组织绑定时即使定义 blocked 也不显示未绑定", async () => {
    sdk.runtimeReadiness.mockResolvedValue({
      tenant,
      catalog: { tenant, items: [], stats: { definitionCount: 6, installedCount: 6, runnableCount: 6, skillDefinitionCount: 37, capabilityDefinitionCount: 10 } },
      capabilityBindings: [{
        bindingId: "b1", status: "active", version: 1,
        capability: { assetId: "copy.generate", revision: 1 },
        dependencies: { providerRef: null, modelRouteRef: null, evalGateRef: null, licenseEvidenceRefs: [], dataDependencyRefs: [], toolDependencyRefs: [], budgetPolicyRef: null },
        readinessReasons: ["MODEL_ROUTE_BLOCKED"],
        dependencySnapshotHash: "h".repeat(64),
        readinessExpiresAt: "2099-01-01T00:00:00Z",
      }],
      skillBindings: [],
      bindingStats: { capabilityBindingCount: 1, skillBindingCount: 0, activeCapabilityBindingCount: 1, activeSkillBindingCount: 0 },
      evaluatedAt: "2026-08-19T06:00:00Z",
    });
    const root = createRoot(host); await act(async () => root.render(<MemoryRouter><CanonicalCapabilityPage /></MemoryRouter>)); await act(async () => undefined);
    expect(host.textContent).toMatch(/组织绑定：已激活|组织绑定：已启用/);
    expect(host.textContent).toContain("定义就绪");
    expect(host.textContent).not.toMatch(/组织绑定：未绑定/);
    expect(host.textContent).toContain("组织绑定侧");
    expect(host.textContent).toContain("定义层");
    expect(host.textContent).not.toContain("去目录绑定");
    await act(async () => root.unmount());
  });
});
