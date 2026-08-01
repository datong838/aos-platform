import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { assertEvalResultConsistency, EvalsPage, QUICK_START_EVAL_SUITE } from "./aip";

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));

vi.mock("../../api/client", () => apiMocks);

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("EvalsPage · 真实运行与门控", () => {
  let host: HTMLDivElement;
  let root: Root;

  const report = {
    suite_id: "suite-1",
    results: [{
      case_id: "case-1",
      passed: false,
      actual: 2,
      expected: 3,
      judge: "exact",
      detail: "期望 3 实际 2",
    }],
    pass_rate: 0,
    passed: 0,
    failed: 1,
    total: 1,
    gate_passed: false,
    run_at: "2026-08-01T00:00:00Z",
  };

  async function flush() {
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
  }

  function setInputValue(element: HTMLInputElement, value: string) {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function runButton(): HTMLButtonElement {
    const found = Array.from(host.querySelectorAll("button")).find((node) => node.textContent?.includes("运行套件并检查门控"));
    if (!found) throw new Error("run button not found");
    return found;
  }

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    apiMocks.apiGet.mockReset();
    apiMocks.apiPost.mockReset();
    apiMocks.apiPut.mockReset();
    apiMocks.apiDelete.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("严格拒绝 run/report 不同次或计数不一致", () => {
    const gate = {
      suite_id: "suite-1",
      gate_passed: false,
      pass_rate: 0,
      threshold: 0.8,
      passed: 0,
      failed: 1,
      total: 1,
      run_at: report.run_at,
    };
    expect(() => assertEvalResultConsistency(
      "suite-1",
      { ...report, total: 2 },
      report,
      gate,
    )).toThrow("运行与报告字段不一致：total");
    expect(() => assertEvalResultConsistency(
      "suite-1",
      { ...report, run_at: "another-run" },
      report,
      gate,
    )).toThrow("最新报告不是本次运行生成的报告");
  });

  it("无套件时通过真实 POST 创建基础套件，重读后自动选中且不伪造报告", async () => {
    const created = {
      id: "suite-quick-start",
      ...QUICK_START_EVAL_SUITE,
    };
    apiMocks.apiGet
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({ items: [created] });
    apiMocks.apiPost.mockResolvedValueOnce(created);

    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(EvalsPage)));
    });
    await flush();
    expect(host.textContent).toContain("输入 x=1，期望 2（exact）");
    expect(host.textContent).toContain("门控阈值 100%");

    const createButton = Array.from(host.querySelectorAll("button"))
      .find((node) => node.textContent?.includes("创建基础评测套件"));
    if (!createButton) throw new Error("create suite button not found");
    await act(async () => createButton.click());
    await flush();

    expect(apiMocks.apiPost).toHaveBeenCalledWith("/v1/evals/suites", QUICK_START_EVAL_SUITE);
    expect(apiMocks.apiGet).toHaveBeenNthCalledWith(2, "/v1/evals/suites");
    expect((host.querySelector('select[aria-label="Eval 套件"]') as HTMLSelectElement).value)
      .toBe("suite-quick-start");
    expect(host.textContent).toContain("已创建并选中真实套件");
    expect(host.textContent).toContain("尚未运行真实评测");
    expect(apiMocks.apiPost).toHaveBeenCalledTimes(1);
  });

  it("基础套件重读内容错配时 fail-closed，不选中也不生成报告", async () => {
    const created = {
      id: "suite-quick-start",
      ...QUICK_START_EVAL_SUITE,
    };
    apiMocks.apiGet
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({
        items: [{ ...created, gate_threshold: 0.5 }],
      });
    apiMocks.apiPost.mockResolvedValueOnce(created);

    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(EvalsPage)));
    });
    await flush();
    const createButton = Array.from(host.querySelectorAll("button"))
      .find((node) => node.textContent?.includes("创建基础评测套件"));
    if (!createButton) throw new Error("create suite button not found");
    await act(async () => createButton.click());
    await flush();

    expect(host.textContent).toContain("基础套件回包核验失败");
    expect((host.querySelector('select[aria-label="Eval 套件"]') as HTMLSelectElement).value).toBe("");
    expect(host.textContent).toContain("尚未运行真实评测");
    expect(host.textContent).not.toContain("已创建并选中真实套件");
  });

  it("手工读取报告 suite_id 错配时 fail-closed", async () => {
    apiMocks.apiGet
      .mockResolvedValueOnce({
        items: [{ id: "suite-1", name: "真实回归", gate_threshold: 0.8, cases: [{}] }],
      })
      .mockResolvedValueOnce({ ...report, suite_id: "suite-other" });

    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(EvalsPage)));
    });
    await flush();
    const refreshButton = Array.from(host.querySelectorAll("button"))
      .find((node) => node.textContent?.includes("读取最新报告"));
    if (!refreshButton) throw new Error("refresh report button not found");
    await act(async () => refreshButton.click());
    await flush();

    expect(host.textContent).toContain("最新报告 suite_id 与当前套件不一致");
    expect(host.textContent).toContain("尚未运行真实评测");
    expect(host.textContent).not.toContain("0.0%");
  });

  it("调用 run、gate-check、report 并展示真实失败报告", async () => {
    apiMocks.apiGet
      .mockResolvedValueOnce({
        items: [{ id: "suite-1", name: "真实回归", gate_threshold: 0.8, cases: [{}] }],
      })
      .mockResolvedValueOnce(report);
    apiMocks.apiPost
      .mockResolvedValueOnce(report)
      .mockResolvedValueOnce({
        suite_id: "suite-1",
        gate_passed: false,
        pass_rate: 0,
        threshold: 0.8,
        passed: 0,
        failed: 1,
        total: 1,
        run_at: report.run_at,
      });

    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(EvalsPage)));
    });
    await flush();
    const target = host.querySelector('input[aria-label="目标表达式"]') as HTMLInputElement;
    await act(async () => setInputValue(target, "x + 1"));
    await act(async () => runButton().click());
    await flush();

    expect(apiMocks.apiPost).toHaveBeenNthCalledWith(1, "/v1/evals/run", {
      suite_id: "suite-1",
      target_type: "function",
      target_expr: "x + 1",
    });
    expect(apiMocks.apiGet).toHaveBeenNthCalledWith(2, "/v1/evals/suite-1/report");
    expect(apiMocks.apiPost).toHaveBeenNthCalledWith(2, "/v1/evals/gate-check", {
      suite_id: "suite-1",
      reuse_latest_report: true,
    });
    expect(apiMocks.apiPost.mock.calls.some(([path]) => path === "/v1/aip/evals")).toBe(false);
    expect(host.textContent).toContain("门控未通过");
    expect(host.textContent).toContain("0.0%");
    expect(host.textContent).toContain("期望 3 实际 2");
    expect(host.textContent).not.toContain("42");
    expect(host.textContent).not.toContain("92%");
  });

  it("真实 API 失败时 fail-closed，不显示门控通过", async () => {
    apiMocks.apiGet.mockResolvedValue({
      items: [{ id: "suite-1", name: "真实回归", gate_threshold: 0.8, cases: [{}] }],
    });
    apiMocks.apiPost.mockRejectedValueOnce(new Error("executor unavailable"));

    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(EvalsPage)));
    });
    await flush();
    const target = host.querySelector('input[aria-label="目标表达式"]') as HTMLInputElement;
    await act(async () => setInputValue(target, "x + 1"));
    await act(async () => runButton().click());
    await flush();

    expect(host.textContent).toContain("评测运行失败：executor unavailable");
    expect(host.textContent).not.toContain("门控通过（");
    expect(apiMocks.apiPost).toHaveBeenCalledTimes(1);
  });

  it("报告与 gate-check 不一致时拒绝显示通过", async () => {
    apiMocks.apiGet
      .mockResolvedValueOnce({
        items: [{ id: "suite-1", name: "真实回归", gate_threshold: 0.8, cases: [{}] }],
      })
      .mockResolvedValueOnce(report);
    apiMocks.apiPost
      .mockResolvedValueOnce(report)
      .mockResolvedValueOnce({
        suite_id: "suite-1",
        gate_passed: true,
        pass_rate: 1,
        threshold: 0.8,
        passed: 1,
        failed: 0,
        total: 1,
        run_at: report.run_at,
      });

    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(EvalsPage)));
    });
    await flush();
    const target = host.querySelector('input[aria-label="目标表达式"]') as HTMLInputElement;
    await act(async () => setInputValue(target, "x + 1"));
    await act(async () => runButton().click());
    await flush();

    expect(host.textContent).toContain("报告与门控字段不一致");
    expect(host.textContent).not.toContain("门控通过（");
  });
});
