import { describe, expect, it, vi } from "vitest";
import { EcommerceInvestigationClient } from "./client";

const tenant = { orgId: "org-org", projectId: "dev-project" };
const hash = `sha256:${"a".repeat(64)}`; const ref = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash: hash });
describe("EcommerceInvestigationClient", () => {
  it("只发出 canonical Case/Run GET 且不提交 tenant", async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ tenant, items: [], count: 0 }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = new EcommerceInvestigationClient({ fetch, getBaseUrl: () => "http://aos.test", getAuthHeaders: () => ({ Authorization: "Bearer test" }) });
    await client.listCases(); await client.listRuns("case:1");
    expect(fetch).toHaveBeenNthCalledWith(1, "http://aos.test/v1/ecommerce/investigations/cases?limit=200", expect.objectContaining({ method: "GET" }));
    expect(fetch).toHaveBeenNthCalledWith(2, "http://aos.test/v1/ecommerce/investigations/cases/case%3A1/runs?limit=200", expect.objectContaining({ method: "GET" }));
    expect(JSON.stringify(fetch.mock.calls)).not.toContain("org-org");
  });
  it("在网络前拒绝非法 Case ID", async () => {
    const fetch = vi.fn(); const client = new EcommerceInvestigationClient({ fetch });
    await expect(client.listRuns("../other")).rejects.toThrow(/caseId 无效/); expect(fetch).not.toHaveBeenCalled();
  });
  it("只用 GET 读取单个 Run 的服务端 Workbench projection", async () => {
    const payload = { schemaVersion: "aos.ecommerce.business-investigation-workbench-view/v2", tenant, projectionHash: hash, sourceWatermark: { caseRevision: 1, runVersion: 1, stateVersion: 1, bindingHashes: [], runtimeHash: null, contentHash: hash }, observedAt: "2026-08-26T08:10:00Z", caseRef: ref("BusinessInvestigationCaseRevision", "case-1"), runRef: ref("BusinessInvestigationRun", "run:1"), stateRef: ref("BusinessInvestigationRunStateRevision", "run:1"), caseEnvelope: { title: "首次分析", analysisType: "initial_store_analysis", lifecycle: "ACTIVE", channelRef: ref("ChannelRevision", "private-mall"), businessEntityRef: ref("BusinessEntityRevision", "store-1"), investigationProfileRef: ref("InvestigationProfileRevision", "profile-1"), scopeRef: ref("InvestigationScopeRevision", "scope-1"), schedulePolicyRef: null, createdBy: "user-1", createdAt: "2026-08-26T08:00:00Z" }, lifecycle: "PREPARING", control: "RUNNING", pendingRequirementRef: null, uncertainCommand: null, runtime: { bindingStatus: "unbound", taskId: null, planRef: null, taskRunRef: null, taskRunStatus: null, checkpoint: null, stages: [{ stageId: "portrait", title: "经营画像", status: "not_started", stepRunId: null, attempt: null }, { stageId: "diagnosis", title: "问题与机会", status: "not_started", stepRunId: null, attempt: null }, { stageId: "solution-design", title: "方案设计", status: "not_started", stepRunId: null, attempt: null }], completed: 0, total: 3, currentStageId: null }, artifacts: ["BusinessDossierRevision", "ProblemMapRevision", "SolutionSetRevision", "DecisionReportRevision"].map((artifactType) => ({ artifactType, status: "missing", artifactRef: null, bindingId: null, bindingHash: null, selectionRevision: null, dataCutoff: null, lineageRef: null })) };
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } })); const client = new EcommerceInvestigationClient({ fetch, getBaseUrl: () => "http://aos.test", getAuthHeaders: () => ({}) });
    await expect(client.getRunView("run:1")).resolves.toMatchObject({ runtime: { bindingStatus: "unbound", total: 3 } }); expect(fetch).toHaveBeenCalledWith("http://aos.test/v1/ecommerce/investigations/runs/run%3A1/view", expect.objectContaining({ method: "GET" }));
  });
});
