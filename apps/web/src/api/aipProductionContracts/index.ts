import { apiGet, apiPost } from "../client";
import type { CompileStageTemplateInput, CreateArtifactRelationInput, CreateEvalContractInput, CreateResponsibilityPlanInput, CreateReviewIssueInput, CreateStageTemplateInput, CreateTaskBriefInput, ResolveReviewIssueInput, ReturnReviewIssueInput, ReviseEvalContractInput, ReviseResponsibilityPlanInput, ReviseStageTemplateInput } from "./contracts";
import { parseArtifactRelation, parseArtifactRelationList, parseBriefList, parseBundleList, parseEvalContract, parseEvalContractList, parseResponsibilityPlan, parseResponsibilityPlanList, parseReturnDecision, parseReviewIssue, parseReviewIssueList, parseStageCompilation, parseStageTemplate, parseStageTemplateList, parseTaskBrief } from "./parser";

const ROOT="/v1/aip/production-contracts";
function keyHeaders(key:string){if(!key.trim())throw new Error("Idempotency-Key 不能为空");return{"Idempotency-Key":key};}
export const aipProductionContracts={
  async listBriefs(){return parseBriefList(await apiGet<unknown>(`${ROOT}/task-briefs`));},
  async listBundles(){return parseBundleList(await apiGet<unknown>(`${ROOT}/evidence-bundles`));},
  async createBrief(input:CreateTaskBriefInput,key:string){return parseTaskBrief(await apiPost<unknown>(`${ROOT}/task-briefs`,input,keyHeaders(key)));},
  async freezeBrief(briefId:string,expectedVersion:number,key:string){return parseTaskBrief(await apiPost<unknown>(`${ROOT}/task-briefs/${encodeURIComponent(briefId)}/freeze`,{expectedVersion},keyHeaders(key)));},
  async listEvalContracts(){return parseEvalContractList(await apiGet<unknown>(`${ROOT}/eval-contracts`));},
  async getEvalContract(contractId:string,revision?:number){return parseEvalContract(await apiGet<unknown>(`${ROOT}/eval-contracts/${encodeURIComponent(contractId)}${revision?`?revision=${revision}`:""}`));},
  async createEvalContract(input:CreateEvalContractInput,key:string){return parseEvalContract(await apiPost<unknown>(`${ROOT}/eval-contracts`,input,keyHeaders(key)));},
  async reviseEvalContract(contractId:string,input:ReviseEvalContractInput,key:string){return parseEvalContract(await apiPost<unknown>(`${ROOT}/eval-contracts/${encodeURIComponent(contractId)}/revisions`,input,keyHeaders(key)));},
  async freezeEvalContract(contractId:string,expectedVersion:number,key:string){return parseEvalContract(await apiPost<unknown>(`${ROOT}/eval-contracts/${encodeURIComponent(contractId)}/freeze`,{expectedVersion},keyHeaders(key)));},
  async listResponsibilityPlans(){return parseResponsibilityPlanList(await apiGet<unknown>(`${ROOT}/responsibility-plans`));},
  async getResponsibilityPlan(planId:string,revision?:number){return parseResponsibilityPlan(await apiGet<unknown>(`${ROOT}/responsibility-plans/${encodeURIComponent(planId)}${revision?`?revision=${revision}`:""}`));},
  async createResponsibilityPlan(input:CreateResponsibilityPlanInput,key:string){return parseResponsibilityPlan(await apiPost<unknown>(`${ROOT}/responsibility-plans`,input,keyHeaders(key)));},
  async reviseResponsibilityPlan(planId:string,input:ReviseResponsibilityPlanInput,key:string){return parseResponsibilityPlan(await apiPost<unknown>(`${ROOT}/responsibility-plans/${encodeURIComponent(planId)}/revisions`,input,keyHeaders(key)));},
  async freezeResponsibilityPlan(planId:string,expectedVersion:number,key:string){return parseResponsibilityPlan(await apiPost<unknown>(`${ROOT}/responsibility-plans/${encodeURIComponent(planId)}/freeze`,{expectedVersion},keyHeaders(key)));},
  async listStageTemplates(){return parseStageTemplateList(await apiGet<unknown>(`${ROOT}/stage-templates`));},
  async getStageTemplate(templateId:string,revision?:number){return parseStageTemplate(await apiGet<unknown>(`${ROOT}/stage-templates/${encodeURIComponent(templateId)}${revision?`?revision=${revision}`:""}`));},
  async createStageTemplate(input:CreateStageTemplateInput,key:string){return parseStageTemplate(await apiPost<unknown>(`${ROOT}/stage-templates`,input,keyHeaders(key)));},
  async reviseStageTemplate(templateId:string,input:ReviseStageTemplateInput,key:string){return parseStageTemplate(await apiPost<unknown>(`${ROOT}/stage-templates/${encodeURIComponent(templateId)}/revisions`,input,keyHeaders(key)));},
  async freezeStageTemplate(templateId:string,expectedVersion:number,key:string){return parseStageTemplate(await apiPost<unknown>(`${ROOT}/stage-templates/${encodeURIComponent(templateId)}/freeze`,{expectedVersion},keyHeaders(key)));},
  async compileStageTemplate(templateId:string,input:CompileStageTemplateInput,key:string){return parseStageCompilation(await apiPost<unknown>(`${ROOT}/stage-templates/${encodeURIComponent(templateId)}/compile`,input,keyHeaders(key)));},
  async listArtifactRelations(){return parseArtifactRelationList(await apiGet<unknown>(`${ROOT}/artifact-relations`));},
  async createArtifactRelation(input:CreateArtifactRelationInput,key:string){return parseArtifactRelation(await apiPost<unknown>(`${ROOT}/artifact-relations`,input,keyHeaders(key)));},
  async listReviewIssues(){return parseReviewIssueList(await apiGet<unknown>(`${ROOT}/review-issues`));},
  async getReviewIssue(issueId:string){return parseReviewIssue(await apiGet<unknown>(`${ROOT}/review-issues/${encodeURIComponent(issueId)}`));},
  async createReviewIssue(input:CreateReviewIssueInput,key:string){return parseReviewIssue(await apiPost<unknown>(`${ROOT}/review-issues`,input,keyHeaders(key)));},
  async resolveReviewIssue(issueId:string,input:ResolveReviewIssueInput,key:string){return parseReviewIssue(await apiPost<unknown>(`${ROOT}/review-issues/${encodeURIComponent(issueId)}/resolve`,input,keyHeaders(key)));},
  async returnReviewIssue(issueId:string,input:ReturnReviewIssueInput,key:string){return parseReturnDecision(await apiPost<unknown>(`${ROOT}/review-issues/${encodeURIComponent(issueId)}/return`,input,keyHeaders(key)));},
};
export * from "./contracts";
