import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ContentCampaignPage } from "./ContentCampaignPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const cutoff = "2026-08-24T13:00:00Z";
const ref = (resourceType: string, resourceId: string, value = "a") => ({ resourceType, resourceId, revision: 1, contentHash: `sha256:${value.repeat(64)}`, receiptId: `receipt-${resourceId}` });
const blocked = {
  schemaVersion: "aos.ecommerce-workshop.content-campaign-view/v1" as const,
  tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded" as const,
  slices: (["plan", "calendar", "content"] as const).map((sliceId) => ({ sliceId, status: "blocked" as const, dataCutoff: cutoff, authorityRefs: [], items: [], blockers: [{ code: `CANONICAL_${sliceId.toUpperCase()}_AUTHORITY_NOT_AVAILABLE`, dependency: `ecommerce.${sliceId}`, requiredAction: "接入 exact authority" }], countLedger: { eligible: 0, attached: 0, unmatched: 0, conflicted: 0 } })),
  page: { limit: 100, count: 0, hasMore: false as const, nextCursor: null },
};
const ready = {
  ...blocked,
  slices: [
    { sliceId: "plan" as const, status: "ready" as const, dataCutoff: cutoff, authorityRefs: [ref("CampaignRevision", "campaign-1")], items: [ref("CampaignRevision", "campaign-1")], blockers: [], countLedger: { eligible: 1, attached: 1, unmatched: 0, conflicted: 0 } },
    { sliceId: "calendar" as const, status: "ready" as const, dataCutoff: cutoff, authorityRefs: [], items: [], blockers: [], countLedger: { eligible: 0, attached: 0, unmatched: 0, conflicted: 0 } },
    { sliceId: "content" as const, status: "ready" as const, dataCutoff: cutoff, authorityRefs: [ref("MasterContentIntentRevision", "intent-1")], items: [ref("MasterContentIntentRevision", "intent-1"), { ...ref("ContentVariant" as const, "variant-1", "c"), resourceType: "ContentVariant" as const, revision: 1 as const, intentRef: ref("MasterContentIntentRevision", "intent-1"), masterArtifactRef: { artifactId: "master-1", contentHash: `sha256:${"b".repeat(64)}` }, variantArtifactRef: { artifactId: "variant-1", contentHash: `sha256:${"c".repeat(64)}` }, relationId: "relation-1", relationType: "variant_of" as const }], blockers: [], countLedger: { eligible: 2, attached: 2, unmatched: 0, conflicted: 0 } },
  ],
  page: { limit: 100, count: 3, hasMore: false as const, nextCursor: null },
};
const commandResponse = {
  tenant: blocked.tenant, command: "generate" as const,
  task: { taskId: "task-1", title: "制定秋季会员回访活动方案" },
  draft: { resourceType: "TaskBriefRevision" as const, resourceId: "brief-1", revision: 1, version: 1, contentHash: "a".repeat(64), objective: "策划秋季会员回访活动", channels: ["微信小店"] },
  receipt: { receiptId: "w2r-1", operation: "task_brief.create" as const, idempotencyKey: "ui-1:brief", replay: false },
  sideEffects: { providerInvocationCount: 0 as const, approvalCreatedCount: 0 as const, taskRunCreatedCount: 0 as const, externalPublicationCount: 0 as const, externalBusinessMutationCount: 0 as const },
  message: "活动方案草稿已生成。",
};
const makeClient = (view: typeof blocked | typeof ready = blocked) => ({
  getContentCampaignView: vi.fn().mockResolvedValue(view),
  executeContentCampaignWorkflow: vi.fn().mockResolvedValue(commandResponse),
  previewContentCampaignApproval: vi.fn().mockResolvedValue({ tenant: blocked.tenant, status: "needs_input", approvalAllowed: false, draft: commandResponse.draft, checks: [], nextActions: ["补充正式经营目标与预算版本"], evaluatedAt: cutoff, dataCutoff: cutoff, sideEffects: commandResponse.sideEffects }),
});

describe("ContentCampaignPage", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); });

  it("等待正式数据时保持可信空骨架且内部业务操作可用", async () => {
    await act(async () => root.render(<ContentCampaignPage client={makeClient()} />));
    expect(host.querySelectorAll(".content-campaign-slice")).toHaveLength(3);
    expect(host.textContent).toContain("CANONICAL_PLAN_AUTHORITY_NOT_AVAILABLE");
    expect(host.querySelector(".content-campaign-assistant-summary")).not.toBeNull();
    expect(host.querySelector(".content-campaign-actionbar")).not.toBeNull();
    expect(host.querySelector('[aria-label="专业贡献归因路径"]')).not.toBeNull();
    expect(host.textContent).not.toMatch(/七夕促销|预算上限|目标 GMV|预估毛利/);
  });

  it("按视觉稿提供活动列表、中央策划、右侧协作风险与底部审批四个稳定区域", async () => {
    await act(async () => root.render(<ContentCampaignPage client={makeClient()} />));
    expect(host.querySelector(".content-campaign-list-lane")?.textContent).toContain("活动列表");
    expect(host.querySelector(".content-campaign-planning-lane")?.textContent).toContain("AI 策划助手");
    expect(host.querySelector(".content-campaign-collaboration-lane")?.textContent).toContain("风险决策");
    expect(host.querySelector(".content-campaign-actionbar")?.getAttribute("aria-label")).toBe("活动审批操作");
  });

  it("生成与审批前检查调用服务端并显示版本与回执", async () => {
    const client = makeClient();
    await act(async () => root.render(<ContentCampaignPage client={client} />));
    const suggestion = [...host.querySelectorAll<HTMLButtonElement>("button")].find((item) => item.textContent === "读取正式活动计划")!;
    await act(async () => suggestion.click());
    const generate = [...host.querySelectorAll<HTMLButtonElement>("button")].find((item) => item.textContent === "生成方案")!;
    await act(async () => generate.click());
    expect(client.executeContentCampaignWorkflow).toHaveBeenCalled();
    expect(host.textContent).toContain("当前第 1 版");
    expect(host.textContent).toContain("业务回执 w2r-1");
    expect(host.textContent).toContain("制定秋季会员回访活动方案");
    const approve = [...host.querySelectorAll<HTMLButtonElement>("button")].find((item) => item.textContent === "批准并发布")!;
    await act(async () => approve.click());
    expect(client.previewContentCampaignApproval).toHaveBeenCalled();
    expect(host.textContent).toContain("补充正式经营目标与预算版本");
  });

  it("三页签与左侧业务列表保持同一选择状态", async () => {
    await act(async () => root.render(<ContentCampaignPage client={makeClient()} />));
    const tab = [...host.querySelectorAll<HTMLButtonElement>(".content-campaign-toolbar button")].find((item) => item.textContent === "内容日历")!;
    await act(async () => tab.click());
    expect(tab.getAttribute("aria-selected")).toBe("true");
    expect(host.querySelector<HTMLButtonElement>('.content-campaign-slice[aria-pressed="true"]')?.textContent).toContain("内容日历");
  });

  it("非空 exact facts 与 ContentVariant lineage 可切换读取", async () => {
    await act(async () => root.render(<ContentCampaignPage client={makeClient(ready)} />));
    expect(host.textContent).toContain("CampaignRevision");
    const button = [...host.querySelectorAll<HTMLButtonElement>(".content-campaign-slice")].find((item) => item.textContent?.includes("主内容与变体"))!;
    await act(async () => button.click());
    expect(host.textContent).toContain("ContentVariant");
    expect(host.textContent).toContain("variant_of");
  });

  it("可信空不伪造成示例业务数据", async () => {
    const empty = { ...blocked, slices: blocked.slices.map((item) => ({ ...item, status: "ready" as const, blockers: [] })) };
    await act(async () => root.render(<ContentCampaignPage client={makeClient(empty)} />));
    expect(host.textContent).toContain("可信空集合");
    expect(host.textContent).not.toContain("七夕促销");
  });
});
