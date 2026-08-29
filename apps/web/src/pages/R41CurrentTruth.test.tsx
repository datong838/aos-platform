// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const clientMocks = vi.hoisted(() => ({
  post: vi.fn(),
}));

const sharedMocks = vi.hoisted(() => ({
  useJsonGet: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, apiPost: clientMocks.post };
});

vi.mock("./s2/shared", async () => {
  const actual = await vi.importActual<typeof import("./s2/shared")>("./s2/shared");
  return { ...actual, useJsonGet: sharedMocks.useJsonGet };
});

import { BuddyPage } from "./BuddyPage";
import { CopPage } from "./s2/extras";
import { MediaSetsPage } from "./s2/MediaSetsPage";
import { DataConnectionPage } from "./s2/DataConnectionPage";

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("R41 current business truth", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    clientMocks.post.mockReset();
    sharedMocks.useJsonGet.mockReset();
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
  });

  it("态势大屏只展示当前接口对象，不注入静态工厂、风险和事件", async () => {
    sharedMocks.useJsonGet.mockImplementation((path: string) => ({
      data: path === "/v1/ontology/graph-health"
        ? { score: 63, metrics: { instances: 819, orphanInstances: 139, edges: 1156 } }
        : path === "/v1/metrics"
          ? { totals: { count: 10, errors: 1, p95Ms: 151 } }
          : path === "/v1/aip/evals/status"
            ? { green: false }
            : { items: [{ id: "Order", name: "订单" }] },
      err: null,
      reload: vi.fn(),
    }));

    await act(async () => root.render(<MemoryRouter><CopPage /></MemoryRouter>));

    expect(host.textContent).toContain("订单");
    expect(host.textContent).not.toContain("华东 F1");
    expect(host.textContent).not.toContain("华南 F3");
    expect(host.textContent).not.toContain("ORD-8821");
  });

  it("Buddy 无真实工单时不注入固定选择且发送保持禁用", async () => {
    clientMocks.post.mockResolvedValue({ items: [] });
    await act(async () => root.render(<MemoryRouter><BuddyPage initialSelection={[]} /></MemoryRouter>));
    await flush();

    expect(host.textContent).not.toContain("wo-1001");
    expect(host.textContent).toContain("暂无工单");
    expect(host.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(true);
  });

  it("媒体接口为空时保持可信空态，不注入演示文件", async () => {
    sharedMocks.useJsonGet.mockReturnValue({ data: { items: [] }, err: null, reload: vi.fn() });
    await act(async () => root.render(<MemoryRouter><MediaSetsPage /></MemoryRouter>));

    expect(host.textContent).toContain("当前租户尚无媒体");
    expect(host.textContent).not.toContain("工单模板.csv");
    expect(host.textContent).not.toContain("product-photo.jpg");
  });

  it("连接器 Registry 为空时不回退静态演示目录", async () => {
    sharedMocks.useJsonGet.mockReturnValue({ data: { items: [] }, err: null, reload: vi.fn() });
    await act(async () => root.render(<MemoryRouter><DataConnectionPage /></MemoryRouter>));

    expect(host.textContent).toContain("当前没有可用连接器");
    expect(host.textContent).not.toContain("Shopify");
    expect(host.textContent).not.toContain("stub");
  });
});
