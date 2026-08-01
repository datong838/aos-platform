import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LogicCanvasPage } from "./LogicCanvasPage";

const apiMocks = vi.hoisted(() => ({
  apiPost: vi.fn(),
}));

vi.mock("../../api/client", () => apiMocks);

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("AIP Logic Stage A1 · P0 交互真实性", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    apiMocks.apiPost.mockReset();
    await act(async () => root.render(<MemoryRouter><LogicCanvasPage /></MemoryRouter>));
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  function button(label: string): HTMLButtonElement {
    const found = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((item) =>
      item.textContent?.includes(label),
    );
    if (!found) throw new Error(`button not found: ${label}`);
    return found;
  }

  function setNativeInput(input: HTMLInputElement, value: string) {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  it("标签编辑修改 Block 顶层 label 并立即反映到画布", async () => {
    await act(async () => button("WorkOrder 输入").click());
    const labelField = Array.from(host.querySelectorAll("label")).find((item) =>
      item.textContent?.includes("标签"),
    );
    const input = labelField?.querySelector("input") as HTMLInputElement | null;
    if (!input) throw new Error("label input not found");

    await act(async () => setNativeInput(input, "工单入口（已编辑）"));

    expect(input.value).toBe("工单入口（已编辑）");
    expect(button("工单入口（已编辑）")).toBeTruthy();
  });

  it("只调用真实安全门卫并固定 dryRun，回包确认后才记录会话历史", async () => {
    apiMocks.apiPost.mockResolvedValue({
      dryRun: true,
      proposedEdits: [{ objectType: "WorkOrder", objectId: "wo-1001", set: { note: "logic" } }],
      productionWritten: false,
    });

    expect(host.textContent).toContain("未保存模板");
    expect(host.textContent).not.toContain("生产执行");
    await act(async () => button("安全 dry-run").click());
    await flush();

    expect(apiMocks.apiPost).toHaveBeenCalledTimes(1);
    expect(apiMocks.apiPost).toHaveBeenCalledWith("/v1/aip/logic/run", { dryRun: true, edits: [] });
    expect(host.textContent).toContain("当前会话");
    expect(host.textContent).toContain("productionWritten");
    expect(host.textContent).not.toContain("Tokens 入");
    expect(host.textContent).not.toContain("生产执行结果");
  });

  it("安全字段缺失或不一致时 fail-closed，不写成功历史", async () => {
    apiMocks.apiPost.mockResolvedValue({
      proposedEdits: [],
      productionWritten: true,
    });

    await act(async () => button("安全 dry-run").click());
    await flush();

    expect(host.textContent).toContain("安全校验失败");
    expect(host.textContent).not.toContain("✓");
    expect(host.textContent).not.toContain("生产执行结果");
  });

  it("自动化没有服务端写契约时全部禁用并说明原因", async () => {
    await act(async () => button("自动化").click());

    expect(host.textContent).toContain("尚无服务端写契约");
    const toggles = Array.from(host.querySelectorAll<HTMLInputElement>('input[type="checkbox"]'));
    expect(toggles.length).toBeGreaterThan(0);
    expect(toggles.every((toggle) => toggle.disabled)).toBe(true);
  });

  it("保留当前会话添加和上下移动能力", async () => {
    await act(async () => button("分支").click());
    expect(host.textContent).toContain("5 blocks");

    const branchCard = button("分支 (Branch)");
    await act(async () => branchCard.click());
    const up = host.querySelector<HTMLButtonElement>('button[aria-label="上移 分支 (Branch)"]');
    if (!up) throw new Error("up button not found");
    expect(up.disabled).toBe(false);
    await act(async () => up.click());

    expect(host.textContent).toContain("编排画布 · 5 个 Block");
    expect(host.textContent!.indexOf("分支 (Branch)")).toBeLessThan(host.textContent!.indexOf("写回 note"));
  });
});
