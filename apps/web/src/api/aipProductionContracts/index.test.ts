import { beforeEach, describe, expect, it, vi } from "vitest";

const transport = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn() }));
vi.mock("../client", () => transport);

import { aipProductionContracts } from "./index";

const tenant={orgId:"org-org",projectId:"dev-project"},hash="a".repeat(64);
const exact=(resourceType:string,resourceId:string)=>({resourceType,resourceId,revision:1,contentHash:hash});

describe("W2-C production contract SDK",()=>{
  beforeEach(()=>{transport.apiGet.mockReset();transport.apiPost.mockReset();});
  it("读取 Stage、Artifact Relation 与 Review authority",async()=>{
    transport.apiGet
      .mockResolvedValueOnce({tenant,items:[],count:0})
      .mockResolvedValueOnce({tenant,items:[],count:0})
      .mockResolvedValueOnce({tenant,items:[],count:0});
    await aipProductionContracts.listStageTemplates();
    await aipProductionContracts.listArtifactRelations();
    await aipProductionContracts.listReviewIssues();
    expect(transport.apiGet.mock.calls.map(call=>call[0])).toEqual([
      "/v1/aip/production-contracts/stage-templates",
      "/v1/aip/production-contracts/artifact-relations",
      "/v1/aip/production-contracts/review-issues",
    ]);
  });
  it("编译只 POST canonical Plan 请求并携带幂等键",async()=>{
    const input={taskId:"task-1",expectedTaskVersion:2,templateRevision:1,templateContentHash:hash,responsibilityPlanRef:exact("ResponsibilityPlanRevision","plan-1"),profile:"standard"};
    transport.apiPost.mockResolvedValue({tenant,taskId:"task-1",templateRef:exact("StageTemplateRevision","stage-1"),responsibilityPlanRef:input.responsibilityPlanRef,planRef:exact("PlanRevision","plan-revision-1"),compilerVersion:"w2c.v1",applicableStageIds:["analysis"],notApplicableStageIds:[],createdAt:"2026-08-14T00:00:00Z"});
    const result=await aipProductionContracts.compileStageTemplate("stage-1",input,"compile-1");
    expect(result.planRef.resourceId).toBe("plan-revision-1");
    expect(transport.apiPost).toHaveBeenCalledWith("/v1/aip/production-contracts/stage-templates/stage-1/compile",input,{"Idempotency-Key":"compile-1"});
  });
  it("退回 Review 只发送 queued attempt 意图",async()=>{
    const input={expectedVersion:1,runId:"run-1",targetStage:"draft",reason:"修订",attemptIdempotencyKey:"attempt-1"};
    transport.apiPost.mockResolvedValue({tenant,decisionId:"decision-1",issueId:"issue-1",issueVersion:1,runId:"run-1",stepKey:"draft",stepRunId:"step-run-2",attempt:2,attemptIdempotencyKey:"attempt-1",reason:"修订",decisionHash:hash,actor:"reviewer",createdAt:"2026-08-14T00:00:00Z"});
    const result=await aipProductionContracts.returnReviewIssue("issue-1",input,"return-1");
    expect(result.attempt).toBe(2);
    expect(transport.apiPost).toHaveBeenCalledWith("/v1/aip/production-contracts/review-issues/issue-1/return",input,{"Idempotency-Key":"return-1"});
  });
});
