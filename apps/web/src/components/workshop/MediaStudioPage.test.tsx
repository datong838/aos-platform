import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FullVideoScenarioContribution, MediaStudioViewResponse } from "../../api/ecommerceWorkshop";
import { MediaStudioPage } from "./MediaStudioPage";

const response = (): MediaStudioViewResponse => ({ schemaVersion: "aos.ecommerce-workshop.media-studio-view/v3", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-24T08:00:00Z", dataCutoff: "2026-08-24T08:00:00Z", readiness: "degraded", slices: ["context", "execution", "delivery"].map((sliceId) => ({ sliceId: sliceId as "context" | "execution" | "delivery", status: "blocked", dataCutoff: "2026-08-24T08:00:00Z", readinessAxes: ["module", "capability", "assignee", "provider", "budget", "publication"].map((axis) => ({ axis: axis as "module", status: "target", exactRef: null, targetContractRef: `ADR-86#${axis}`, gaps: ["missing authority"], blockers: [{ code: "MEDIA_AUTHORITY_NOT_AVAILABLE", dependency: axis, requiredAction: "attach exact ref" }] })), authorityRefs: [], blockers: [{ code: `MEDIA_${sliceId.toUpperCase()}_AUTHORITY_NOT_AVAILABLE`, dependency: sliceId, requiredAction: "attach exact refs" }], countLedger: { denominator: 6, ready: 0, target: 6, blocked: 0, unknown: 0, conflict: 0, notApplicable: 0 } })), providerJobsStatus: "blocked", providerJobs: [], providerJobBlockers: [{ code: "MEDIA_PROVIDER_JOB_AUTHORITY_NOT_AVAILABLE", dependency: "aip.media-provider-jobs", requiredAction: "install authority" }], mediaFinanceStatus: "ready", mediaFinance: [], mediaFinanceBlockers: [], lifecycleStatus: "blocked", lifecycle: null, lifecycleBlockers: [{ code: "MEDIA_LIFECYCLE_LEGACY_VIEW", dependency: "media-studio-v4", requiredAction: "refresh canonical v4 projection" }], publishStatus: "blocked", publishContributions: [], publishBlockers: [{ code: "MEDIA_PUBLISH_LEGACY_VIEW", dependency: "media-studio-v5", requiredAction: "refresh canonical v5 projection" }], page: { limit: 100, count: 0, hasMore: false, nextCursor: null } });

const fullVideoScenario = (): FullVideoScenarioContribution => {
  const contentHash = `sha256:${"a".repeat(64)}`; const ref = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash });
  const blocker = { code: "FULL_VIDEO_EXTERNAL_GATE_REQUIRED", dependency: "workshop.full-video", requiredAction: "append exact current evidence" };
  const stageIds = ["brief_profile", "compile_start", "script_art", "storyboard_capture", "post_review", "publish_delivery", "settlement_effect"] as const;
  const responsibilityIds = ["media.producer", "media.director", "media.screenwriter", "media.art", "media.storyboard", "media.capture", "media.post", "media.review"] as const;
  const faultIds = ["crash_before_submit", "crash_after_submit_before_receipt", "lease_fence_loss", "webhook_ordering", "timeout_cancel_late_result", "checkpoint_drift", "capacity_budget_race", "restart_partition", "malicious_artifact"] as const;
  const brief = ref("MediaProductionBriefRevision", "brief-full-1"); const run = ref("TaskRun", "run-full-1");
  return { schemaVersion: "aos.ecommerce-workshop.full-video-scenario/v1", status: "blocked", rootBriefRef: brief, taskRunRef: run, fullProductionBindingHash: "b".repeat(64), composition: { atomicSkillRefs: [ref("SkillRevision", "media-script"), ref("SkillRevision", "media-review")], logicRevisionRef: ref("LogicRevision", "full-short-video-production"), roleBindings: [{ roleRef: ref("AgentTemplate", "content-officer"), assigneeRef: ref("AgentInstance", "content-officer-1"), skillBindingRef: ref("SkillBinding", "media-script-binding") }] }, evaluatedAt: "2026-08-26T06:00:00Z", responsibilities: responsibilityIds.map((responsibilityId, index) => ({ responsibilityId, label: responsibilityId, status: "assigned", assigneeRef: ref("AgentInstance", `assignee-${index % 3}`), skillBindingRef: ref("SkillBinding", `binding-${index}`), independentReviewRequired: responsibilityId === "media.review", blocker: null })), stages: stageIds.map((stageId, index) => index < 5 ? { stageId, status: "ready", exactRefs: [index === 0 ? brief : index === 1 ? run : ref("ArtifactRevision", `artifact-${index}`)], contribution: `stage ${stageId}`, blocker: null } : { stageId, status: "blocked", exactRefs: [], contribution: "external gate blocked", blocker }), faultRecovery: faultIds.map((faultId, index) => index < 8 ? { faultId, status: "ready", recoveryDecision: `durable ${faultId}`, authorityRefs: [ref("RecoveryDecisionReceipt", `recovery-${index}`)], blocker: null, automaticRetryAllowed: false } : { faultId, status: "unknown", recoveryDecision: "quarantine evidence required", authorityRefs: [], blocker, automaticRetryAllowed: false }), ledger: { responsibilitiesExpected: 8, responsibilitiesObserved: 8, stagesExpected: 7, stagesObserved: 5, attemptsExpected: 5, attemptsObserved: 5, artifactsExpected: 6, artifactsObserved: 6, mediaGatesExpected: 4, mediaGatesObserved: 4, faultCasesExpected: 9, faultCasesObserved: 8, usageBucketsExpected: 2, usageBucketsObserved: 2 }, blockers: [blocker], commands: { prepare: false, start: false, resume: false, takeover: false, cancel: false, reconcile: false, publish: false, settle: false }, externalEffectsAllowed: false, releaseAllowed: false };
};

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
    expect(host.querySelectorAll(".media-studio-summary-metrics article")).toHaveLength(4);
    expect(host.querySelectorAll(".media-studio-summary-metrics strong")).toHaveLength(4);
    expect(Array.from(host.querySelectorAll(".media-studio-summary-metrics strong")).map((item) => item.textContent)).toEqual(["unknown", "unknown", "unknown", "unknown"]);
    expect(host.querySelector(".media-studio-context-strip")?.textContent).toContain("内容官（owner 未绑定）");
    expect(host.querySelector(".media-studio-context-strip")?.textContent).toContain("今日计划：unknown");
    expect(host.querySelector(".media-studio-task-empty")?.textContent).toContain("当前没有可审阅文案任务");
    expect(host.querySelector(".media-studio-production-empty")?.textContent).toContain("等待生产上下文");
    expect(host.querySelector(".media-studio-advice-empty")?.textContent).toContain("尚无可回链内容建议");
    expect(host.textContent).not.toMatch(/七夕专题|banner 文案|历史回款 CTR|整体 GMV 贡献 ¥/);
    expect(Array.from(host.querySelectorAll<HTMLButtonElement>("button")).some((button) => button.textContent === "重新读取")).toBe(true);
    expect(host.textContent).toContain("target ≠ achieved；Provider submitted ≠ delivered；published、settled 与 effect-reviewed 分轴。");
    expect(host.textContent).not.toMatch(/开始|发布|取消|批准|结算|对账/);
  });

  it("切换 Tab 不制造业务事实", async () => {
    await act(async () => { root.render(<MediaStudioPage client={{ getMediaStudioView: vi.fn().mockResolvedValue(response()) }} />); });
    const tab = Array.from(host.querySelectorAll<HTMLButtonElement>('[role="tab"]')).find((item) => item.textContent?.includes("短视频"));
    expect(tab).toBeTruthy();
    act(() => tab?.click());
    expect(host.querySelector('[role="tabpanel"]')?.textContent).toContain("当前没有可挂接的媒体 authority");
  });

  it("用 roving tabindex 和稳定 controls 支持方向键、Home 与 End", async () => {
    await act(async () => { root.render(<MediaStudioPage client={{ getMediaStudioView: vi.fn().mockResolvedValue(response()) }} />); });
    const tabs = host.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    const panel = host.querySelector<HTMLElement>('[role="tabpanel"]');
    expect(tabs[0]?.tabIndex).toBe(0);
    expect(tabs[1]?.tabIndex).toBe(-1);
    expect(tabs[0]?.getAttribute("aria-controls")).toBe(panel?.id);
    act(() => tabs[0]?.dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true })));
    expect(tabs[2]?.tabIndex).toBe(0);
    expect(host.querySelector<HTMLElement>('[role="tabpanel"]')?.getAttribute("aria-labelledby")).toBe(tabs[2]?.id);
    act(() => tabs[2]?.dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true })));
    expect(tabs[0]?.tabIndex).toBe(0);
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
    expect(Array.from(host.querySelectorAll("button")).map((item) => item.textContent)).toEqual(["重新读取", "种草文案blocked", "短视频blocked", "数字人直播blocked"]);
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
    expect(Array.from(host.querySelectorAll("button")).map((item) => item.textContent)).toEqual(["重新读取", "种草文案blocked", "短视频blocked", "数字人直播blocked"]);
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
    expect(Array.from(host.querySelectorAll("button")).map((item) => item.textContent)).toEqual(["重新读取", "种草文案blocked", "短视频blocked", "数字人直播blocked"]);
  });

  it("展示 Candidate 到 Handoff 的 canonical 发布贡献但不生成发布按钮", async () => {
    const payload = response();
    const hash = "a".repeat(64); const binding = "b".repeat(64);
    const ref = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash: hash });
    payload.schemaVersion = "aos.ecommerce-workshop.media-studio-view/v5";
    payload.publishStatus = "ready"; payload.publishBlockers = [];
    payload.publishContributions = [{ schemaVersion: "aos.ecommerce-workshop.media-publish-contribution/v1", candidate: { familyId: "family-1", familyVersion: 3, variantRef: ref("ArtifactRevision", "variant-1"), gateSetRef: ref("MediaGateSetDecision", "gate-1"), platform: "douyin", profile: "short-video" }, impact: { previewRef: ref("ImpactPreviewRevision", "preview-1"), actionBindingHash: binding, readiness: "ready", expiresAt: "2026-08-27T00:00:00Z", atomicSkillRefs: [ref("CapabilityRevision", "content.publish")], logicRef: ref("PlanRevision", "logic-media-publish"), colleagueBindingRefs: [] }, action: { proposalId: "proposal-1", proposalVersion: 2, proposalHash: hash, status: "approved", actionBindingHash: binding, approvalCount: 1, leaseId: null, attemptId: null }, receipt: null, handoff: { status: "required", reasonCode: "MEDIA_PUBLISH_MANUAL_EVIDENCE_REQUIRED", requiredFacts: ["provider object identity"], minimalDisclosure: true, completionReceiptRequired: true, completionAllowed: false }, blockerCodes: ["MEDIA_PUBLISH_EXTERNAL_EFFECT_NOT_AUTHORIZED", "MEDIA_PUBLISH_RECEIPT_NOT_AVAILABLE"], externalEffectsAllowed: false }];
    await act(async () => { root.render(<MediaStudioPage client={{ getMediaStudioView: vi.fn().mockResolvedValue(payload) }} />); });
    expect(host.textContent).toContain("Candidate → Impact → Action → Receipt → Handoff");
    expect(host.textContent).toContain("variant-1 · short-video");
    expect(host.textContent).toContain("logic-media-publish");
    expect(host.textContent).toContain("尚无 Receipt");
    expect(host.textContent).toContain("required · 仅最小披露");
    expect(Array.from(host.querySelectorAll("button")).map((item) => item.textContent)).toEqual(["重新读取", "种草文案blocked", "短视频blocked", "数字人直播blocked"]);
  });

  it("展示 W7 十一栏累计门且保留 Provider、Canary 和运营阻断", async () => {
    const payload = response();
    const gateIds = ["contract_green", "service_green", "database_restart_green", "tenant_rls_green", "browser_positive_green", "browser_negative_green", "security_green", "fault_injection_green", "provider_adapter_green", "publish_canary_green", "operational_ready"] as const;
    payload.schemaVersion = "aos.ecommerce-workshop.media-studio-view/v6";
    payload.cumulativeGateSet = { schemaVersion: "aos.ecommerce-workshop.media-cumulative-gates/v1", releaseRevision: "AOS-000267", evaluatedAt: "2026-08-26T02:30:00Z", gates: gateIds.map((gateId, index) => index < 8 ? { gateId, status: "ready", evidenceRef: { resourceType: "EvidencePack", resourceId: "workshop-w7-11", revision: "AOS-000267", contentHash: "f".repeat(64) }, reasonCode: "MEDIA_ENGINEERING_EVIDENCE_CURRENT", observedAt: "2026-08-26T02:30:00Z", externalEffectsObserved: false } : { gateId, status: "blocked", evidenceRef: null, reasonCode: ["MEDIA_PRODUCTION_PROVIDER_ADAPTER_RECEIPT_REQUIRED", "MEDIA_PUBLISH_CANARY_RECEIPT_REQUIRED", "MEDIA_OPERATIONAL_READY_RECEIPT_REQUIRED"][index - 8] ?? "MEDIA_OPERATIONAL_READY_RECEIPT_REQUIRED", observedAt: null, externalEffectsObserved: false }), overallStatus: "blocked", blockerCodes: ["MEDIA_OPERATIONAL_READY_RECEIPT_REQUIRED", "MEDIA_PRODUCTION_PROVIDER_ADAPTER_RECEIPT_REQUIRED", "MEDIA_PUBLISH_CANARY_RECEIPT_REQUIRED"], externalEffectsAllowed: false, releaseAllowed: false };
    await act(async () => { root.render(<MediaStudioPage client={{ getMediaStudioView: vi.fn().mockResolvedValue(payload) }} />); });
    expect(host.textContent).toContain("W7 累计门 · 十一栏独立证据");
    expect(host.querySelectorAll('[aria-label="W7媒体累计十一栏验收门"] .media-command-grid article')).toHaveLength(11);
    expect(host.textContent).toContain("provider_adapter_greenblocked");
    expect(host.textContent).toContain("外部副作用：关闭 · Release：关闭");
    expect(Array.from(host.querySelectorAll("button")).map((item) => item.textContent)).toEqual(["重新读取", "种草文案blocked", "短视频blocked", "数字人直播blocked"]);
  });

  it("展示 FULL 视频四层贡献、八职责、七阶段和九类故障且无写按钮", async () => {
    await act(async () => { root.render(<MediaStudioPage client={{ getMediaStudioView: vi.fn().mockResolvedValue(response()), getMediaStudioFullProductionScenario: vi.fn().mockResolvedValue(fullVideoScenario()) }} />); });
    expect(host.textContent).toContain("FULL 短视频生产 · 故障恢复");
    expect(host.textContent).toContain("原子 Skill → Logic 编排 → 数字同事绑定 → 工作台贡献");
    expect(host.querySelectorAll(".full-video-responsibility-grid article")).toHaveLength(8);
    expect(host.querySelectorAll(".full-video-stage-grid article")).toHaveLength(7);
    expect(host.querySelectorAll(".full-video-fault-grid article")).toHaveLength(9);
    expect(host.textContent).toContain("故障证据 8/9");
    expect(host.querySelectorAll(".full-video-scenario .media-command-grid article")).toHaveLength(8);
    expect(Array.from(host.querySelectorAll("button")).map((item) => item.textContent)).toEqual(["重新读取", "种草文案blocked", "短视频blocked", "数字人直播blocked"]);
  });
});
