// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  apiGet: apiMocks.get,
  apiPost: apiMocks.post,
  apiPut: apiMocks.put,
  apiPatch: apiMocks.patch,
  apiDelete: apiMocks.del,
}));

import { StylesPage } from "./StylesPage";
import { WidgetRegistryPage } from "./WidgetRegistryPage";
import { MaturityPage } from "./extras";

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function byText(container: HTMLElement, text: string): HTMLElement {
  const node = Array.from(container.querySelectorAll<HTMLElement>("button, a, [role='button']"))
    .find((item) => item.textContent?.includes(text));
  if (!node) throw new Error(`找不到交互元素：${text}`);
  return node;
}

describe("Wave3B W4 · DOM 真实性闭环", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    apiMocks.get.mockReset();
    apiMocks.post.mockReset();
    apiMocks.put.mockReset();
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
  });

  it("Styles PUT 后 GET 重读一致才显示保存成功", async () => {
    const base = {
      id: "theme-user",
      name: "用户主题",
      mode: "light",
      description: "自定义",
      tokens: { colorPrimary: "#2563EB" },
    };
    let saved: typeof base | (Omit<typeof base, "tokens"> & { tokens: Record<string, unknown> }) = base;
    apiMocks.get.mockImplementation(async (path: string) => path === "/v1/themes" ? { items: [base] } : saved);
    apiMocks.put.mockImplementation(async (_path: string, body: { tokens: Record<string, unknown> }) => {
      saved = { ...base, tokens: body.tokens };
      return saved;
    });

    await act(async () => root.render(<MemoryRouter><StylesPage /></MemoryRouter>));
    await flush();
    const swatch = host.querySelector<HTMLElement>('[title="#4F46E5"]')!;
    await act(async () => swatch.click());
    await act(async () => byText(host, "保存样式").click());
    await flush();

    expect(apiMocks.put).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("已保存并验证主题 用户主题");
  });

  it("Styles 服务失败时不注入演示主题或虚构业务记录", async () => {
    apiMocks.get.mockRejectedValue(new Error("theme offline"));
    await act(async () => root.render(<MemoryRouter><StylesPage /></MemoryRouter>));
    await flush();

    expect(host.textContent).toContain("主题服务暂不可用");
    expect(host.textContent).not.toContain("AOS 浅色");
    expect(host.textContent).not.toContain("订单管理");
    expect(host.textContent).not.toContain("张三");
    expect(host.textContent).not.toContain("#20250725");
    expect(apiMocks.post).not.toHaveBeenCalled();
  });

  it("Widget 详情只为已安装且声明 canvasKind 的插件给出真实画布链接", async () => {
    apiMocks.get.mockResolvedValue({
      items: [{ id: "metric-card", nameZh: "指标卡", installed: true, canvasKind: "metric", author: "aos" }],
    });
    await act(async () => root.render(<MemoryRouter><WidgetRegistryPage /></MemoryRouter>));
    await flush();
    await act(async () => byText(host, "指标卡").click());
    const link = host.querySelector<HTMLAnchorElement>('a[href*="pluginId=metric-card"]');
    expect(link?.getAttribute("href")).toBe("/workshop/canvas?pluginId=metric-card&canvasKind=metric");
  });

  it("Widget 服务失败时保持可信空态且不注入演示目录", async () => {
    apiMocks.get.mockRejectedValue(new Error("widget offline"));
    await act(async () => root.render(<MemoryRouter><WidgetRegistryPage /></MemoryRouter>));
    await flush();

    expect(host.textContent).toContain("组件目录服务暂不可用");
    expect(host.textContent).toContain("没有匹配的组件");
    expect(host.textContent).not.toContain("甘特图");
    expect(host.textContent).not.toContain("自定义图表");
    expect(apiMocks.post).not.toHaveBeenCalled();
  });

  it("成熟度页以真实 Eval/Draft 数据展示条件，并核验服务端熔断响应", async () => {
    apiMocks.get.mockImplementation(async (path: string) => {
      if (path === "/v1/aip/evals/status") return { green: true, l4Allowed: true };
      if (path === "/v1/aip/drafts") return { count: 2, items: [{}, {}] };
      throw new Error(path);
    });
    apiMocks.post.mockResolvedValue({ open: true, mode: "L3" });
    await act(async () => root.render(<MemoryRouter><MaturityPage /></MemoryRouter>));
    await flush();
    expect(host.textContent).toContain("审批台 2 项");
    expect(host.textContent).toContain("查看自动化申请条件");
    await act(async () => byText(host, "模拟熔断降级").click());
    await flush();
    expect(host.textContent).toContain("服务端已确认熔断");
  });
});
