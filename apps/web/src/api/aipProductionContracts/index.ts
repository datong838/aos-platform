import { apiGet, apiPost } from "../client";
import type { CreateTaskBriefInput } from "./contracts";
import { parseBriefList, parseBundleList, parseTaskBrief } from "./parser";

const ROOT="/v1/aip/production-contracts";
export const aipProductionContracts={
  async listBriefs(){return parseBriefList(await apiGet<unknown>(`${ROOT}/task-briefs`));},
  async listBundles(){return parseBundleList(await apiGet<unknown>(`${ROOT}/evidence-bundles`));},
  async createBrief(input:CreateTaskBriefInput,key:string){if(!key.trim()) throw new Error("Idempotency-Key 不能为空");return parseTaskBrief(await apiPost<unknown>(`${ROOT}/task-briefs`,input,{"Idempotency-Key":key}));},
  async freezeBrief(briefId:string,expectedVersion:number,key:string){if(!key.trim()) throw new Error("Idempotency-Key 不能为空");return parseTaskBrief(await apiPost<unknown>(`${ROOT}/task-briefs/${encodeURIComponent(briefId)}/freeze`,{expectedVersion},{"Idempotency-Key":key}));},
};
export * from "./contracts";
