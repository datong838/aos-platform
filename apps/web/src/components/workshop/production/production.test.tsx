import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ArtifactRevisionViewer,
  AuthorityStateBoundary,
  BriefInspector,
  EvalContractBadge,
  EvalContractDiff,
  EvidenceBundleDrawer,
  ImpactPreviewDialog,
  ResponsibilityMatrix,
  ReviewIssuePanel,
  StageTimeline,
  type ProductionComponentBase,
  type ProductionExactRef,
  type ProductionUiState,
} from ".";

const hash = "a".repeat(64);
const ref = (resourceType: string, resourceId: string): ProductionExactRef => ({ resourceType, resourceId, revision: 1, contentHash: hash });
const lineage = { atomicSkillRef: ref("SkillPublicationRevision", "build-evidence-pack"), logicRef: ref("LogicRevision", "content-production"), coworker: { roleName: "内容官", assigneeId: "agent-content-1" }, workshopContribution: "生成并复核内容产物" };
const blocker = { code: "EVIDENCE_STALE", message: "证据已过期", owner: "数据与证据负责人", requiredAction: "刷新 exact EvidenceBundle", cutoffAt: "2026-08-25T01:00:00Z" };
const base = <Kind extends string>(title: string, allowedIntents: readonly Kind[] = []): Omit<ProductionComponentBase<Kind>, "onIntent"> => ({ title, state: "ready", lineage, blockers: [], allowedIntents });

describe("W3-09 common production UI", () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => { (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true; host = document.createElement("div"); document.body.append(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("由唯一 public identity 导出九个命名组件并显示 Skill Logic 数字同事贡献链", () => {
    act(() => root.render(<div>
      <BriefInspector {...base("任务简报", ["revise"])} briefRef={ref("TaskBriefRevision", "brief-1")} summary="目标摘要" diff={[]} />
      <EvidenceBundleDrawer {...base("证据包", ["select"])} bundleRef={ref("EvidenceBundleRevision", "bundle-1")} evidenceRefs={[]} open onClose={() => undefined} />
      <EvalContractBadge {...base("评价契约", ["select"])} contractRef={ref("EvalContractRevision", "eval-1")} decision="待评价" />
      <EvalContractDiff {...base("评价差异")} rows={[{ field: "阈值", before: "0.8", after: "0.9" }]} />
      <ResponsibilityMatrix {...base("职责矩阵")} planRef={ref("ResponsibilityPlanRevision", "plan-1")} slots={[]} />
      <StageTimeline {...base("阶段时间线")} planRef={ref("PlanRevision", "run-plan-1")} stages={[]} />
      <ArtifactRevisionViewer {...base("产物修订")} artifactRef={ref("ArtifactRevision", "artifact-1")} family="内容" relation="supersedes" />
      <ReviewIssuePanel {...base("评审问题")} issueRef={ref("ReviewIssueRevision", "issue-1")} severity="warning" suggestedFix="补充来源" />
      <ImpactPreviewDialog {...base("影响预览")} previewRef={ref("ImpactPreviewRevision", "preview-1")} rows={[]} open onClose={() => undefined} />
    </div>));
    expect(host.querySelectorAll(".production-frame")).toHaveLength(9);
    expect(host.textContent).toContain("原子 Skill");
    expect(host.textContent).toContain("build-evidence-pack");
    expect(host.textContent).toContain("Logic 编排");
    expect(host.textContent).toContain("内容官 · agent-content-1");
    expect(host.textContent).toContain("工作台贡献");
  });

  it.each<ProductionUiState>(["loading", "empty", "partial", "stale", "blocked", "forbidden", "unknown", "ready", "failed"])("区分 %s 状态", (state) => {
    act(() => root.render(<AuthorityStateBoundary state={state} title="状态测试"><span data-testid="content">canonical content</span></AuthorityStateBoundary>));
    expect(host.querySelector("section")?.getAttribute("aria-label")).toContain("状态测试");
    if (["loading", "empty", "forbidden", "failed"].includes(state)) expect(host.querySelector('[data-testid="content"]')).toBeNull();
    else expect(host.textContent).toContain("canonical content");
  });

  it("unknown 不归零且 blocked command 可聚焦但不发 intent", () => {
    const onIntent = vi.fn();
    act(() => root.render(<BriefInspector {...base("未知简报")} state="blocked" blockers={[blocker]} onIntent={onIntent} briefRef={ref("TaskBriefRevision", "brief-1")} summary="数量 unknown，不显示 0" diff={[]} />));
    const button = host.querySelector("button") as HTMLButtonElement;
    button.focus();
    expect(document.activeElement).toBe(button);
    expect(button.getAttribute("aria-disabled")).toBe("true");
    act(() => button.click());
    expect(onIntent).not.toHaveBeenCalled();
    expect(host.textContent).toContain("数量 unknown，不显示 0");
    expect(host.textContent).toContain("刷新 exact EvidenceBundle");
  });

  it("只发 typed intent，不调用 SDK 或乐观改写 authority", () => {
    const onIntent = vi.fn();
    const subjectRef = ref("TaskBriefRevision", "brief-1");
    act(() => root.render(<BriefInspector {...base("任务简报", ["freeze"])} onIntent={onIntent} briefRef={subjectRef} summary="待冻结" diff={[]} />));
    const freeze = [...host.querySelectorAll("button")].find((item) => item.textContent === "冻结") as HTMLButtonElement;
    act(() => freeze.click());
    expect(onIntent).toHaveBeenCalledWith({ kind: "freeze", subjectRef });
    expect(host.textContent).toContain("待冻结");
  });

  it("Dialog Escape 关闭并把焦点返回触发器", () => {
    const trigger = document.createElement("button"); document.body.append(trigger);
    const onClose = vi.fn();
    act(() => root.render(<ImpactPreviewDialog {...base("影响预览", ["confirm"])} previewRef={ref("ImpactPreviewRevision", "preview-1")} rows={[]} open onClose={onClose} returnFocusRef={{ current: trigger }} />));
    const dialog = host.querySelector('[role="dialog"]') as HTMLElement;
    expect(document.activeElement?.textContent).toContain("关闭影响预览");
    const buttons = dialog.querySelectorAll("button");
    buttons[buttons.length - 1].focus();
    act(() => buttons[buttons.length - 1].dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true })));
    expect(document.activeElement?.textContent).toContain("关闭影响预览");
    act(() => dialog.parentElement?.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });

  it("Timeline 与 Diff 提供可读表格文本替代", () => {
    act(() => root.render(<div><StageTimeline {...base("阶段时间线")} planRef={ref("PlanRevision", "plan-1")} stages={[{ stageId: "draft", title: "起草", state: "partial", assignee: null }]} /><EvalContractDiff {...base("契约差异")} rows={[{ field: "阈值", before: "未知", after: "0.9" }]} /></div>));
    const captions = [...host.querySelectorAll("caption")].map((item) => item.textContent);
    expect(captions).toContain("生产阶段时间线文本替代");
    expect(captions).toContain("评价契约修订差异的文本替代");
    expect(host.textContent).toContain("unknown");
  });

  it("Evidence Drawer 不预取正文，逐层调用服务端并对拒绝保持零正文", async () => {
    const evidenceRef = ref("Evidence", "evidence-1");
    const decision = (level: "l1" | "l2", status: "allowed" | "blocked") => ({
      tenant: { orgId: "org-org", projectId: "dev-project" }, decisionId: `decision-${level}`,
      evidenceRef: { ...evidenceRef, resourceType: "Evidence" as const }, purpose: level === "l1" ? "summary" as const : "excerpt" as const,
      requestedLevel: level, grantedLevel: status === "allowed" ? level : null, status,
      reasons: status === "blocked" ? ["MARKING_ACCESS_DENIED"] : [],
      citation: {}, displayPayload: status === "allowed" ? { layer: level, sourceType: "database", capturedAt: "2026-08-25T01:00:00Z", freshnessAt: "2026-08-25T01:00:00Z", applicability: "applicable", marking: ["public"], licenseStatus: "internal_controlled" } : {},
      redactionReceipt: { bodyReturned: status === "allowed" }, decisionHash: "b".repeat(64), expiresAt: null, createdBy: "user:dev", createdAt: "2026-08-25T01:00:00Z",
    });
    const resolveDisclosure = vi.fn().mockResolvedValueOnce(decision("l1", "allowed")).mockResolvedValueOnce(decision("l2", "blocked"));
    act(() => root.render(<EvidenceBundleDrawer {...base("证据包")} bundleRef={ref("EvidenceBundleRevision", "bundle-1")} evidenceRefs={[evidenceRef]} open onClose={() => undefined} disclosureSdk={{ resolveDisclosure }} />));
    expect(resolveDisclosure).not.toHaveBeenCalled();
    const button = (label: string) => [...host.querySelectorAll("button")].find((item) => item.textContent === label) as HTMLButtonElement;
    expect(button("查看最小引用片段").disabled).toBe(true);
    await act(async () => { button("查看安全摘要").click(); });
    expect(resolveDisclosure).toHaveBeenNthCalledWith(1, expect.objectContaining({ purpose: "summary", requestedLevel: "l1" }), expect.stringContaining("workshop-disclosure-"));
    expect(host.textContent).toContain("已授权 · L1");
    expect(button("查看最小引用片段").disabled).toBe(false);
    await act(async () => { button("查看最小引用片段").click(); });
    expect(resolveDisclosure).toHaveBeenNthCalledWith(2, expect.objectContaining({ purpose: "excerpt", requestedLevel: "l2" }), expect.stringContaining("workshop-disclosure-"));
    expect(host.textContent).toContain("服务端未返回正文");
    expect(host.textContent).toContain("MARKING_ACCESS_DENIED");
    expect(host.textContent).not.toContain("最小片段");
    expect(button("申请短期来源引用").disabled).toBe(true);
  });
});
