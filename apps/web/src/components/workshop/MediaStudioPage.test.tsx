import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MediaStudioViewResponse } from "../../api/ecommerceWorkshop";
import { MediaStudioPage } from "./MediaStudioPage";

const response = (): MediaStudioViewResponse => ({ schemaVersion: "aos.ecommerce-workshop.media-studio-view/v3", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-24T08:00:00Z", dataCutoff: "2026-08-24T08:00:00Z", readiness: "degraded", slices: ["context", "execution", "delivery"].map((sliceId) => ({ sliceId: sliceId as "context" | "execution" | "delivery", status: "blocked", dataCutoff: "2026-08-24T08:00:00Z", readinessAxes: ["module", "capability", "assignee", "provider", "budget", "publication"].map((axis) => ({ axis: axis as "module", status: "target", exactRef: null, targetContractRef: `ADR-86#${axis}`, gaps: ["missing authority"], blockers: [{ code: "MEDIA_AUTHORITY_NOT_AVAILABLE", dependency: axis, requiredAction: "attach exact ref" }] })), authorityRefs: [], blockers: [{ code: `MEDIA_${sliceId.toUpperCase()}_AUTHORITY_NOT_AVAILABLE`, dependency: sliceId, requiredAction: "attach exact refs" }], countLedger: { denominator: 6, ready: 0, target: 6, blocked: 0, unknown: 0, conflict: 0, notApplicable: 0 } })), providerJobsStatus: "blocked", providerJobs: [], providerJobBlockers: [{ code: "MEDIA_PROVIDER_JOB_AUTHORITY_NOT_AVAILABLE", dependency: "aip.media-provider-jobs", requiredAction: "install authority" }], mediaFinanceStatus: "ready", mediaFinance: [], mediaFinanceBlockers: [], lifecycleStatus: "blocked", lifecycle: null, lifecycleBlockers: [{ code: "MEDIA_LIFECYCLE_LEGACY_VIEW", dependency: "media-studio-v4", requiredAction: "refresh canonical v4 projection" }], page: { limit: 100, count: 0, hasMore: false, nextCursor: null } });

describe("MediaStudioPage", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("展示三切片 target 边界且没有媒体写入口", async () => {
    await act(async () => { root.render(<MediaStudioPage client={{ getMediaStudioView: vi.fn().mockResolvedValue(response()) }} />); });
    expect(host.querySelectorAll('[role="tab"]')).toHaveLength(3);
    expect(host.textContent).toContain("target ≠ achieved；Provider submitted ≠ delivered；published、settled 与 effect-reviewed 分轴。");
    expect(host.textContent).not.toMatch(/开始|发布|取消|批准|结算|对账/);
  });

  it("切换 Tab 不制造业务事实", async () => {
    await act(async () => { root.render(<MediaStudioPage client={{ getMediaStudioView: vi.fn().mockResolvedValue(response()) }} />); });
    const tab = Array.from(host.querySelectorAll<HTMLButtonElement>('[role="tab"]')).find((item) => item.textContent?.includes("职责与执行"));
    expect(tab).toBeTruthy();
    act(() => tab?.click());
    expect(host.querySelector('[role="tabpanel"]')?.textContent).toContain("当前没有可挂接的媒体 authority");
  });

  it("展示原子能力到数字同事的 Provider Job 贡献链且不提供写按钮", async () => {
    const payload = response();
    const ref = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash: "a".repeat(64) });
    payload.providerJobsStatus = "ready";
    payload.providerJobBlockers = [];
    payload.providerJobs = [{ jobId: "media-job-1", status: "unknown", sequence: 3, atomicCapabilityRef: ref("CapabilityRevision", "media-generate"), logicRef: ref("TaskRun", "logic-run-1"), colleagueBindingRef: ref("CapabilityBindingRevision", "content-officer-binding"), modelRef: ref("RegisteredModelRevision", "image-model"), providerRef: ref("ProviderInstanceRevision", "image-provider"), adapterRef: ref("MediaProviderAdapterRevision", "image-adapter"), scanRefs: [ref("MediaScanObservation", "scan-1")], primaryColleague: "内容官", collaboratorColleagues: ["活动策划师", "数据参谋"], blockerCodes: ["MEDIA_PROVIDER_RESULT_UNKNOWN_RECONCILE_REQUIRED"], externalEffectsAllowed: false }];
    await act(async () => { root.render(<MediaStudioPage client={{ getMediaStudioView: vi.fn().mockResolvedValue(payload) }} />); });
    expect(host.textContent).toContain("原子 Skill → Logic 编排 → 数字同事 → 工作台贡献");
    expect(host.textContent).toContain("内容官 · unknown");
    expect(host.textContent).toContain("media-generate");
    expect(host.textContent).toContain("外部副作用关闭");
    expect(Array.from(host.querySelectorAll("button")).map((item) => item.textContent)).toEqual(["重新读取", "生产上下文blocked", "职责与执行blocked", "交付与复盘blocked"]);
  });

  it("按币种分轴展示双预留、取消、Usage 与 Settlement 且保持只读", async () => {
    const payload = response();
    const ref = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash: "b".repeat(64) });
    payload.mediaFinance = [{ financeId: "media-fin-1", jobId: "media-job-1", version: 6, attemptBindingHash: "c".repeat(64), capacityReservationRef: ref("MediaCapacityReservation", "capacity-1"), budgetReservationRef: ref("MediaBudgetReservation", "budget-1"), projectedMinMinor: 800, projectedMaxMinor: 1200, projectedCurrency: "CNY", reservationsActive: true, cancelOutcome: "too_late", feeConclusion: "chargeable", settlementStatus: "settled", currencyBuckets: [{ currency: "CNY", measuredMinor: 1000, estimatedMinor: 0, unknownCount: 0, adjustmentMinor: 100, refundMinor: 50, residualMinor: -150 }, { currency: "USD", measuredMinor: 0, estimatedMinor: 25, unknownCount: 0, adjustmentMinor: 0, refundMinor: 0, residualMinor: 25 }], blockerCodes: [], externalEffectsAllowed: false }];
    await act(async () => { root.render(<MediaStudioPage client={{ getMediaStudioView: vi.fn().mockResolvedValue(payload) }} />); });
    expect(host.textContent).toContain("Capacity / Budget / Usage / Cancel / Settlement");
    expect(host.textContent).toContain("CNY：measured 1000");
    expect(host.textContent).toContain("USD：measured 0 / estimated 25");
    expect(host.textContent).toContain("too_late");
    expect(Array.from(host.querySelectorAll("button")).map((item) => item.textContent)).toEqual(["重新读取", "生产上下文blocked", "职责与执行blocked", "交付与复盘blocked"]);
  });

  it("按 frozen context 在三 Tab 展示七节点、八职责、Stage、Artifact、Issue 与禁用命令", async () => {
    const payload = response();
    const authorityRef = { resourceType: "ProductionContextRevision", resourceId: "context-1", revision: 2, contentHash: "d".repeat(64) };
    const nodeIds = ["prepare", "freeze_confirm", "compile_approve", "start_run", "review_return", "deliver_publish", "reconcile_effect"] as const;
    const slotIds = ["media.producer", "media.director", "media.screenwriter", "media.art", "media.storyboard", "media.capture", "media.post", "media.review"] as const;
    payload.schemaVersion = "aos.ecommerce-workshop.media-studio-view/v4";
    payload.lifecycleStatus = "ready";
    payload.lifecycleBlockers = [];
    payload.lifecycle = { schemaVersion: "aos.ecommerce-workshop.media-studio-lifecycle/v1", contextId: "context-1", contextRevision: 2, contextHash: "d".repeat(64), taskId: "task-1", status: "partial", lifecycle: nodeIds.map((nodeId, index) => ({ nodeId, label: nodeId, status: index < 4 ? "active" : index === 4 ? "not_started" : "blocked", authorityRefs: index < 4 ? [authorityRef] : [], blockerCodes: index > 4 ? ["MEDIA_NOT_AUTHORIZED"] : [], observedAt: null })), responsibilities: slotIds.map((slotId) => ({ slotId, label: slotId, responsibilityType: `responsibility:${slotId}`, status: "assigned", requiredCapabilityIds: ["strategy.plan"], assigneeKind: "agent_instance", assigneeId: `agent:${slotId}`, assigneeVersion: 1, resolutionReceiptId: `receipt:${slotId}`, blockerCodes: [] })), stages: [{ stageId: "stage-post", taskRunId: "run-1", attempt: 4, status: "unknown", capabilityRef: { ...authorityRef, resourceType: "CapabilityRevision", resourceId: "video.compose" }, colleagueBindingRef: { ...authorityRef, resourceType: "ColleagueBindingRevision", resourceId: "content-officer" }, providerRef: { ...authorityRef, resourceType: "ProviderInstanceRevision", resourceId: "provider-disabled" }, providerJobId: "job-1", blockerCodes: ["MEDIA_PROVIDER_RESULT_UNKNOWN_RECONCILE_REQUIRED"], externalEffectsAllowed: false }], artifactFamilies: [{ familyId: "family-1", version: 2, topologyStatus: "valid", memberCount: 3, conflictCount: 0, gateSetCount: 1, latestGateReadiness: "ready", issueCount: 1 }], reviewIssues: [{ issueId: "issue-1", version: 1, status: "open", severity: "major", artifactId: "artifact-1", artifactHash: "e".repeat(64), returnStage: "media.post", returnDecisionCount: 1 }], commandCapabilities: ["freeze", "start", "pause_resume", "return", "publish", "settle_reconcile"].map((commandId) => ({ commandId, allowed: false, reasonCode: "MEDIA_STUDIO_W7_09_READ_ONLY_NO_EXTERNAL_EFFECT", expectedVersion: 2, requiredExactRefs: [authorityRef] })), blockerCodes: ["MEDIA_PUBLICATION_NOT_AUTHORIZED", "MEDIA_EFFECT_REVIEW_NOT_AUTHORIZED"], externalEffectsAllowed: false };
    await act(async () => { root.render(<MediaStudioPage client={{ getMediaStudioView: vi.fn().mockResolvedValue(payload) }} />); });
    expect(host.textContent).toContain("冻结生产上下文context-1 · r2");
    expect(host.textContent).toContain("publish不可执行");
    const tabs = Array.from(host.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
    act(() => tabs[1]?.click());
    expect(host.querySelectorAll(".media-responsibility-grid article")).toHaveLength(8);
    expect(host.textContent).toContain("video.compose → content-officer → provider-disabled");
    act(() => tabs[2]?.click());
    expect(host.textContent).toContain("family-1");
    expect(host.textContent).toContain("issue-1 · major");
    expect(Array.from(host.querySelectorAll("button")).map((item) => item.textContent)).toEqual(["重新读取", "生产上下文blocked", "职责与执行blocked", "交付与复盘blocked"]);
  });
});
