import { describe, expect, it } from "vitest";
import { parseInvestigationCaseList, parseInvestigationRunList, parseInvestigationWorkbenchView } from "./parser";

const hash = `sha256:${"a".repeat(64)}`; const tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = (resourceType: string, resourceId: string, revision = 1) => ({ resourceType, resourceId, revision, contentHash: hash });
const caseItem = { schemaVersion: "aos.ecommerce.business-investigation-case/v1", tenant, caseId: "case-1", revision: 1, version: 1, priorRef: null, contentHash: hash, lifecycle: "ACTIVE", analysisType: "initial_store_analysis", title: "首次全店经营分析", purposeCode: "business.investigation.initial", channelRef: ref("ChannelRevision", "private-mall"), businessEntityRef: ref("BusinessEntityRevision", "store-1"), entityChannelBindingRef: ref("BusinessEntityChannelBindingRevision", "binding-1"), investigationProfileRef: ref("InvestigationProfileRevision", "profile-1"), scopeRef: ref("InvestigationScopeRevision", "scope-1"), schedulePolicyRef: null, createdBy: "user-1", createdAt: "2026-08-26T08:00:00Z" };
const runItem = { authority: { schemaVersion: "aos.ecommerce.business-investigation-run/v1", tenant, runId: "run-1", version: 1, contentHash: hash, caseRef: ref("BusinessInvestigationCaseRevision", "case-1"), analysisType: "initial_store_analysis", triggerKind: "manual", triggerKey: "manual:run-1", lifecycle: "PREPARING", control: "RUNNING", createdBy: "user-1", createdAt: "2026-08-26T08:01:00Z" }, state: { schemaVersion: "aos.ecommerce.business-investigation-run-state/v1", tenant, runId: "run-1", version: 1, priorRef: null, lifecycle: "PREPARING", control: "RUNNING", eventSequence: 1, contentHash: hash, pendingRequirementRef: null, uncertainCommand: null, createdBy: "user-1", createdAt: "2026-08-26T08:01:00Z" } };
const resourceRef = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: "1", authority: "test-authority" });
const view = { schemaVersion: "aos.ecommerce.business-investigation-workbench-view/v3", tenant, projectionHash: hash, sourceWatermark: { caseRevision: 1, runVersion: 1, stateVersion: 1, bindingHashes: [], runtimeHash: hash, contentHash: hash }, observedAt: "2026-08-26T08:10:00Z", caseRef: ref("BusinessInvestigationCaseRevision", "case-1"), runRef: ref("BusinessInvestigationRun", "run-1"), stateRef: ref("BusinessInvestigationRunStateRevision", "run-1"), caseEnvelope: { title: "首次全店经营分析", analysisType: "initial_store_analysis", lifecycle: "ACTIVE", channelRef: ref("ChannelRevision", "private-mall"), businessEntityRef: ref("BusinessEntityRevision", "store-1"), investigationProfileRef: ref("InvestigationProfileRevision", "profile-1"), scopeRef: ref("InvestigationScopeRevision", "scope-1"), schedulePolicyRef: null, createdBy: "user-1", createdAt: "2026-08-26T08:00:00Z" }, lifecycle: "DIAGNOSIS", control: "RUNNING", pendingRequirementRef: null, uncertainCommand: null, runtime: { bindingStatus: "bound", taskId: "task-1", planRef: ref("PlanRevision", "plan-1"), taskRunRef: { resourceType: "TaskRun", resourceId: "task-run-1", version: 3 }, taskRunStatus: "running", checkpoint: { checkpointId: "checkpoint-1", sequence: 1, stepKey: "diagnosis", stateHash: "a".repeat(64), createdAt: "2026-08-26T08:09:00Z" }, stages: [{ stageId: "portrait", title: "经营画像", status: "completed", stepRunId: "step-1", attempt: 1 }, { stageId: "diagnosis", title: "问题与机会", status: "running", stepRunId: "step-2", attempt: 1 }, { stageId: "solution-design", title: "方案设计", status: "not_started", stepRunId: null, attempt: null }], completed: 1, total: 3, currentStageId: "diagnosis" }, currentWorkspace: { stageId: "diagnosis", title: "问题与机会", question: "哪些问题与机会被证据支持，哪些替代解释仍需保留？", status: "running", responsibilitySlotIds: ["slot-diagnosis"], assigneeRefs: [resourceRef("AgentInstance", "data-advisor")], inputRefs: [resourceRef("EvidenceBundleRevision", "evidence-1")], outputRefs: [], areas: [{ area: "known", title: "已知与可回链输入", status: "reference_only", summary: "仅确认存在可回链输入；其内容尚不能自动声称为经营事实。", resourceRefs: [resourceRef("EvidenceBundleRevision", "evidence-1")], exactRefs: [] }, { area: "unknown", title: "未知与缺口", status: "present", summary: "当前阶段运行中，未形成专门权威的内容仍保持未知。", resourceRefs: [], exactRefs: [] }, { area: "assumption", title: "关键假设", status: "unknown", summary: "尚无专门的假设 authority。", resourceRefs: [], exactRefs: [] }, { area: "counter_evidence", title: "反证与替代解释", status: "unknown", summary: "尚无专门的反证 authority。", resourceRefs: [], exactRefs: [] }], nonClaims: ["可回链输入不等于已确认经营事实。", "当前阶段状态不代表方案已执行。", "不展示模型私有过程。"] }, artifacts: ["BusinessDossierRevision", "ProblemMapRevision", "SolutionSetRevision", "DecisionReportRevision"].map((artifactType) => ({ artifactType, status: "missing", artifactRef: null, bindingId: null, bindingHash: null, selectionRevision: null, dataCutoff: null, lineageRef: null })) };

describe("ecommerceInvestigation strict parser", () => {
  it("解析 tenant-scoped Case 与 Run canonical 列表", () => {
    expect(parseInvestigationCaseList({ tenant, items: [caseItem], count: 1 }, tenant).items[0]?.channelRef.resourceId).toBe("private-mall");
    expect(parseInvestigationRunList({ tenant, items: [runItem], count: 1 }, "case-1", tenant).items[0]?.state.control).toBe("RUNNING");
  });
  it("拒绝未知字段、非法 hash、count 与 tenant 漂移", () => {
    expect(() => parseInvestigationCaseList({ tenant, items: [caseItem], count: 1, tenantOverride: true })).toThrow(/字段漂移/);
    expect(() => parseInvestigationCaseList({ tenant, items: [{ ...caseItem, contentHash: "sha256:bad" }], count: 1 })).toThrow(/contentHash/);
    expect(() => parseInvestigationCaseList({ tenant, items: [caseItem], count: 0 })).toThrow(/不守恒/);
    expect(() => parseInvestigationCaseList({ tenant, items: [caseItem], count: 1 }, { orgId: "dev-org", projectId: "dev-project" })).toThrow(/tenant 漂移/);
  });
  it("拒绝 Run 跨 Case、重复 ID 与状态 revision 漂移", () => {
    expect(() => parseInvestigationRunList({ tenant, items: [runItem], count: 1 }, "other-case")).toThrow(/caseRef 漂移/);
    expect(() => parseInvestigationRunList({ tenant, items: [runItem, runItem], count: 2 }, "case-1")).toThrow(/identity 不守恒/);
    expect(() => parseInvestigationRunList({ tenant, items: [{ ...runItem, state: { ...runItem.state, eventSequence: 2 } }], count: 1 }, "case-1")).toThrow(/eventSequence/);
  });
  it("解析服务端 StageRail 并拒绝进度、顺序与 Run identity 漂移", () => {
    const parsed = parseInvestigationWorkbenchView(view, "run-1", tenant);
    expect(parsed.runtime.completed).toBe(1);
    expect(parsed.currentWorkspace.areas.map((item) => item.area)).toEqual(["known", "unknown", "assumption", "counter_evidence"]);
    expect(parsed.currentWorkspace.inputRefs[0]?.resourceId).toBe("evidence-1");
    expect(() => parseInvestigationWorkbenchView({ ...view, runtime: { ...view.runtime, completed: 2 } }, "run-1")).toThrow(/进度不守恒/);
    expect(() => parseInvestigationWorkbenchView({ ...view, runtime: { ...view.runtime, stages: [...view.runtime.stages].reverse() } }, "run-1")).toThrow(/顺序或标题/);
    expect(() => parseInvestigationWorkbenchView(view, "other-run")).toThrow(/Run identity/);
  });
  it("拒绝工作区未知字段、重复 ref 与四区错序", () => {
    expect(() => parseInvestigationWorkbenchView({ ...view, currentWorkspace: { ...view.currentWorkspace, reasoningChain: "private" } }, "run-1")).toThrow(/字段漂移/);
    expect(() => parseInvestigationWorkbenchView({ ...view, currentWorkspace: { ...view.currentWorkspace, inputRefs: [resourceRef("EvidenceBundleRevision", "evidence-1"), resourceRef("EvidenceBundleRevision", "evidence-1")] } }, "run-1")).toThrow(/必须唯一/);
    expect(() => parseInvestigationWorkbenchView({ ...view, currentWorkspace: { ...view.currentWorkspace, areas: [...view.currentWorkspace.areas].reverse() } }, "run-1")).toThrow(/顺序漂移/);
  });
});
