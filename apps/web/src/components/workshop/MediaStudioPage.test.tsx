import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MediaStudioViewResponse } from "../../api/ecommerceWorkshop";
import { MediaStudioPage } from "./MediaStudioPage";

const response = (): MediaStudioViewResponse => ({ schemaVersion: "aos.ecommerce-workshop.media-studio-view/v3", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-24T08:00:00Z", dataCutoff: "2026-08-24T08:00:00Z", readiness: "degraded", slices: ["context", "execution", "delivery"].map((sliceId) => ({ sliceId: sliceId as "context" | "execution" | "delivery", status: "blocked", dataCutoff: "2026-08-24T08:00:00Z", readinessAxes: ["module", "capability", "assignee", "provider", "budget", "publication"].map((axis) => ({ axis: axis as "module", status: "target", exactRef: null, targetContractRef: `ADR-86#${axis}`, gaps: ["missing authority"], blockers: [{ code: "MEDIA_AUTHORITY_NOT_AVAILABLE", dependency: axis, requiredAction: "attach exact ref" }] })), authorityRefs: [], blockers: [{ code: `MEDIA_${sliceId.toUpperCase()}_AUTHORITY_NOT_AVAILABLE`, dependency: sliceId, requiredAction: "attach exact refs" }], countLedger: { denominator: 6, ready: 0, target: 6, blocked: 0, unknown: 0, conflict: 0, notApplicable: 0 } })), providerJobsStatus: "blocked", providerJobs: [], providerJobBlockers: [{ code: "MEDIA_PROVIDER_JOB_AUTHORITY_NOT_AVAILABLE", dependency: "aip.media-provider-jobs", requiredAction: "install authority" }], mediaFinanceStatus: "ready", mediaFinance: [], mediaFinanceBlockers: [], page: { limit: 100, count: 0, hasMore: false, nextCursor: null } });

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
});
