import { apiGetAuthoritative, apiPostUnqueued } from './client';
import { getTenant } from './tenant';
import { parseBudgetTarget, type BudgetTarget } from './aipBudgetActivation';

export type CostRef={id:string;operation:'decide'|'revoke'|'consume'|'configure'};
type ProviderRef={assetType:'ProviderInstanceRevision';assetId:string;revision:number;contentHash:string};
type Proposal={schemaVersion:1;tenant:{orgId:string;projectId:string};target:BudgetTarget;draftRevision:number;expectedHeadVersion:number;
 makerSubject:string;checkerSubject:string;basis:{kind:'development_risk_proposal';provider:ProviderRef;providerModelId:string;perRequestRiskMinor:number;totalRiskMinor:number;maxRequests:number};
 accounts:{daily:string;pilot:string};currency:'CNY';period:{start:string;end:string}};
export type CostReview={proposal:{proposalId:string;proposalHash:string;proposal:Proposal;status:'proposed';sourceVerification:'pending';activationEligible:false;createdAt:string;expiresAt:string};
 decision:null|{decisionId:string;proposalId:string;proposalHash:string;checkerSubject:string;decision:'approved'|'rejected';expiresAt:string;activationEligible:false};
 revocation:null|{revocationId:string;decisionId:string;actorSubject:string;reason:string;createdAt:string}};
export type CostAssetRef={assetType:string;assetId:string;revision:number;contentHash:string};
export type CostResult={status:'not_attempted'|'unresolved'|'conflict'}|{status:'observed';id:string;budgetRef?:CostAssetRef;priceRef?:CostAssetRef;policyRef?:CostAssetRef};
const base='/v1/aip/budgets/cost-proposals/';
function row(x:unknown,keys:string[]):Record<string,unknown>{
 if(!x||typeof x!=='object'||Array.isArray(x)||Object.keys(x).length!==keys.length||keys.some(k=>!(k in x)))throw new Error('费用审核响应字段不完整');
 return x as Record<string,unknown>;
}
function text(x:unknown,max=200):x is string{return typeof x==='string'&&x.length>0&&x.length<=max&&x.trim()===x&&!/[\u0000-\u001f\u007f]/.test(x);}
const pos=(x:unknown):x is number=>Number.isSafeInteger(x)&&Number(x)>0;
const hash=(x:unknown)=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x);
const instant=(x:unknown):x is string=>typeof x==='string'&&/(Z|[+-]\d\d:\d\d)$/.test(x)&&Number.isFinite(Date.parse(x));
function requireValue(ok:unknown){if(!ok)throw new Error('费用审核来源或关联记录不一致');}
export function parseCostReview(value:unknown,id:string):CostReview{
 const v=row(value,['proposal','decision','revocation']);
 const s=row(v.proposal,['proposalId','proposalHash','proposal','status','sourceVerification','activationEligible','createdAt','expiresAt']);
 const p=row(s.proposal,['schemaVersion','tenant','target','draftRevision','expectedHeadVersion','makerSubject','checkerSubject','basis','accounts','currency','period']);
 const t=parseBudgetTarget(p.target),tenant=row(p.tenant,['orgId','projectId']),current=getTenant();
 const b=row(p.basis,['kind','provider','providerModelId','perRequestRiskMinor','totalRiskMinor','maxRequests']);
 const provider=row(b.provider,['assetType','assetId','revision','contentHash']),accounts=row(p.accounts,['daily','pilot']),period=row(p.period,['start','end']);
 requireValue(s.proposalId===id&&text(id,160)&&hash(s.proposalHash)&&s.status==='proposed'&&s.sourceVerification==='pending'&&s.activationEligible===false);
 requireValue(p.schemaVersion===1&&tenant.orgId==='org-org'&&tenant.projectId==='dev-project'&&tenant.orgId===current.orgId&&tenant.projectId===current.projectId
  &&pos(p.draftRevision)&&p.draftRevision+1===t.revision&&pos(p.expectedHeadVersion)&&text(p.makerSubject)&&text(p.checkerSubject)&&p.makerSubject!==p.checkerSubject);
 requireValue(b.kind==='development_risk_proposal'&&provider.assetType==='ProviderInstanceRevision'&&text(provider.assetId)&&pos(provider.revision)&&hash(provider.contentHash)&&text(b.providerModelId,240));
 requireValue(pos(b.perRequestRiskMinor)&&pos(b.totalRiskMinor)&&pos(b.maxRequests)&&Number.isSafeInteger(Number(b.perRequestRiskMinor)*Number(b.maxRequests))
  &&Number(b.perRequestRiskMinor)*Number(b.maxRequests)<=Number(b.totalRiskMinor)&&Number(b.perRequestRiskMinor)<=t.dailyLimitMinor&&Number(b.totalRiskMinor)<=t.monthlyLimitMinor);
 requireValue(accounts.daily===t.budgetId+':daily'&&accounts.pilot===t.budgetId+':pilot'&&p.currency==='CNY'&&period.start===t.effectiveFrom&&period.end===t.effectiveUntil);
 requireValue(instant(s.createdAt)&&instant(s.expiresAt)&&Date.parse(s.createdAt as string)>=Date.parse(t.effectiveFrom)
  &&Date.parse(s.createdAt as string)<Date.parse(t.effectiveUntil)&&Date.parse(s.expiresAt as string)===Math.min(Date.parse(s.createdAt as string)+1800000,Date.parse(t.effectiveUntil)));
 if(v.decision!==null){
  const d=row(v.decision,['decisionId','proposalId','proposalHash','checkerSubject','decision','expiresAt','activationEligible']);
  requireValue(text(d.decisionId)&&d.proposalId===id&&d.proposalHash===s.proposalHash&&d.checkerSubject===p.checkerSubject
   &&['approved','rejected'].includes(String(d.decision))&&d.activationEligible===false&&d.expiresAt===s.expiresAt);
  if(v.revocation!==null){const r=row(v.revocation,['revocationId','decisionId','actorSubject','reason','createdAt']);
   requireValue(d.decision==='approved'&&text(r.revocationId)&&r.decisionId===d.decisionId&&[p.makerSubject,p.checkerSubject].includes(r.actorSubject)&&text(r.reason,500)&&instant(r.createdAt));}
 }else requireValue(v.revocation===null);
 return value as CostReview;
}
export function parseCostResult(value:unknown,ref:CostRef,query:boolean,source?:CostReview,choice?:string,consumed?:CostResult):CostResult{
 const status=(value as {status?:unknown}|null)?.status;
 if(status!=='observed'){row(value,['status']);requireValue(status==='unresolved'||status==='conflict'||(query&&status==='not_attempted'));return {status} as CostResult;}
 if(ref.operation==='configure'){
  const v=row(value,['status','receipt','activationEligible']),r=row(v.receipt,['proposalId','proposalHash','decisionId','budgetRef','priceRef','policyRef','receiptId']);
  requireValue(v.activationEligible===false&&r.proposalId===ref.id&&hash(r.proposalHash)&&text(r.decisionId,160)
   &&typeof r.receiptId==='string'&&/^cost-configuration-[0-9a-f]{64}$/.test(r.receiptId));
  function exact(value:unknown,kind:string):CostAssetRef{const r=row(value,['assetType','assetId','revision','contentHash']);
   requireValue(r.assetType===kind&&text(r.assetId,160)&&pos(r.revision)&&hash(r.contentHash));return r as CostAssetRef;}
  const budgetRef=exact(r.budgetRef,'BudgetRevision'),priceRef=exact(r.priceRef,'ModelPriceSnapshotRevision'),policyRef=exact(r.policyRef,'BudgetPolicyRevision');
  const digest=(r.receiptId as string).slice('cost-configuration-'.length);
  requireValue(priceRef.assetId==='cost-price-'+digest&&policyRef.assetId==='cost-policy-'+digest&&priceRef.revision===1&&policyRef.revision===1);
  if(source)requireValue(r.proposalHash===source.proposal.proposalHash&&r.decisionId===source.decision?.decisionId
   &&budgetRef.assetId===source.proposal.proposal.target.budgetId&&budgetRef.revision===source.proposal.proposal.target.revision);
  if(consumed){requireValue(consumed.status==='observed'&&consumed.budgetRef
   &&budgetRef.assetId===consumed.budgetRef.assetId&&budgetRef.revision===consumed.budgetRef.revision&&budgetRef.contentHash===consumed.budgetRef.contentHash);}
  return {status:'observed',id:r.receiptId as string,budgetRef,priceRef,policyRef};
 }
 if(ref.operation==='consume'){
  const v=row(value,['status','receipt','activationEligible']),r=row(v.receipt,['resourceType','resourceId','revision','contentHash','proposalId','proposalHash','decisionId','receiptId']);
  requireValue(v.activationEligible===false&&r.resourceType==='BudgetRevision'&&text(r.resourceId,160)&&pos(r.revision)&&hash(r.contentHash)
   &&r.proposalId===ref.id&&hash(r.proposalHash)&&text(r.decisionId,160)&&typeof r.receiptId==='string'&&/^budget-cost-consume-[0-9a-f]{64}$/.test(r.receiptId));
  if(source)requireValue(r.proposalHash===source.proposal.proposalHash&&r.decisionId===source.decision?.decisionId
   &&r.resourceId===source.proposal.proposal.target.budgetId&&r.revision===source.proposal.proposal.target.revision);
  return {status:'observed',id:r.receiptId as string,budgetRef:{assetType:'BudgetRevision',assetId:r.resourceId as string,revision:r.revision as number,contentHash:r.contentHash as string}};
 }
 const v=row(value,['status','result','activationEligible']);requireValue(v.activationEligible===false);
 if(ref.operation==='decide'){
  const r=row(v.result,['decisionId','decision','proposalHash','activationEligible']);
  requireValue(text(r.decisionId)&&['approved','rejected'].includes(String(r.decision))&&hash(r.proposalHash)&&r.activationEligible===false
   &&(!source||r.proposalHash===source.proposal.proposalHash)&&(!choice||r.decision===choice));return {status:'observed',id:r.decisionId as string};
 }
 const r=row(v.result,['revocationId','decisionId','activationEligible']);
 requireValue(text(r.revocationId)&&text(r.decisionId)&&r.activationEligible===false&&(!source||r.decisionId===source.decision?.decisionId));return {status:'observed',id:r.revocationId as string};
}
function path(ref:CostRef){requireValue(text(ref.id,160)&&['decide','revoke','consume','configure'].includes(ref.operation));return base+encodeURIComponent(ref.id)+(ref.operation==='consume'?'/consumption-request':ref.operation==='configure'?'/configuration-request':'/review-requests/'+ref.operation);}
export async function readCostReview(id:string){requireValue(text(id,160));return parseCostReview(await apiGetAuthoritative(base+encodeURIComponent(id)+'/review'),id);}
export async function inquireCost(ref:CostRef,source?:CostReview,consumed?:CostResult){return parseCostResult(await apiGetAuthoritative(path(ref)),ref,true,source,undefined,consumed);}
export async function submitCost(ref:CostRef,source:CostReview,choice:string,reason:string,consumed?:CostResult){
 requireValue(ref.id===source.proposal.proposalId);
 if(ref.operation==='consume'||ref.operation==='configure')requireValue(source.decision?.decision==='approved');
 if(ref.operation==='configure')requireValue(consumed?.status==='observed'&&consumed.budgetRef?.assetType==='BudgetRevision'
  &&consumed.budgetRef.assetId===source.proposal.proposal.target.budgetId&&consumed.budgetRef.revision===source.proposal.proposal.target.revision);
 const body=(ref.operation==='consume'||ref.operation==='configure')?{proposalHash:source.proposal.proposalHash,decisionId:source.decision!.decisionId}:ref.operation==='decide'?{proposalHash:source.proposal.proposalHash,decision:choice}:{proposalHash:source.proposal.proposalHash,reason};
 return parseCostResult(await apiPostUnqueued(path(ref),body,{}),ref,false,source,ref.operation==='decide'?choice:undefined,consumed);
}
const keys=['budgetCostRef','budgetCostOperation','budgetCostAttempted'];
export function restoreCostReference(search:string):{ref:CostRef;attempted:boolean}|null{
 const p=new URLSearchParams(search),id=p.get(keys[0]),operation=p.get(keys[1]);
 if(keys.some(k=>p.getAll(k).length>1)||!text(id,160)||!['decide','revoke','consume','configure'].includes(operation??'')||!['0','1',null].includes(p.get(keys[2])))return null;
 return {ref:{id,operation:operation as CostRef['operation']},attempted:p.get(keys[2])==='1'};
}
export function saveCostReference(ref:CostRef,attempted:boolean){const u=new URL(window.location.href);keys.forEach(k=>u.searchParams.delete(k));u.searchParams.set(keys[0],ref.id);u.searchParams.set(keys[1],ref.operation);if(attempted)u.searchParams.set(keys[2],'1');window.history.replaceState(window.history.state,'',u);}
