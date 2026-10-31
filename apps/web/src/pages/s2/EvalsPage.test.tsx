import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildModelRuntimeEvalHandoffHref } from "../../api/aipModelRuntime/evalHandoff";
import { QYH_RUNTIME_SUCCESSOR } from "../../api/aipModelRuntime/qyhSuccessorPreflight";
import {
  assertEvalResultConsistency,
  buildEvalTargetInventory,
  EvalsPage,
  exactEvalRegressionHistory,
  QUICK_START_EVAL_SUITE,
} from "./aip";

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPostUnqueued: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));

const evidenceMocks = vi.hoisted(() => ({ evalRun: vi.fn() }));

vi.mock("../../api/client", () => apiMocks);
vi.mock("../../api/aipEvidence", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/aipEvidence")>()),
  aipEvidenceSdk: evidenceMocks,
}));
vi.mock("../../components/aip/AipOperationalProjectionStrip", () => ({
  AipOperationalProjectionStrip: () => createElement("div", { "data-testid": "aip-operational-projection-test-double" }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("EvalsPage · 真实运行与门控", () => {
  let host: HTMLDivElement;
  let root: Root;

  const modelCandidate = {
  sourceRef: { assetType: "RegisteredModelRevision", assetId: "model-1", revision: 1, contentHash: "a".repeat(64) },
  targetRef: { assetType: "RegisteredModelRevision", assetId: "model-1", revision: 2, contentHash: "b".repeat(64) },
  expectedHeadVersion: 1, sourceLifecycle: "validated" as const, executionAllowed: false as const,
};
  const routeCandidate = {
    sourceRef: { assetType: "ModelRouteRevision", assetId: QYH_RUNTIME_SUCCESSOR.routeId, revision: 8, contentHash: "d".repeat(64) },
    targetRef: { assetType: "ModelRouteRevision", assetId: QYH_RUNTIME_SUCCESSOR.routeId, revision: 9, contentHash: "e".repeat(64) },
    expectedHeadVersion: 8, sourceLifecycle: "draft" as const, executionAllowed: false as const,
  };
  const qyhModelCandidate = {
    ...modelCandidate,
    sourceRef: { ...modelCandidate.sourceRef, assetId: QYH_RUNTIME_SUCCESSOR.modelId },
    targetRef: { ...modelCandidate.targetRef, assetId: QYH_RUNTIME_SUCCESSOR.modelId },
    sourceLifecycle: "draft" as const,
  };
  const routeEvalRun = {
    tenant: { orgId: "org-org", projectId: "dev-project" },
    runId: "route-eval-run-1",
    suiteRef: { assetType: "eval_suite", assetId: "route-suite-1", revision: "2", contentHash: "1".repeat(64) },
    target: { assetType: "model_route", assetId: routeCandidate.targetRef.assetId, revision: String(routeCandidate.targetRef.revision), contentHash: routeCandidate.targetRef.contentHash },
    dataset: { datasetId: "route-dataset-1", revision: 3, contentHash: "2".repeat(64), sourceHash: "3".repeat(64), redactionPolicy: { assetType: "redaction_policy", assetId: "redact-1", revision: "1", contentHash: "4".repeat(64) } },
    judge: { judgeId: "route-judge-1", revision: 4, contentHash: "5".repeat(64), modelRoute: { assetType: "registered_model", assetId: "judge-model-1", revision: "1", contentHash: "6".repeat(64) } },
    evalContractRef: { resourceType: "EvalContractRevision", resourceId: "route-contract-1", revision: 5, contentHash: "7".repeat(64) },
    status: "queued" as const, idempotencyKey: "route-once", createdBy: "user", createdAt: "2026-10-31T08:00:00Z", startedAt: null, finishedAt: null, version: 1,
  };
  const routeEvalContextSnapshot = {
    schemaVersion: "aos.model-route-eval-context/v1",
    subject: { schemaVersion: "aos.model-route-eval-subject-binding/v1", tenant: routeEvalRun.tenant, candidate: routeCandidate, source: {}, models: [], runtimePolicy: {}, executionAllowed: false },
    run: routeEvalRun,
    suite: { suiteId: routeEvalRun.suiteRef.assetId, revision: Number(routeEvalRun.suiteRef.revision), contentHash: routeEvalRun.suiteRef.contentHash, target: routeEvalRun.target, dataset: routeEvalRun.dataset, judge: routeEvalRun.judge },
    dataset: routeEvalRun.dataset,
    contract: { tenant: routeEvalRun.tenant, contractId: routeEvalRun.evalContractRef.resourceId, revision: routeEvalRun.evalContractRef.revision, version: 1, contentHash: routeEvalRun.evalContractRef.contentHash, lifecycle: "frozen", readiness: "ready", blockers: [], suiteRef: { resourceType: "EvalSuiteRevision", resourceId: routeEvalRun.suiteRef.assetId, revision: Number(routeEvalRun.suiteRef.revision), contentHash: routeEvalRun.suiteRef.contentHash } },
    snapshotReadAt: "2026-10-31T08:02:00+00:00",
    executionAllowed: false,
  };

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
    apiMocks.apiPostUnqueued.mockReset();
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

  it("按四类权威资产生成评测执行清单且不把目录登记冒充评测", () => {
    const rows = buildEvalTargetInventory({
      graphs: [graph],
      skills: [{ skillId: "skill-1", revision: 2, contentHash: "b".repeat(64), canonicalLogicId: "内容经营" }],
      agents: [{ template: { templateId: "agent-1", revision: 4, contentHash: "c".repeat(64), displayName: "内容官" } }],
      models: [modelCandidate],
    });
    expect(rows.map((item) => item.targetType)).toEqual(["业务逻辑", "原子技能", "数字同事", "模型"]);
    expect(rows[0].evidenceState).toBe("可直接评测");
    expect(rows[1].evidenceState).toBe("需独立执行");
    expect(rows[2].costEvidence).toContain("尚无");
    expect(rows[3].evidenceState).toBe("需独立执行");
    expect(rows[3].contentHash).toBe(modelCandidate.targetRef.contentHash);
    expect(rows[3].revision).toBe("2");
    expect(rows[3].costEvidence).not.toContain("零费用");
  });

  it("从栖月汇深链只读匹配精确模型与路由候选且不自动执行", async () => {
    const href = buildModelRuntimeEvalHandoffHref(qyhModelCandidate.sourceRef, routeCandidate.sourceRef);
    apiMocks.apiGet.mockImplementation((path: string) => {
      if (path === "/v1/evals/suites") return Promise.resolve({ items: [] });
      if (path === "/v1/aip/logic/graphs") return Promise.resolve(graphList);
      if (path === "/v1/aip/model-runtime/eval-candidates") return Promise.resolve([qyhModelCandidate, routeCandidate]);
      return Promise.reject(new Error(`unexpected path ${path}`));
    });

    await act(async () => root.render(createElement(MemoryRouter, { initialEntries: [href] }, createElement(EvalsPage))));
    await flush();

    expect(host.textContent).toContain("栖月汇模型链 Eval 精确交接");
    expect(host.textContent).toContain(`${QYH_RUNTIME_SUCCESSOR.modelId}@2`);
    expect(host.textContent).toContain(`${QYH_RUNTIME_SUCCESSOR.routeId}@9`);
    expect(host.textContent).toContain("待正式执行（不可自动运行）");
    expect(apiMocks.apiGet).toHaveBeenCalledWith("/v1/aip/model-runtime/eval-candidates");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
    expect(apiMocks.apiPostUnqueued).not.toHaveBeenCalled();
  });

  it("明确点击后只做一次模型 Eval 办理条件核对并展示真实阻断", async () => {
    const href = buildModelRuntimeEvalHandoffHref(qyhModelCandidate.sourceRef, routeCandidate.sourceRef);
    apiMocks.apiGet.mockImplementation((path: string) => {
      if (path === "/v1/evals/suites") return Promise.resolve({ items: [] });
      if (path === "/v1/aip/logic/graphs") return Promise.resolve(graphList);
      if (path === "/v1/aip/model-runtime/eval-candidates") return Promise.resolve([qyhModelCandidate, routeCandidate]);
      return Promise.reject(new Error(`unexpected path ${path}`));
    });
    apiMocks.apiPostUnqueued.mockResolvedValue({
      tenant: { orgId: "org-org", projectId: "dev-project" },
      sourceRef: qyhModelCandidate.sourceRef,
      targetRef: qyhModelCandidate.targetRef,
      expectedHeadVersion: qyhModelCandidate.expectedHeadVersion,
      providerRef: { assetType: "ProviderInstanceRevision", assetId: "provider-1", revision: 1, contentHash: "1".repeat(64) },
      priceRef: { assetType: "ModelPriceSnapshotRevision", assetId: "price-1", revision: 1, contentHash: "2".repeat(64) },
      quotaPolicyRef: { assetType: "QuotaPolicyRevision", assetId: "quota-1", revision: 1, contentHash: "3".repeat(64) },
      budgetPolicyRef: { assetType: "BudgetPolicyRevision", assetId: "budget-1", revision: 1, contentHash: "4".repeat(64) },
      checkedAt: "2026-10-31T13:05:00Z",
      blockerCodes: ["eval_approval_missing", "budget_capacity_unverified", "provider_transport_unverified"],
      purpose: "quality-eval",
      executionAllowed: false,
    });

    await act(async () => root.render(createElement(MemoryRouter, { initialEntries: [href] }, createElement(EvalsPage))));
    await flush();
    const button = Array.from(host.querySelectorAll("button")).find((node) => node.textContent?.includes("只读核对模型 Eval 办理条件"));
    expect(button).toBeDefined();
    expect(apiMocks.apiPostUnqueued).not.toHaveBeenCalled();
    await act(async () => button!.click());
    await flush();

    expect(apiMocks.apiPostUnqueued).toHaveBeenCalledTimes(1);
    expect(apiMocks.apiPostUnqueued).toHaveBeenCalledWith(
      "/v1/aip/model-runtime/model-eval-preflight",
      qyhModelCandidate,
      {},
    );
    expect(host.textContent).toContain("eval_approval_missing");
    expect(host.textContent).toContain("budget_capacity_unverified");
    expect(host.textContent).toContain("仍不可执行");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
  });

  it("手工读取后把当前路由候选精确绑定到栖月汇权威 EvalRun，且仍不可执行", async () => {
    const href = buildModelRuntimeEvalHandoffHref(qyhModelCandidate.sourceRef, routeCandidate.sourceRef);
    apiMocks.apiGet.mockImplementation((path: string) => {
      if (path === "/v1/evals/suites") return Promise.resolve({ items: [] });
      if (path === "/v1/aip/logic/graphs") return Promise.resolve(graphList);
      if (path === "/v1/aip/model-runtime/eval-candidates") return Promise.resolve([qyhModelCandidate, routeCandidate]);
      return Promise.reject(new Error(`unexpected path ${path}`));
    });
    evidenceMocks.evalRun.mockResolvedValue(routeEvalRun);
    await act(async () => root.render(createElement(MemoryRouter, { initialEntries: [href] }, createElement(EvalsPage))));
    await flush();

    const input = host.querySelector<HTMLInputElement>("[aria-label='eval-authority-run-id']")!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, routeEvalRun.runId);
    await act(async () => input.dispatchEvent(new Event("input", { bubbles: true })));
    const read = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "读取权威评测运行")!;
    await act(async () => read.click());
    await flush();

    expect(host.textContent).toContain("当前路由候选已与权威 EvalRun 精确绑定");
    expect(host.textContent).toContain("route-contract-1@5");
    expect(host.textContent).toContain("不可执行");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
    expect(apiMocks.apiPostUnqueued).not.toHaveBeenCalled();
  });

  it("只有本人点击后才读取一次路由 Eval 上下文快照，且不授予执行权", async () => {
    const href = buildModelRuntimeEvalHandoffHref(qyhModelCandidate.sourceRef, routeCandidate.sourceRef);
    apiMocks.apiGet.mockImplementation((path: string) => {
      if (path === "/v1/evals/suites") return Promise.resolve({ items: [] });
      if (path === "/v1/aip/logic/graphs") return Promise.resolve(graphList);
      if (path === "/v1/aip/model-runtime/eval-candidates") return Promise.resolve([qyhModelCandidate, routeCandidate]);
      return Promise.reject(new Error(`unexpected path ${path}`));
    });
    evidenceMocks.evalRun.mockResolvedValue(routeEvalRun);
    apiMocks.apiPostUnqueued.mockResolvedValue(routeEvalContextSnapshot);
    await act(async () => root.render(createElement(MemoryRouter, { initialEntries: [href] }, createElement(EvalsPage))));
    await flush();
    expect(apiMocks.apiPostUnqueued).not.toHaveBeenCalled();

    const input = host.querySelector<HTMLInputElement>("[aria-label='eval-authority-run-id']")!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, routeEvalRun.runId);
    await act(async () => input.dispatchEvent(new Event("input", { bubbles: true })));
    const readRun = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "读取权威评测运行")!;
    await act(async () => readRun.click());
    await flush();
    expect(apiMocks.apiPostUnqueued).not.toHaveBeenCalled();

    const readContext = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "只读读取路由 Eval 上下文")!;
    await act(async () => readContext.click());
    await flush();
    expect(apiMocks.apiPostUnqueued).toHaveBeenCalledTimes(1);
    expect(apiMocks.apiPostUnqueued).toHaveBeenCalledWith(
      "/v1/aip/model-runtime/route-eval-context-snapshot",
      {
        candidate: routeCandidate,
        runId: routeEvalRun.runId,
        expectedRunVersion: routeEvalRun.version,
        expectedRunStatus: routeEvalRun.status,
      },
      {},
    );
    expect(host.textContent).toContain("路由 Eval 上下文只读快照已精确对齐");
    expect(host.textContent).toContain("route-contract-1@5");
    expect(host.textContent).toContain("不可执行");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
  });

  it("EvalRun 目标漂移时只阻断路由绑定，仍保留通用权威运行查看", async () => {
    const href = buildModelRuntimeEvalHandoffHref(qyhModelCandidate.sourceRef, routeCandidate.sourceRef);
    apiMocks.apiGet.mockImplementation((path: string) => {
      if (path === "/v1/evals/suites") return Promise.resolve({ items: [] });
      if (path === "/v1/aip/logic/graphs") return Promise.resolve(graphList);
      if (path === "/v1/aip/model-runtime/eval-candidates") return Promise.resolve([qyhModelCandidate, routeCandidate]);
      return Promise.reject(new Error(`unexpected path ${path}`));
    });
    evidenceMocks.evalRun.mockResolvedValue({ ...routeEvalRun, target: { ...routeEvalRun.target, contentHash: "9".repeat(64) } });
    await act(async () => root.render(createElement(MemoryRouter, { initialEntries: [href] }, createElement(EvalsPage))));
    await flush();
    const input = host.querySelector<HTMLInputElement>("[aria-label='eval-authority-run-id']")!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, routeEvalRun.runId);
    await act(async () => input.dispatchEvent(new Event("input", { bubbles: true })));
    const read = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "读取权威评测运行")!;
    await act(async () => read.click());
    await flush();

    expect(host.textContent).toContain("路由 EvalRun 绑定已阻断");
    expect(host.textContent).toContain("route-eval-run-1");
    expect(host.textContent).not.toContain("route-contract-1@5");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
  });

  it("栖月汇深链任一候选漂移时整体阻断且不回退执行", async () => {
    const href = buildModelRuntimeEvalHandoffHref(qyhModelCandidate.sourceRef, routeCandidate.sourceRef);
    apiMocks.apiGet.mockImplementation((path: string) => {
      if (path === "/v1/evals/suites") return Promise.resolve({ items: [] });
      if (path === "/v1/aip/logic/graphs") return Promise.resolve(graphList);
      if (path === "/v1/aip/model-runtime/eval-candidates") return Promise.resolve([
        qyhModelCandidate,
        {
          ...routeCandidate,
          sourceRef: { ...routeCandidate.sourceRef, revision: 9 },
          targetRef: { ...routeCandidate.targetRef, revision: 10 },
        },
      ]);
      return Promise.reject(new Error(`unexpected path ${path}`));
    });

    await act(async () => root.render(createElement(MemoryRouter, { initialEntries: [href] }, createElement(EvalsPage))));
    await flush();

    expect(host.textContent).toContain("栖月汇模型链 Eval 精确交接");
    expect(host.textContent).toContain("交接已阻断");
    expect(host.textContent).toContain("路由候选未精确匹配");
    expect(host.textContent).not.toContain("待正式执行（不可自动运行）");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
  });

  it("回归历史只接受同一 Logic 精确修订与摘要", () => {
    expect(exactEvalRegressionHistory([
      report,
      { ...report, report_id: "wrong-revision", target_revision: graph.revision + 1 },
      { ...report, report_id: "wrong-hash", target_hash: "f".repeat(64) },
    ], graph).map((item) => item.report_id)).toEqual([report.report_id]);
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
      tenant: { orgId: "org-org", projectId: "dev-project" },
      runId: "eval-run-1",
      suiteRef: { assetType: "eval_suite", assetId: "suite-1", revision: "2", contentHash: "1".repeat(64) },
      target: { assetType: "logic_graph", assetId: "logic-1", revision: "3", contentHash: "2".repeat(64) },
      dataset: { datasetId: "dataset-1", revision: 4, contentHash: "3".repeat(64), sourceHash: "4".repeat(64), redactionPolicy: { assetType: "policy", assetId: "p1", revision: "1", contentHash: "5".repeat(64) } },
      judge: { judgeId: "judge-1", revision: 2, contentHash: "6".repeat(64), modelRoute: null },
      evalContractRef: null,
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

  it("显式读取四类目标和精确版本回归历史", async () => {
    apiMocks.apiGet.mockImplementation((path: string) => {
      if (path === "/v1/evals/suites") return Promise.resolve({ items: [{ id: "suite-1", name: "真实回归", gate_threshold: 0.8, cases: [{}] }] });
      if (path === "/v1/aip/logic/graphs") return Promise.resolve(graphList);
      if (path === "/v1/aip/skills?limit=200") return Promise.resolve({ items: [{ skillId: "skill-1", revision: 2, contentHash: "b".repeat(64), canonicalLogicId: "内容经营" }] });
      if (path === "/v1/aip/agent-registry") return Promise.resolve({ items: [{ template: { templateId: "agent-1", revision: 4, contentHash: "c".repeat(64), displayName: "内容官" } }] });
      if (path === "/v1/aip/model-runtime/eval-candidates") return Promise.resolve([modelCandidate]);
      if (path === "/v1/evals/suite-1/history") return Promise.resolve({ items: [report, { ...report, report_id: "report-2", run_at: "2026-08-02T00:00:00Z", pass_rate: 1, passed: 1, failed: 0, gate_passed: true }] });
      return Promise.reject(new Error(`unexpected path ${path}`));
    });

    await act(async () => root.render(createElement(MemoryRouter, null, createElement(EvalsPage))));
    await flush();
    const inventory = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "读取全部评测目标")!;
    await act(async () => inventory.click());
    await flush();
    expect(host.textContent).toContain("已读取 4 个真实评测目标");
    expect(host.textContent).toContain("model-1");
    expect(host.textContent).toContain("下一生效版本");
    expect(apiMocks.apiGet).not.toHaveBeenCalledWith("/v1/aip/model-admin/models");
    expect(apiMocks.apiGet).not.toHaveBeenCalledWith("/v1/aip/model-catalog");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();

    const history = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "加载回归历史")!;
    await act(async () => history.click());
    await flush();
    expect(host.textContent).toContain("已读取当前 Logic 精确修订的 2 次回归");
    expect(host.textContent).toContain("+100.0 个百分点");
    const previous = apiMocks.apiGet.getMockImplementation()!;
    apiMocks.apiGet.mockImplementation((path: string) => path === "/v1/aip/model-runtime/eval-candidates"
      ? Promise.reject(new Error("candidate authority unavailable")) : previous(path));
    await act(async () => inventory.click());
    await flush();
    expect(host.textContent).toContain("1 类权威目录读取失败");
    expect(apiMocks.apiGet).not.toHaveBeenCalledWith("/v1/aip/model-admin/models");
    expect(apiMocks.apiGet).not.toHaveBeenCalledWith("/v1/aip/model-catalog");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();

  });
});
