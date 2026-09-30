import { apiGetAuthoritative, apiPostUnqueued } from './client';

export type BudgetMode = 'preview' | 'decision' | 'revoke';
export type BudgetRef = { mode: BudgetMode; id: string; revision?: number; head?: number };
export type BudgetTarget = { budgetId: string; revision: number; environment: 'development'; currency: 'CNY';
 dailyLimitMinor: number; monthlyLimitMinor: number; alertThresholdPct: number; hardStop: true;
 unknownUsageBehavior: 'block'; effectiveFrom: string; effectiveUntil: string; owner: string;
 overBudgetApprover: string; lifecycle: 'active' };
export type BudgetPreview = { previewId: string; previewHash: string; budgetId: string; targetRevision: number;
 targetHash: string; expectedHeadVersion: number; makerSubject: string; checkerSubject: string;
 externalUsageProven: false; activationEligible: false; target: BudgetTarget; internalLedgerCheckedAt: string; expiresAt: string };
export type BudgetDecision = { decisionId: string; previewId: string; previewHash: string; targetHash: string;
 checkerSubject: string; decision: 'approved' | 'rejected'; activationEligible: false; expiresAt: string };
export type BudgetSource = { ref: BudgetRef; target: BudgetTarget; preview?: BudgetPreview;
 decision?: BudgetDecision; revoked?: boolean };
export type BudgetResult = { status: 'not_attempted' | 'unresolved' | 'conflict' } | { status: 'observed'; id: string };
const BASE = '/v1/aip/budgets';
function object(value: unknown): Record<string, unknown> {
 if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('预算响应不完整');
 return value as Record<string, unknown>;
}
function exact(row: Record<string, unknown>, fields: string[]) {
 if (Object.keys(row).length !== fields.length || fields.some(k=>!(k in row))) throw new Error('预算响应字段不完整');
}
const text = (x: unknown): x is string => typeof x==='string' && x.length>0 && x.length<=200 && x.trim()===x && !/[\u0000-\u001f\u007f]/.test(x);
const positive = (x: unknown): x is number => Number.isSafeInteger(x) && Number(x)>0;
const hash = (x: unknown) => typeof x==='string' && /^[0-9a-f]{64}$/.test(x);
const instant = (x: unknown): x is string => typeof x==='string' && /(Z|[+-]\d\d:\d\d)$/.test(x) && Number.isFinite(Date.parse(x));
function target(value: unknown): BudgetTarget {
 const r=object(value); exact(r,['budgetId','revision','environment','currency','dailyLimitMinor','monthlyLimitMinor','alertThresholdPct','hardStop','unknownUsageBehavior','effectiveFrom','effectiveUntil','owner','overBudgetApprover','lifecycle']);
 if (!text(r.budgetId)||!positive(r.revision)||r.environment!=='development'||r.currency!=='CNY'
   ||!positive(r.dailyLimitMinor)||!positive(r.monthlyLimitMinor)||r.monthlyLimitMinor<r.dailyLimitMinor
   ||!positive(r.alertThresholdPct)||r.alertThresholdPct>100||r.hardStop!==true||r.unknownUsageBehavior!=='block'
   ||!instant(r.effectiveFrom)||!instant(r.effectiveUntil)||Date.parse(r.effectiveUntil)<=Date.parse(r.effectiveFrom)
   ||!text(r.owner)||!text(r.overBudgetApprover)||r.lifecycle!=='active') throw new Error('预算候选内容无效');
 return r as BudgetTarget;
}
function preview(value: unknown): BudgetPreview {
 const r=object(value);exact(r,['previewId','previewHash','budgetId','targetRevision','targetHash','expectedHeadVersion','makerSubject','checkerSubject','externalUsageProven','activationEligible','target','internalLedgerCheckedAt','expiresAt']);
 const t=target(r.target);
 if (!text(r.previewId)||!hash(r.previewHash)||!hash(r.targetHash)||r.budgetId!==t.budgetId||r.targetRevision!==t.revision
   ||!positive(r.expectedHeadVersion)||!text(r.makerSubject)||!text(r.checkerSubject)||r.makerSubject===r.checkerSubject
   ||r.externalUsageProven!==false||r.activationEligible!==false||!instant(r.internalLedgerCheckedAt)||!instant(r.expiresAt)) throw new Error('预算预览来源不一致');
 return {...r,target:t} as BudgetPreview;
}
export function parseBudgetResult(value: unknown, mode: BudgetMode, query: boolean): BudgetResult {
 const r=object(value);
 if (r.status==='observed') {
  const id=mode==='preview'?'previewId':mode==='decision'?'decisionId':'revocationId';
  exact(r,mode==='preview'?['status',id,'previewHash','activationEligible']:['status',id,'activationEligible']);
  if (!text(r[id])||r.activationEligible!==false||(mode==='preview'&&!hash(r.previewHash))) throw new Error('预算回执无效');
  return {status:'observed',id:r[id] as string};
 }
 exact(r,['status']);
 if (r.status==='unresolved'||r.status==='conflict'||(query&&r.status==='not_attempted')) return {status:r.status};
 throw new Error('预算请求尚未确认');
}
export async function readBudgetSource(mode: BudgetMode,id: string): Promise<BudgetSource> {
 if(!text(id)||id.length>160)throw new Error('请填写有效预算或审批记录 ID');
 const encoded=encodeURIComponent(id);
 if(mode==='preview') {
  const r=object(await apiGetAuthoritative(BASE+'/activation-candidates/'+encoded));
  exact(r,['headVersion','draftRevision','target','activationEligible']);const t=target(r.target);
  if(r.activationEligible!==false||!positive(r.headVersion)||!positive(r.draftRevision)||t.revision!==r.draftRevision+1||t.budgetId!==id)throw new Error('当前草稿来源不一致');
  return {ref:{mode,id,revision:t.revision,head:r.headVersion},target:t};
 }
 if(mode==='decision') {
  const p=preview(await apiGetAuthoritative(BASE+'/activation-previews/'+encoded));
  if(p.previewId!==id)throw new Error('原预览引用不一致');
  return {ref:{mode,id},target:p.target,preview:p};
 }
 const r=object(await apiGetAuthoritative(BASE+'/activation-decisions/'+encoded));exact(r,['decision','preview','revoked']);
 const p=preview(r.preview),d=object(r.decision);exact(d,['decisionId','previewId','previewHash','targetHash','checkerSubject','decision','activationEligible','expiresAt']);
 if(d.decisionId!==id||d.previewId!==p.previewId||d.previewHash!==p.previewHash||d.targetHash!==p.targetHash||d.checkerSubject!==p.checkerSubject
   ||!['approved','rejected'].includes(String(d.decision))||d.activationEligible!==false||!instant(d.expiresAt)||typeof r.revoked!=='boolean')throw new Error('原批准引用不一致');
 return {ref:{mode,id},target:p.target,preview:p,decision:d as BudgetDecision,revoked:r.revoked};
}
function path(ref: BudgetRef) {
 if(ref.mode==='preview')return BASE+'/activation-previews/intent';
 return BASE+(ref.mode==='decision'?'/activation-previews/':'/activation-decisions/')+encodeURIComponent(ref.id)+(ref.mode==='decision'?'/decision-intent':'/revocation-intent');
}
export async function inquireBudget(ref: BudgetRef): Promise<BudgetResult> {
 const query=ref.mode==='preview'?'?'+new URLSearchParams({budgetId:ref.id,revision:String(ref.revision),headVersion:String(ref.head)}):'';
 return parseBudgetResult(await apiGetAuthoritative(path(ref)+query),ref.mode,true);
}
export async function submitBudget(source: BudgetSource, input: {checker:string;decision:string;reason:string}): Promise<BudgetResult> {
 const ref=source.ref;
 const body=ref.mode==='preview'?{target:source.target,checkerSubject:input.checker}:ref.mode==='decision'?{decision:input.decision}:{reason:input.reason};
 return parseBudgetResult(await apiPostUnqueued(path(ref),body,ref.mode==='preview'?{'If-Match':String(ref.head)}:{}),ref.mode,false);
}
export function restoreBudgetReference(search: string): {ref:BudgetRef;attempted:boolean}|null {
 const p=new URLSearchParams(search),mode=p.get('budgetReviewMode'),id=p.get('budgetReviewRef');
 if(!['preview','decision','revoke'].includes(mode??'')||!text(id)||id.length>160)return null;
 for(const k of ['budgetReviewMode','budgetReviewRef','budgetReviewRevision','budgetReviewHead','budgetAttempted'])if(p.getAll(k).length>1)return null;
 const ref:BudgetRef={mode:mode as BudgetMode,id};
 if(mode==='preview') {
  const rev=p.get('budgetReviewRevision')??'',head=p.get('budgetReviewHead')??'';
  if(!/^[1-9]\d*$/.test(rev)||!positive(Number(rev))||Number(rev)<2||!/^[1-9]\d*$/.test(head)||!positive(Number(head)))return null;
  ref.revision=Number(rev);ref.head=Number(head);
 }
 return {ref,attempted:p.get('budgetAttempted')==='1'};
}
export function saveBudgetReference(ref: BudgetRef, attempted: boolean) {
 const url=new URL(window.location.href);
 for(const key of ['budgetReviewMode','budgetReviewRef','budgetReviewRevision','budgetReviewHead','budgetAttempted'])url.searchParams.delete(key);
 url.searchParams.set('budgetReviewMode',ref.mode);url.searchParams.set('budgetReviewRef',ref.id);
 if(ref.mode==='preview'){url.searchParams.set('budgetReviewRevision',String(ref.revision));url.searchParams.set('budgetReviewHead',String(ref.head));}
 if(attempted)url.searchParams.set('budgetAttempted','1');
 window.history.replaceState(window.history.state,'',url);
}
