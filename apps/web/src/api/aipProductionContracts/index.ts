import { apiGet, apiPost } from "../client";
import type { CreateEvalContractInput, CreateResponsibilityPlanInput, CreateTaskBriefInput, ReviseEvalContractInput, ReviseResponsibilityPlanInput } from "./contracts";
import { parseBriefList, parseBundleList, parseEvalContract, parseEvalContractList, parseResponsibilityPlan, parseResponsibilityPlanList, parseTaskBrief } from "./parser";

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
};
export * from "./contracts";
