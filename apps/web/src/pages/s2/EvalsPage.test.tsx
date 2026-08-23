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

const evidenceMocks = vi.hoisted(() => ({ evalRun: vi.fn() }));

vi.mock("../../api/client", () => apiMocks);
vi.mock("../../api/aipEvidence", () => ({
  aipEvidenceSdk: evidenceMocks,
  LINEAGE_ROOT_TYPES: ["task_run", "action", "eval_run", "publication", "research_job", "legacy_decision_lineage"],
}));
vi.mock("../../components/aip/AipOperationalProjectionStrip", () => ({
  AipOperationalProjectionStrip: () => createElement("div", { "data-testid": "aip-operational-projection-test-double" }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("EvalsPage · 真实运行与门控", () => {
  let host: HTMLDivElement;
  let root: Root;

  const graph = {
    id: "logic-1",
    name: "真实 Logic",
    revision: 3,
    graph_hash: "a".repeat(64),
    persisted: true,
  };
  const graphList = { items: [graph], count: 1 };

  const report = {
    report_id: "eval-report-1",
    suite_id: "suite-1",
    target_type: "logic_graph" as const,
    target_id: graph.id,
    target_revision: graph.revision,
    target_hash: graph.graph_hash,
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
    evidenceMocks.evalRun.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("严格拒绝 run/report 不同次或计数不一致", () => {
    const gate = {
      report_id: report.report_id,
      suite_id: "suite-1",
      target_type: report.target_type,
      target_id: report.target_id,
      target_revision: report.target_revision,
      target_hash: report.target_hash,
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
      .mockResolvedValueOnce(graphList)
      .mockResolvedValueOnce({ items: [created] });
    apiMocks.apiPost.mockResolvedValueOnce(created);

    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(EvalsPage)));
    });
    await flush();
    expect(host.textContent).toContain("输入 x=1，期望 2（精确匹配）");
    expect(host.textContent).toContain("门控阈值 100%");

    const createButton = Array.from(host.querySelectorAll("button"))
      .find((node) => node.textContent?.includes("创建基础评测套件"));
    if (!createButton) throw new Error("create suite button not found");
    await act(async () => createButton.click());
    await flush();

    expect(apiMocks.apiPost).toHaveBeenCalledWith("/v1/evals/suites", QUICK_START_EVAL_SUITE);
    expect(apiMocks.apiGet).toHaveBeenNthCalledWith(3, "/v1/evals/suites");
    expect((host.querySelector('select[aria-label="评测套件"]') as HTMLSelectElement).value)
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
      .mockResolvedValueOnce(graphList)
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
    expect((host.querySelector('select[aria-label="评测套件"]') as HTMLSelectElement).value).toBe("");
    expect(host.textContent).toContain("尚未运行真实评测");
    expect(host.textContent).not.toContain("已创建并选中真实套件");
  });

  it("手工读取报告 suite_id 错配时 fail-closed", async () => {
    apiMocks.apiGet
      .mockResolvedValueOnce({
        items: [{ id: "suite-1", name: "真实回归", gate_threshold: 0.8, cases: [{}] }],
      })
      .mockResolvedValueOnce(graphList)
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
      .mockResolvedValueOnce(graphList)
      .mockResolvedValueOnce(report);
    apiMocks.apiPost
      .mockResolvedValueOnce(report)
      .mockResolvedValueOnce({
        report_id: report.report_id,
        suite_id: "suite-1",
        target_type: report.target_type,
        target_id: report.target_id,
        target_revision: report.target_revision,
        target_hash: report.target_hash,
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
    await act(async () => runButton().click());
    await flush();

    expect(apiMocks.apiPost).toHaveBeenNthCalledWith(1, "/v1/evals/run", {
      suite_id: "suite-1",
      target_type: "logic_graph",
      target_id: graph.id,
      target_revision: graph.revision,
      target_hash: graph.graph_hash,
    });
    expect(apiMocks.apiGet).toHaveBeenNthCalledWith(3, "/v1/evals/suite-1/report");
    expect(apiMocks.apiPost).toHaveBeenNthCalledWith(2, "/v1/evals/gate-check", {
      suite_id: "suite-1",
      target_type: "logic_graph",
      target_id: graph.id,
      target_revision: graph.revision,
      target_hash: graph.graph_hash,
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
    apiMocks.apiGet.mockImplementation((path: string) => Promise.resolve(
      path === "/v1/aip/logic/graphs"
        ? graphList
        : { items: [{ id: "suite-1", name: "真实回归", gate_threshold: 0.8, cases: [{}] }] },
    ));
    apiMocks.apiPost.mockRejectedValueOnce(new Error("executor unavailable"));

    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(EvalsPage)));
    });
    await flush();
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
      .mockResolvedValueOnce(graphList)
      .mockResolvedValueOnce(report);
    apiMocks.apiPost
      .mockResolvedValueOnce(report)
      .mockResolvedValueOnce({
        report_id: report.report_id,
        suite_id: "suite-1",
        target_type: report.target_type,
        target_id: report.target_id,
        target_revision: report.target_revision,
        target_hash: report.target_hash,
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
    await act(async () => runButton().click());
    await flush();

    expect(host.textContent).toContain("报告与门控字段不一致");
    expect(host.textContent).not.toContain("门控通过（");
  });

  it("按真实 Run ID 读取 AIP-4 权威引用且不产生写操作", async () => {
    apiMocks.apiGet.mockImplementation((path: string) => Promise.resolve(
      path === "/v1/aip/logic/graphs" ? graphList : { items: [] },
    ));
    evidenceMocks.evalRun.mockResolvedValue({
      runId: "eval-run-1",
      suiteRef: { assetType: "eval_suite", assetId: "suite-1", revision: "2", contentHash: "1".repeat(64) },
      target: { assetType: "logic_graph", assetId: "logic-1", revision: "3", contentHash: "2".repeat(64) },
      dataset: { datasetId: "dataset-1", revision: 4, contentHash: "3".repeat(64), sourceHash: "4".repeat(64), redactionPolicy: { assetType: "policy", assetId: "p1", revision: "1", contentHash: "5".repeat(64) } },
      judge: { judgeId: "judge-1", revision: 2, contentHash: "6".repeat(64), modelRoute: null },
      status: "succeeded", idempotencyKey: "key", createdBy: "user", createdAt: "2026-08-12T01:00:00Z", startedAt: "2026-08-12T01:00:01Z", finishedAt: "2026-08-12T01:00:02Z", version: 3,
    });

    await act(async () => root.render(createElement(MemoryRouter, null, createElement(EvalsPage))));
    await flush();
    const input = host.querySelector<HTMLInputElement>("[aria-label='eval-authority-run-id']")!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, "eval-run-1");
    await act(async () => input.dispatchEvent(new Event("input", { bubbles: true })));
    const read = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "读取权威评测运行")!;
    await act(async () => read.click());
    await flush();

    expect(evidenceMocks.evalRun).toHaveBeenCalledWith("eval-run-1");
    expect(host.textContent).toContain("logic-1@3");
    expect(host.textContent).toContain("succeeded");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
  });
});
