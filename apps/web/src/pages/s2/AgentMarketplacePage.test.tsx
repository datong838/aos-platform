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
});
