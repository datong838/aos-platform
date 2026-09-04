import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ContentCampaignInputsResponse, CreatorGrowthViewResponse } from "../../api/ecommerceWorkshop";
import { CreatorGrowthPage } from "./CreatorGrowthPage";

const cutoff = "2026-09-05T00:00:00+08:00";
const stages = ["candidate", "outreach", "contract", "delivery", "relationship"] as const;
const phases = ["discovery", "evidence", "matching", "batch_prepare", "start"] as const;
const emptyView: CreatorGrowthViewResponse = {
  schemaVersion: "aos.ecommerce-workshop.creator-growth-view/v1",
  tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded",
  slices: stages.map((businessStage) => ({ businessStage, workflowPhases: [...phases], status: "blocked", dataCutoff: cutoff, authorityRefs: [], blockers: [{ code: `CANONICAL_CREATOR_${businessStage.toUpperCase()}_AUTHORITY_NOT_AVAILABLE`, dependency: businessStage, requiredAction: "补充正式业务数据" }], countLedger: { input: 0, eligible: 0, excluded: 0, needsReview: 0, unknown: 0, deduplicated: 0 } })),
  page: { limit: 100, count: 0, hasMore: false, nextCursor: null },
};
const contribution = { schemaVersion: "aos.ecommerce-workshop.creator-prepare/v1" as const, tenant: emptyView.tenant, evaluatedAt: cutoff, atomicSkillRefs: [], logicRef: null, primaryColleague: "导购顾问" as const, collaboratorColleagues: ["数据参谋", "内容官", "活动策划师"], latestBatch: null, blockers: ["CREATOR_BATCH_PREPARATION_NOT_AVAILABLE"], allowedCommands: ["PREPARE_CREATOR_BATCH" as const], externalEffectsAllowed: false as const };
const lifecycle = { schemaVersion: "aos.ecommerce-workshop.creator-lifecycle/v1" as const, tenant: emptyView.tenant, evaluatedAt: cutoff, latestStart: null, ledger: { eligibleItems: 0, lanes: 0, prepared: 0, accepted: 0, applied: 0, failed: 0, unknown: 0, disputed: 0, completed: 0 }, contracts: [], deliveries: [], relationships: [], blockers: ["CREATOR_BATCH_START_NOT_AVAILABLE"], allowedCommands: ["START_CREATOR_BATCH_GOVERNANCE" as const], externalEffectsAllowed: false as const };
const draft = { resourceType: "TaskBriefRevision" as const, resourceId: "creator-brief-1", revision: 1, contentHash: "a".repeat(64), version: 1, purpose: "candidate_import" as const, title: "达人候选导入", summary: "品牌合作名单与美妆达人筛选", details: { owner: "经营负责人" }, status: "draft" as const };
const realInputs: ContentCampaignInputsResponse = { schemaVersion: "aos.ecommerce-workshop.content-campaign-inputs/v1", tenant: emptyView.tenant, evaluatedAt: cutoff, dataCutoff: cutoff, status: "ready", products: [{ productRef: { resourceType: "Product", resourceId: "niushop:1:65", revision: null, contentHash: "sha256:" + "b".repeat(64), authority: "ecom_object" }, title: "栖月汇焕亮面膜", price: "99.00", availableStock: 28, businessStatus: "1", sourceUpdatedAt: cutoff }], inventory: [], plans: [], ledger: { products: 1, inventory: 0, plans: 0, unmatchedInventory: 0 }, unavailableGroups: [] };
const clientFor = () => ({ getCreatorGrowthView: vi.fn().mockResolvedValue(emptyView), getCreatorContributionView: vi.fn().mockResolvedValue(contribution), getCreatorLifecycleView: vi.fn().mockResolvedValue(lifecycle), getContentCampaignRealInputs: vi.fn().mockResolvedValue(realInputs), listCreatorInternalWorkflows: vi.fn().mockResolvedValue({ tenant: emptyView.tenant, items: [], count: 0 }), executeCreatorInternalWorkflow: vi.fn().mockResolvedValue({ tenant: emptyView.tenant, command: "create", taskId: "creator-task-1", draft, receipt: { receiptId: "receipt-1", operation: "task_brief.create", idempotencyKey: "creator-key:creator-brief", replay: false }, sideEffects: { providerInvocationCount: 0, externalOutreachCount: 0, contractSignatureCount: 0, businessMutationCount: 0 }, message: "内部业务草稿已创建。" }), getCreatorInternalWorkflowHistory: vi.fn().mockResolvedValue({ tenant: emptyView.tenant, items: [draft], count: 1 }) });

describe("CreatorGrowthPage R5-D01 视觉与交互", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("以真实零数据呈现五标签三栏业务工作区且不注入演示达人", async () => {
    await act(async () => root.render(<CreatorGrowthPage client={clientFor()} />));
    expect([...host.querySelectorAll(".creator-growth-toolbar button")].map((node) => node.textContent)).toEqual(["达人库", "招募漏斗", "商务签约", "履约效果", "长期关系"]);
    expect(host.querySelectorAll(".creator-growth-board > *")).toHaveLength(3);
    expect(host.textContent).toContain("达人与机构"); expect(host.textContent).toContain("候选匹配概览"); expect(host.textContent).toContain("AI 匹配分析 · 导购顾问");
    expect(host.textContent).not.toMatch(/赵小美|王博士|李美妆|8\.6万粉|¥18\.2万/); expect(host.textContent).not.toMatch(/未就绪|待完成|不可派发/);
  });

  it("五个标签分别呈现对应业务结构而不是共用空模板", async () => {
    await act(async () => root.render(<CreatorGrowthPage client={clientFor()} />));
    const clickTab = async (label: string) => act(async () => [...host.querySelectorAll<HTMLButtonElement>(".creator-growth-toolbar button")].find((button) => button.textContent === label)!.click());
    await clickTab("招募漏斗"); expect(host.textContent).toContain("邀约漏斗"); expect(host.textContent).toContain("批次准备");
    await clickTab("商务签约"); expect(host.textContent).toContain("合作条款看板"); expect(host.textContent).toContain("谈判中");
    await clickTab("履约效果"); expect(host.textContent).toContain("履约任务列表"); expect(host.textContent).toContain("效果窗口");
    await clickTab("长期关系"); expect(host.textContent).toContain("复邀计划"); expect(host.textContent).toContain("关系事件流");
  });

  it("页头搜索、导入达人和新建批次均联动到可编辑准备面板", async () => {
    await act(async () => root.render(<CreatorGrowthPage client={clientFor()} />));
    await act(async () => window.dispatchEvent(new CustomEvent("aos-workshop-creator-search", { detail: { value: "美妆" } })));
    expect(host.querySelector<HTMLInputElement>('input[aria-label="检索达人或机构"]')?.value).toBe("美妆");
    await act(async () => window.dispatchEvent(new CustomEvent("aos-workshop-creator-import")));
    expect(host.textContent).toContain("导入达人准备");
    const summary = host.querySelector<HTMLTextAreaElement>('textarea[aria-label="来源与筛选条件"]')!;
    await act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(summary, "品牌合作名单与美妆达人筛选"); summary.dispatchEvent(new Event("input", { bubbles: true })); });
    await act(async () => [...host.querySelectorAll<HTMLButtonElement>(".creator-growth-preparation button")].find((button) => button.textContent === "保存草稿")!.click());
    expect(host.textContent).toContain("内部业务草稿已创建"); expect(host.textContent).toContain("草稿 · 第 1 版"); expect(host.textContent).toContain("回执 receipt-1");
    await act(async () => window.dispatchEvent(new CustomEvent("aos-workshop-creator-new-batch")));
    expect(host.textContent).toContain("新建邀约批次准备"); expect(host.querySelector(".creator-growth-toolbar button.is-active")?.textContent).toBe("招募漏斗");
  });

  it("业务动作落到准备区，技术状态仅进入默认折叠诊断", async () => {
    await act(async () => root.render(<CreatorGrowthPage client={clientFor()} />));
    const action = [...host.querySelectorAll<HTMLButtonElement>(".creator-growth-next-actions button")].find((button) => button.textContent === "准备候选条件")!;
    await act(async () => action.click()); expect(host.textContent).toContain("导入达人准备");
    const audit = host.querySelector<HTMLDetailsElement>(".creator-growth-audit-context")!; expect(audit.open).toBe(false); expect(audit.textContent).toContain("CANONICAL_CREATOR_CANDIDATE_AUTHORITY_NOT_AVAILABLE");
    expect(host.textContent).toContain("数据截止");
  });

  it("贡献接口暂不可读时仍保留完整业务工作区", async () => {
    const client = clientFor(); client.getCreatorContributionView.mockRejectedValueOnce(new Error("404"));
    await act(async () => root.render(<CreatorGrowthPage client={client} />));
    expect(host.querySelectorAll(".creator-growth-board > *")).toHaveLength(3);
    expect(host.textContent).toContain("候选匹配概览");
    expect(host.textContent).not.toContain("读取失败");
  });

  it("页面准备不冒充真实发送签约履约或关系变更", async () => {
    await act(async () => root.render(<CreatorGrowthPage client={clientFor()} />));
    expect([...host.querySelectorAll<HTMLButtonElement>("button")].map((button) => button.textContent).join(" ")).not.toMatch(/发送邀约|签署合同|确认寄样|修改佣金/);
    await act(async () => window.dispatchEvent(new CustomEvent("aos-workshop-creator-new-batch")));
    expect(host.textContent).toContain("不会自动导入、发送邀约、签署合同或产生外部触达");
  });

  it("刷新后从服务端水合最新内部草稿", async () => {
    const client = clientFor(); client.listCreatorInternalWorkflows.mockResolvedValueOnce({ tenant: emptyView.tenant, items: [draft], count: 1 });
    await act(async () => root.render(<CreatorGrowthPage client={client} />));
    await act(async () => window.dispatchEvent(new CustomEvent("aos-workshop-creator-import")));
    expect(host.textContent).toContain("草稿 · 第 1 版"); expect(host.querySelector<HTMLInputElement>('input[aria-label="任务名称"]')?.value).toBe("达人候选导入");
    expect(client.getCreatorInternalWorkflowHistory).toHaveBeenCalledWith("creator-brief-1");
    expect(host.textContent).toContain("查看版本历史（1）");
  });

  it("修订命令只提交精确草稿引用而不夹带展示字段", async () => {
    const client = clientFor(); client.listCreatorInternalWorkflows.mockResolvedValueOnce({ tenant: emptyView.tenant, items: [draft], count: 1 });
    await act(async () => root.render(<CreatorGrowthPage client={client} />));
    await act(async () => window.dispatchEvent(new CustomEvent("aos-workshop-creator-import")));
    await act(async () => [...host.querySelectorAll<HTMLButtonElement>(".creator-growth-preparation button")].find((button) => button.textContent === "保存修改")!.click());
    const input = client.executeCreatorInternalWorkflow.mock.calls[0]![0];
    expect(input.draftRef).toEqual({ resourceType: "TaskBriefRevision", resourceId: "creator-brief-1", revision: 1, contentHash: "a".repeat(64) });
    expect(input.draftRef).not.toHaveProperty("status");
  });

  it("命令成功但历史读取失败时保留草稿和回执", async () => {
    const client = clientFor(); client.getCreatorInternalWorkflowHistory.mockRejectedValueOnce(new Error("history unavailable"));
    await act(async () => root.render(<CreatorGrowthPage client={client} />));
    await act(async () => window.dispatchEvent(new CustomEvent("aos-workshop-creator-import")));
    const summary = host.querySelector<HTMLTextAreaElement>('textarea[aria-label="来源与筛选条件"]')!;
    await act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(summary, "品牌合作名单与美妆达人筛选"); summary.dispatchEvent(new Event("input", { bubbles: true })); });
    await act(async () => [...host.querySelectorAll<HTMLButtonElement>(".creator-growth-preparation button")].find((button) => button.textContent === "保存草稿")!.click());
    expect(host.textContent).toContain("回执 receipt-1"); expect(host.textContent).toContain("操作已保存并取得回执"); expect(host.textContent).not.toContain("操作未保存");
  });

  it("读取栖月汇正式商品并在达人业务区显示名称价格库存和来源时间", async () => {
    await act(async () => root.render(<CreatorGrowthPage client={clientFor()} />));
    expect(host.textContent).toContain("栖月汇商品"); expect(host.textContent).toContain("栖月汇焕亮面膜");
    expect(host.textContent).toContain("¥99.00"); expect(host.textContent).toContain("库存 28"); expect(host.textContent).toContain("正式商品 1");
  });

  it("商品读取失败不影响达人内部工作流并提供重新读取入口", async () => {
    const client = clientFor(); client.getContentCampaignRealInputs.mockRejectedValueOnce(new Error("products unavailable"));
    await act(async () => root.render(<CreatorGrowthPage client={client} />));
    expect(host.textContent).toContain("商品数据暂未读取"); expect(host.textContent).toContain("重新读取业务数据");
    await act(async () => window.dispatchEvent(new CustomEvent("aos-workshop-creator-import")));
    expect(host.textContent).toContain("导入达人准备"); expect(host.querySelector('button')?.disabled).toBe(false);
  });

  it("候选条件按中文业务字段保存并带入正式商品引用", async () => {
    const client = clientFor();
    await act(async () => root.render(<CreatorGrowthPage client={client} />));
    await act(async () => window.dispatchEvent(new CustomEvent("aos-workshop-creator-import")));
    const fill = async (label: string, value: string) => { const input = host.querySelector<HTMLInputElement>(`input[aria-label="${label}"]`)!; await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value); input.dispatchEvent(new Event("input", { bubbles: true })); }); };
    await fill("候选来源", "小红书美妆作者库"); await fill("内容领域", "成分护肤"); await fill("粉丝范围", "1万至10万");
    const summary = host.querySelector<HTMLTextAreaElement>('textarea[aria-label="来源与筛选条件"]')!;
    await act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(summary, "筛选适合栖月汇面膜的成分护肤达人"); summary.dispatchEvent(new Event("input", { bubbles: true })); });
    await act(async () => [...host.querySelectorAll<HTMLButtonElement>(".creator-growth-preparation button")].find((button) => button.textContent === "保存草稿")!.click());
    expect(client.executeCreatorInternalWorkflow.mock.calls[0]![0].details).toMatchObject({ productRef: "niushop:1:65", productName: "栖月汇焕亮面膜", candidateSource: "小红书美妆作者库", contentCategory: "成分护肤", audienceScale: "1万至10万", owner: "经营负责人" });
  });

  it("合作与履约页提供预算权益和交付物证据的直接补录入口", async () => {
    await act(async () => root.render(<CreatorGrowthPage client={clientFor()} />));
    expect(host.textContent).toContain("补充候选条件"); expect(host.textContent).toContain("补充预算权益"); expect(host.textContent).toContain("补充交付物证据");
    await act(async () => [...host.querySelectorAll<HTMLButtonElement>(".creator-growth-next-actions button")].find((button) => button.textContent === "补充预算权益")!.click());
    expect(host.textContent).toContain("新建合作准备"); expect(host.querySelector('input[aria-label="合作预算"]')).not.toBeNull(); expect(host.querySelector('input[aria-label="合作权益"]')).not.toBeNull();
    await act(async () => [...host.querySelectorAll<HTMLButtonElement>(".creator-growth-preparation button")].find((button) => button.textContent === "关闭")!.click());
    await act(async () => [...host.querySelectorAll<HTMLButtonElement>(".creator-growth-next-actions button")].find((button) => button.textContent === "补充交付物证据")!.click());
    expect(host.textContent).toContain("履约检查准备"); expect(host.querySelector('input[aria-label="约定交付物"]')).not.toBeNull(); expect(host.querySelector('input[aria-label="验收证据"]')).not.toBeNull();
  });
});
