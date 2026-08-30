import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { aipMarketplaceImport } from "../../api/aipMarketplaceImport";
import { AgentMarketplacePage } from "./AgentMarketplacePage";

vi.mock("../../api/aipMarketplaceImport", async (loadOriginal) => {
  const original = await loadOriginal<typeof import("../../api/aipMarketplaceImport")>();
  return {
    ...original,
    aipMarketplaceImport: {
      ...original.aipMarketplaceImport,
      listMarketplace: vi.fn(),
    },
  };
});

describe("AgentMarketplacePage", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    vi.clearAllMocks();
  });

  it("接口缺失时诚实失败关闭且不保留无限加载文案", async () => {
    vi.mocked(aipMarketplaceImport.listMarketplace).mockRejectedValue(new Error("Not Found"));

    await act(async () => root.render(<MemoryRouter><AgentMarketplacePage /></MemoryRouter>));
    await act(async () => undefined);

    expect(host.querySelector('[role="alert"]')?.textContent).toContain("Not Found");
    expect(host.textContent).toContain("不会用演示资产替代");
    expect(host.textContent).not.toContain("正在读取组织市场目录");
  });

  it("支持搜索、状态筛选、详情审计和受控引入入口", async () => {
    vi.mocked(aipMarketplaceImport.listMarketplace).mockResolvedValue({
      tenant: { orgId: "org-org", projectId: "dev-project" }, count: 1,
      items: [{ packageId: "solution.ecommerce.growth", version: "1.3.0", contentHash: "a".repeat(64), displayName: "电商增长数字同事", publisher: "AOS", license: "internal", sourceRef: { resourceType: "SolutionPack", resourceId: "solution.ecommerce.growth", revision: "1.3.0", authority: "bundle" }, agentCount: 2, skillCount: 10, capabilityCount: 5, installedCount: 1, runnableCount: 1, discoverable: true, installAuthorized: false, agents: [
        { templateId: "ecommerce.content_officer", displayName: "内容官", installed: true, runtimeReadiness: "runnable", blockers: [], repairHref: "/aip/agent-registry", repairLabel: "核验" },
        { templateId: "ecommerce.data_advisor", displayName: "数据参谋", installed: false, runtimeReadiness: "blocked", blockers: ["provider_health_unavailable"], repairHref: "/aip/agent-registry", repairLabel: "核验" },
      ] }],
    });
    await act(async () => root.render(<MemoryRouter><AgentMarketplacePage /></MemoryRouter>));
    await act(async () => undefined);
    expect(host.textContent).toContain("内容官");
    const search = host.querySelector<HTMLInputElement>('input[aria-label="搜索数字同事"]')!;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(search, "数据");
      search.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(host.textContent).toContain("数据参谋");
    expect(host.textContent).not.toContain("内容官");
    const details = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "查看详情")!;
    await act(async () => details.click());
    expect(host.textContent).toContain("当前权威方案包未提供公开评价");
    const entry = Array.from(host.querySelectorAll("a")).find((link) => link.textContent === "提交引入预检");
    expect(entry?.getAttribute("href")).toContain("/aip/agent-import?templateId=ecommerce.data_advisor");
    expect(entry?.getAttribute("href")).toContain("sourceId=solution.ecommerce.growth");
    expect(entry?.getAttribute("href")).toContain("displayName=%E6%95%B0%E6%8D%AE%E5%8F%82%E8%B0%8B");
  });
});
