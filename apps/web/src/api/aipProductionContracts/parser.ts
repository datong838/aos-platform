import type { EvidenceBundleListResponse, EvidenceBundleRevision, ExactRevisionRef, ResourceRef, TaskBriefListResponse, TaskBriefRevision, Tenant } from "./contracts";

function object(value: unknown, label: string): Record<string, unknown> { if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} 必须是对象`); return value as Record<string, unknown>; }
function string(value: unknown, label: string): string { if (typeof value !== "string" || !value) throw new Error(`${label} 必须是非空字符串`); return value; }
function number(value: unknown, label: string): number { if (typeof value !== "number" || !Number.isInteger(value) || value < 0) throw new Error(`${label} 必须是非负整数`); return value; }
function sha(value: unknown, label: string): string { const result=string(value,label); if (!/^[0-9a-f]{64}$/.test(result)) throw new Error(`${label} 非 SHA-256`); return result; }
function array(value: unknown, label: string): unknown[] { if (!Array.isArray(value)) throw new Error(`${label} 必须是数组`); return value; }
function tenant(value: unknown): Tenant { const raw=object(value,"tenant"); return {orgId:string(raw.orgId,"tenant.orgId"),projectId:string(raw.projectId,"tenant.projectId")}; }
function resource(value: unknown, label: string): ResourceRef { const raw=object(value,label); const revision=raw.revision; if (revision!==null && typeof revision!=="string") throw new Error(`${label}.revision 必须是字符串或 null`); return {resourceType:string(raw.resourceType,`${label}.resourceType`),resourceId:string(raw.resourceId,`${label}.resourceId`),revision,authority:string(raw.authority,`${label}.authority`)}; }
function exact(value: unknown, label: string): ExactRevisionRef { const raw=object(value,label); const revision=number(raw.revision,`${label}.revision`); if (revision<1) throw new Error(`${label}.revision 必须大于 0`); return {resourceType:string(raw.resourceType,`${label}.resourceType`),resourceId:string(raw.resourceId,`${label}.resourceId`),revision,contentHash:sha(raw.contentHash,`${label}.contentHash`)}; }
function records(value: unknown, label: string): Record<string, unknown>[] { return array(value,label).map((item,index)=>object(item,`${label}[${index}]`)); }

export function parseTaskBrief(value: unknown): TaskBriefRevision {
  const raw=object(value,"TaskBriefRevision"); const lifecycle=string(raw.lifecycle,"lifecycle") as TaskBriefRevision["lifecycle"];
  if (!["draft","frozen","withdrawn","superseded"].includes(lifecycle)) throw new Error("lifecycle 非法");
  const revision=number(raw.revision,"revision"), version=number(raw.version,"version"); if (revision<1||version<1) throw new Error("revision/version 必须大于 0");
  return {tenant:tenant(raw.tenant),briefId:string(raw.briefId,"briefId"),taskId:string(raw.taskId,"taskId"),revision,version,briefType:string(raw.briefType,"briefType"),schemaRef:resource(raw.schemaRef,"schemaRef"),spec:object(raw.spec,"spec"),contentHash:sha(raw.contentHash,"contentHash"),lifecycle,createdBy:string(raw.createdBy,"createdBy"),createdAt:string(raw.createdAt,"createdAt")};
}

export function parseBriefList(value: unknown): TaskBriefListResponse { const raw=object(value,"TaskBriefListResponse"), items=array(raw.items,"items").map(parseTaskBrief), count=number(raw.count,"count"); if(count!==items.length) throw new Error("Brief count 与 items 不一致"); return {tenant:tenant(raw.tenant),items,count}; }

function parseBundle(value: unknown): EvidenceBundleRevision {
  const raw=object(value,"EvidenceBundleRevision"), coverage=string(raw.coverage,"coverage") as EvidenceBundleRevision["coverage"], freshness=string(raw.freshness,"freshness") as EvidenceBundleRevision["freshness"];
  if(!["complete","partial","blocked","unknown"].includes(coverage)||!["fresh","stale","blocked","unknown"].includes(freshness)||raw.lifecycle!=="frozen") throw new Error("EvidenceBundle 状态非法");
  return {tenant:tenant(raw.tenant),bundleId:string(raw.bundleId,"bundleId"),revision:number(raw.revision,"revision"),briefRef:exact(raw.briefRef,"briefRef"),subjectRefs:array(raw.subjectRefs,"subjectRefs").map((item,index)=>resource(item,`subjectRefs[${index}]`)),cutoffAt:string(raw.cutoffAt,"cutoffAt"),itemRefs:array(raw.itemRefs,"itemRefs").map((item,index)=>exact(item,`itemRefs[${index}]`)),coverage,missing:records(raw.missing,"missing"),conflicts:records(raw.conflicts,"conflicts"),uncertainties:records(raw.uncertainties,"uncertainties"),freshness,marking:array(raw.marking,"marking").map((item,index)=>string(item,`marking[${index}]`)),licenseSummary:object(raw.licenseSummary,"licenseSummary"),contentHash:sha(raw.contentHash,"contentHash"),lifecycle:"frozen",createdBy:string(raw.createdBy,"createdBy"),createdAt:string(raw.createdAt,"createdAt")};
}

export function parseBundleList(value: unknown): EvidenceBundleListResponse { const raw=object(value,"EvidenceBundleListResponse"), items=array(raw.items,"items").map(parseBundle), count=number(raw.count,"count"); if(count!==items.length) throw new Error("Bundle count 与 items 不一致"); return {tenant:tenant(raw.tenant),items,count}; }
