import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationsPage } from "./OperationsPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const ids = ["orders", "orderLines", "inventory", "shipments", "payments", "aftersaleEvents", "operationCases"] as const;
const response = { schemaVersion: "aos.ecommerce-workshop.operations-view/v1" as const, tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-24T08:00:00Z", dataCutoff: "2026-08-24T08:00:00Z", readiness: "degraded" as const, slices: ids.map((sliceId, index) => ({ sliceId, status: (index === 5 ? "blocked" : "ready") as "ready" | "blocked", dataCutoff: "2026-08-24T08:00:00Z", authorityRefs: index === 5 ? [] : [{ resourceType: "ReadAuthority", resourceId: sliceId, revision: 1, contentHash: `sha256:${"a".repeat(64)}`, receiptId: "receipt-1" }], blockers: index === 5 ? [{ code: "AFTERSALE_EVENTS_READ_FAILED_CLOSED", dependency: "data.aftersale", requiredAction: "检查 canonical reader" }] : [], countLedger: { sourceTotal: index === 5 ? 0 : 1, attached: index === 5 ? 0 : 1, unmatched: 0, conflicted: 0 } })), page: { limit: 50, count: 6, hasMore: false, nextCursor: null } };
const commandIds = ["classify", "createCase", "changeMembership", "manageSla", "automationKill", "refund"] as const;
const commands = { schemaVersion: "aos.ecommerce-workshop.operation-command-readiness/v1" as const, tenant: response.tenant, evaluatedAt: "2026-08-24T08:00:00Z", commands: commandIds.map((commandId, index) => ({ commandId, label: ["分类事件", "创建运营工单", "调整工单成员", "管理服务时限", "停止自动化", "退款"][index], status: "blocked" as const, risk: (index > 3 ? "high" : "controlled") as "high" | "controlled", sideEffect: (index === 5 ? "external" : "internalAuthority") as "external" | "internalAuthority", blockers: [{ code: index === 5 ? "EXTERNAL_ACTION_GATE_NOT_BOUND" : "OPERATION_COMMAND_HANDLER_NOT_BOUND", dependency: "W3-12B2", requiredAction: "完成 exact command gate" }] })) };
const observation = { schemaVersion: "aos.ecommerce-workshop.operation-command-observation/v1" as const, tenant: response.tenant, proposalId: "proposal-1", leaseId: "lease-1", commandId: "classify" as const, status: "applied" as const, proposalHash: "a".repeat(64), receiptId: "receipt-1", requestFingerprint: "b".repeat(64), operationReceiptId: "operation-receipt-1", replayAllowed: false as const };
const workspaceRef = { tenant: response.tenant, resourceType: "ProductSku", resourceId: "niushop:1:70", contentHash: "c".repeat(64), sourceUpdatedAt: "2026-08-24T07:00:00Z" };
const workspace = { schemaVersion: "aos.ecommerce-workshop.operation-case-workspace/v1" as const, tenant: response.tenant, status: "ready" as const, evaluatedAt: "2026-08-24T08:00:00Z", dataCutoff: "2026-08-24T08:00:00Z", sources: ["orders", "inventory", "shipments", "aftersaleEvents", "payments", "operationCases"].map((sourceId, index) => ({ sourceId, status: "ready" as const, count: index === 1 ? 1 : 0, blocker: null })), cases: [], candidates: [{ candidateId: "d".repeat(64), kind: "inventory_data_gap" as const, title: "库存资料待核对", summary: "商品库存缺少正式数量。", priority: "high" as const, memberRefs: [workspaceRef], externalEffectAllowed: false as const }], availableRefs: [workspaceRef], ledger: { sourceTotal: 1, assigned: 0, unassigned: 1, candidates: 1, openCases: 0, pausedCases: 0, closedCases: 0 }, externalEffectAllowed: false as const };
const proposalBundle = { proposal: { id: "proposal-r4o04", actionType: { actionTypeId: "ecommerce.operation.create-case", revisionHash: "a".repeat(64), objectType: "OperationCase" }, taskId: null, runId: null, objectRef: { resourceType: "ProductSku", resourceId: "niushop:1:70", revision: "c".repeat(64), authority: "ecommerce-workshop.operation-case-workspace" }, impactPreviewRef: null, purpose: "库存资料待核对", riskLevel: "R1" as const, payload: { priority: "high", summary: "商品库存缺少正式数量。" }, proposalHash: "e".repeat(64), status: "drafted" as const, expiresAt: "2099-01-01T00:00:00Z", version: 1, createdBy: { actorType: "user", actorId: "maker" }, createdAt: "2026-08-24T08:00:00Z", updatedAt: "2026-08-24T08:00:00Z" }, draft: { id: "draft-r4o04", proposalId: "proposal-r4o04", proposalVersion: 1, proposalHash: "e".repeat(64), diff: {}, evidenceRefs: [], status: "awaiting_approval", createdAt: "2026-08-24T08:00:00Z" }, approvals: [] };

describe("OperationsPage", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); });
  it("按视觉稿三栏呈现七切片，并把 blocked 与合格 0 区分", async () => {
    const client = { getOperationsView: vi.fn().mockResolvedValue(response), getOperationCommandReadiness: vi.fn().mockResolvedValue(commands), getOperationCommandObservation: vi.fn().mockResolvedValue(observation) };
    await act(async () => root.render(<OperationsPage client={client} />));
    expect(host.querySelectorAll(".operations-slice-card")).toHaveLength(7);
    expect(host.textContent).toContain("统一待办");
    expect(host.textContent).toContain("部分数据可用");
    expect(host.querySelector(".operations-detail")?.textContent).toContain("订单");
    expect(host.querySelector(".operations-detail")?.textContent).not.toContain("AFTERSALE_EVENTS_READ_FAILED_CLOSED");
    const sliceButtons = host.querySelectorAll<HTMLButtonElement>(".operations-slice-card");
    await act(async () => sliceButtons[5]!.click());
    expect(host.textContent).toContain("AFTERSALE_EVENTS_READ_FAILED_CLOSED");
    expect(host.textContent).toContain("跨域运营分诊");
    expect(host.textContent).not.toContain("0 / 6 可提交");
    expect(host.textContent).not.toContain("王女士");
    expect(host.textContent).not.toContain("一键采纳");
    expect(host.textContent).toContain("请求级命令证据");
    expect(host.querySelector('[aria-label="专业贡献归因路径"]')).not.toBeNull();
    expect(host.textContent).toContain("原子技能");
    expect(host.textContent).toContain("逻辑编排");
    expect(host.textContent).toContain("数字同事");
    expect(host.textContent).toContain("工作台贡献");
    expect(host.textContent).toContain("外部动作需独立审批");
    expect(host.textContent).toContain("以正式售后事件数据支撑售后事件分类");
    const inputs = host.querySelectorAll<HTMLInputElement>(".operations-observation-form input");
    const setInput = (input: HTMLInputElement, value: string) => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value); input.dispatchEvent(new Event("input", { bubbles: true })); };
    await act(async () => { setInput(inputs[0], "proposal-1"); setInput(inputs[1], "lease-1"); });
    await act(async () => host.querySelector<HTMLFormElement>(".operations-observation-form")!.requestSubmit());
    expect(client.getOperationCommandObservation).toHaveBeenCalledWith("proposal-1", "lease-1");
    expect(host.textContent).toContain("applied");
    expect(host.textContent).toContain("禁止自动重放");
    expect(host.textContent).not.toContain("重新执行");
  });
  it("接口乱序时仍默认展示最高优先级的有数据订单，而不是运营工单", async () => {
    const ordered = response.slices.map((slice) => slice.sliceId === "orders"
      ? { ...slice, countLedger: { ...slice.countLedger, sourceTotal: 50, attached: 50 } }
      : slice.sliceId === "operationCases"
        ? { ...slice, countLedger: { ...slice.countLedger, sourceTotal: 7, attached: 7 } }
        : slice);
    const shuffled = { ...response, slices: [ordered[6]!, ordered[4]!, ordered[2]!, ordered[0]!, ordered[1]!, ordered[3]!, ordered[5]!] };
    const client = { getOperationsView: vi.fn().mockResolvedValue(shuffled), getOperationCommandReadiness: vi.fn().mockResolvedValue(commands), getOperationCommandObservation: vi.fn().mockResolvedValue(observation) };
    await act(async () => root.render(<OperationsPage client={client} />));
    expect(host.querySelector(".operations-detail-heading h2")?.textContent).toContain("订单 · 业务处理");
    expect(host.querySelector(".operations-detail")?.textContent).toContain("来源总量50");
    expect(host.querySelector<HTMLButtonElement>('.operations-slice-card[aria-pressed="true"]')?.textContent).toContain("订单");
  });
  it("按蓝图提供可用的待办分类、搜索和处理详情层级", async () => {
    const client = { getOperationsView: vi.fn().mockResolvedValue(response), getOperationCommandReadiness: vi.fn().mockResolvedValue(commands), getOperationCommandObservation: vi.fn().mockResolvedValue(observation) };
    await act(async () => root.render(<OperationsPage client={client} />));
    expect(host.querySelector('[aria-label="统一待办分类"]')).not.toBeNull();
    expect(host.querySelectorAll(".operations-queue-filter")).toHaveLength(4);
    expect(host.textContent).toContain("订单与履约");
    expect(host.textContent).toContain("库存与告警");
    expect(host.textContent).toContain("售后与工单");

    const filters = host.querySelectorAll<HTMLButtonElement>(".operations-queue-filter");
    await act(async () => filters[1]!.click());
    expect(host.querySelectorAll(".operations-slice-card")).toHaveLength(4);
    expect(host.textContent).not.toContain("售后事件数据 · 第");

    const search = host.querySelector<HTMLInputElement>('[aria-label="搜索运营待办"]')!;
    const setInput = (input: HTMLInputElement, value: string) => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value); input.dispatchEvent(new Event("input", { bubbles: true })); };
    await act(async () => setInput(search, "payments"));
    expect(host.querySelectorAll(".operations-slice-card")).toHaveLength(1);
    expect(host.textContent).toContain("支付");
    await act(async () => setInput(search, "不存在的业务对象"));
    expect(host.textContent).toContain("当前筛选下没有匹配的正式业务视图");

    await act(async () => { setInput(search, ""); filters[0]!.click(); });
    expect(host.querySelector('[aria-label="业务处理流程"]')).not.toBeNull();
    expect(host.textContent).toContain("读取正式业务数据");
    expect(host.textContent).toContain("数量守恒核对");
    expect(host.textContent).toContain("运营处理关联");
    expect(host.textContent).toContain("人工业务处置");
    expect(host.textContent).toContain("业务证据");
    expect(host.textContent).toContain("处理建议");
    expect(host.textContent).toContain("处理 SOP");
    expect(host.textContent).toContain("相似经验");
  });
  it("原始数据、处理日志、建议依据和 SOP 按钮都产生可观察的页内结果", async () => {
    const client = { getOperationsView: vi.fn().mockResolvedValue(response), getOperationCommandReadiness: vi.fn().mockResolvedValue(commands), getOperationCommandObservation: vi.fn().mockResolvedValue(observation) };
    await act(async () => root.render(<OperationsPage client={client} />));
    const clickByText = async (label: string) => {
      const button = [...host.querySelectorAll<HTMLButtonElement>("button")].find((item) => item.textContent?.includes(label));
      expect(button).toBeDefined();
      await act(async () => button!.click());
    };
    await clickByText("查看原订单");
    expect(host.querySelector('[role="dialog"]')?.textContent).toContain("ReadAuthority");
    await clickByText("处理日志");
    expect(host.querySelector('[role="dialog"]')?.textContent).toContain("同一数据截止");
    await clickByText("查看建议依据");
    expect(host.textContent).toContain("建议仅根据当前数量守恒和正式来源生成");
    await clickByText("查看完整 SOP");
    expect(host.textContent).toContain("核对订单、支付、履约和售后的同一截止面");
    expect(host.textContent).not.toContain("王女士");
    expect(host.textContent).not.toContain("¥199");
  });
  it("unknown 与 observation 读取错误均失败关闭且不生成重放入口", async () => {
    const unknown = { ...observation, status: "unknown" as const, receiptId: "receipt-unknown", operationReceiptId: null };
    const client = { getOperationsView: vi.fn().mockResolvedValue(response), getOperationCommandReadiness: vi.fn().mockResolvedValue(commands), getOperationCommandObservation: vi.fn().mockResolvedValueOnce(unknown).mockRejectedValueOnce(new Error("offline")) };
    await act(async () => root.render(<OperationsPage client={client} />));
    const inputs = host.querySelectorAll<HTMLInputElement>(".operations-observation-form input");
    const setInput = (input: HTMLInputElement, value: string) => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value); input.dispatchEvent(new Event("input", { bubbles: true })); };
    await act(async () => { setInput(inputs[0], "proposal-1"); setInput(inputs[1], "lease-1"); });
    await act(async () => host.querySelector<HTMLFormElement>(".operations-observation-form")!.requestSubmit());
    expect(host.textContent).toContain("结果待核对，必须另行对账");
    expect(host.textContent).toContain("禁止自动重放");
    await act(async () => host.querySelector<HTMLFormElement>(".operations-observation-form")!.requestSubmit());
    expect(host.textContent).toContain("OBSERVATION_FAILED_CLOSED");
    expect(host.textContent).toContain("未执行重放或补偿");
    expect(host.textContent).not.toContain("重新执行");
  });
  it("以真实候选完成新建、建议采纳、修改、日志、审批预览和撤回内部处理", async () => {
    const client = { getOperationsView: vi.fn().mockResolvedValue(response), getOperationCommandReadiness: vi.fn().mockResolvedValue(commands), getOperationCaseWorkspace: vi.fn().mockResolvedValue(workspace), getOperationCommandObservation: vi.fn().mockResolvedValue(observation) };
    const revised = { ...proposalBundle, proposal: { ...proposalBundle.proposal, id: "proposal-r4o04-v2", proposalHash: "f".repeat(64) } };
    const withdrawn = { ...revised, proposal: { ...revised.proposal, status: "withdrawn" as const } };
    const actions = { createProposal: vi.fn().mockResolvedValue(proposalBundle), createReplacementProposal: vi.fn().mockResolvedValue(revised), timeline: vi.fn().mockResolvedValue({ bundle: proposalBundle, events: [{ id: "event-1", type: "submitted", actorId: "maker", proposalVersion: 1, proposalHash: "e".repeat(64), payload: {}, createdAt: "2026-08-24T08:00:00Z" }] }), withdraw: vi.fn().mockResolvedValue(withdrawn) };
    await act(async () => root.render(<OperationsPage client={client} actions={actions} />));
    expect(host.textContent).toContain("库存资料待核对");
    const click = async (label: string) => { const button = [...host.querySelectorAll<HTMLButtonElement>(".operations-internal-workflow button")].find((item) => item.textContent === label); expect(button).toBeDefined(); await act(async () => button!.click()); };
    await click("新建处理");
    await click("采纳建议");
    expect(host.textContent).toContain("已采纳建议并回填处置说明");
    await act(async () => host.querySelector<HTMLFormElement>('.operations-internal-workflow form')!.requestSubmit());
    expect(actions.createProposal).toHaveBeenCalledWith(expect.objectContaining({ actionTypeId: "ecommerce.operation.create-case", riskHint: "R2", objectRef: expect.objectContaining({ resourceId: "niushop:1:70" }), payload: expect.objectContaining({ externalEffectAllowed: false }) }));
    expect(host.textContent).toContain("内部提案凭证");
    await click("批准预览");
    expect(host.textContent).toContain("需由独立审批人批准后取得执行租约");
    await click("处理日志");
    expect(actions.timeline).toHaveBeenCalledWith("proposal-r4o04");
    expect(host.textContent).toContain("submitted");
    await click("修改");
    await act(async () => host.querySelector<HTMLFormElement>('.operations-internal-workflow form')!.requestSubmit());
    expect(actions.createReplacementProposal).toHaveBeenCalled();
    await click("驳回/撤回");
    expect(actions.withdraw).toHaveBeenCalled();
    expect(host.textContent).toContain("未触发业务执行");
  });
  it("收到主视觉刷新动作后重新读取三个正式只读依赖", async () => {
    const client = { getOperationsView: vi.fn().mockResolvedValue(response), getOperationCommandReadiness: vi.fn().mockResolvedValue(commands), getOperationCaseWorkspace: vi.fn().mockResolvedValue(workspace), getOperationCommandObservation: vi.fn().mockResolvedValue(observation) };
    await act(async () => root.render(<OperationsPage client={client} />));
    expect(client.getOperationsView).toHaveBeenCalledTimes(1);
    expect(client.getOperationCommandReadiness).toHaveBeenCalledTimes(1);
    expect(client.getOperationCaseWorkspace).toHaveBeenCalledTimes(1);
    await act(async () => window.dispatchEvent(new CustomEvent("aos-workshop-operation-refresh")));
    expect(client.getOperationsView).toHaveBeenCalledTimes(2);
    expect(client.getOperationCommandReadiness).toHaveBeenCalledTimes(2);
    expect(client.getOperationCaseWorkspace).toHaveBeenCalledTimes(2);
  });
});
