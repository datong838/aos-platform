/** Independent initial-window display/command inputs; never a second authority. */
import {apiGetAuthoritative} from './client';
import {getAuthRevision, getTenant, tenantAuthHeaders} from './tenant';
import {getApiBase} from './apiBase';
import type {BudgetTarget} from './aipBudgetActivation';

type Tenant={orgId:'org-org';projectId:'dev-project'};
type Ref<K extends string>={assetType:K;assetId:string;revision:number;contentHash:string};
type Lifecycle='draft'|'active'|'suspended'|'revoked'|'expired';
export type PolicyWindowBudget=Omit<BudgetTarget,'lifecycle'>&{lifecycle:Lifecycle;tenant:Tenant;contentHash:string;createdBy:string;createdAt:string};
type Provider={tenant:Tenant;ref:Ref<'ProviderInstanceRevision'>;lifecycle:Exclude<Lifecycle,'expired'>|'validated'};
type Basis={kind:'development_risk_proposal';provider:Ref<'ProviderInstanceRevision'>;providerModelId:string;
 perRequestRiskMinor:number;totalRiskMinor:number;maxRequests:number};
export type PolicyWindowParent={proposalId:string;proposalHash:string;
 proposal:{schemaVersion:1;tenant:Tenant;target:BudgetTarget;draftRevision:number;expectedHeadVersion:number;
 makerSubject:string;checkerSubject:string;basis:Basis};decisionId:string|null;decision:'approved'|'rejected'|'missing';revoked:boolean};
type Consumption={receiptId:string;requestHash:string;createdBy:string;resultRef:{resourceType:'BudgetRevision';resourceId:string;
 revision:number;contentHash:string;proposalId:string;proposalHash:string;decisionId:string;receiptId:string}};
export type PolicyWindowSource={schemaVersion:'aos.budget-policy-window.review-source/v1';tenant:Tenant;evaluatedAt:string;
 parent:PolicyWindowParent;consumption:Consumption|null;sourceBudget:PolicyWindowBudget|null;currentBudget:PolicyWindowBudget|null;
 currentBudgetHeadVersion:number|null;sourceProvider:Provider|null;currentProvider:Provider|null;state:'observed'|'blocked';blockers:string[];
 approvalVerified:false;activationEligible:false;nativeWriteAllowed:false;runtimeAdmissionAllowed:false;nativeParentVerification:'not-performed'};
export type PolicyWindowProposeCommand={schemaVersion:1;orgId:'org-org';projectId:'dev-project';idempotencyKey:string;
 parentCostProposalId:string;parentCostProposalHash:string;parentCostDecisionId:string;parentConsumptionReceiptId:string;
 expectedBudgetRef:Ref<'BudgetRevision'>;expectedBudgetHeadVersion:number;expectedProviderRef:Ref<'ProviderInstanceRevision'>;
 expectedProviderModelId:string;effectiveFrom:string;effectiveUntil:string};
const HUMAN='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657';
const displayContexts=new WeakMap<object,string>();
const targetKeys=['budgetId','revision','environment','currency','dailyLimitMinor','monthlyLimitMinor','alertThresholdPct',
 'hardStop','unknownUsageBehavior','effectiveFrom','effectiveUntil','owner','overBudgetApprover','lifecycle'];
const blockers=[
 'WINDOW_PARENT_APPROVAL_NOT_OBSERVED','WINDOW_PARENT_REVOKED','WINDOW_PARENT_CONSUMPTION_NOT_OBSERVED',
 'WINDOW_SOURCE_BUDGET_MISSING','WINDOW_SOURCE_BUDGET_CHANGED','WINDOW_SOURCE_BUDGET_NOT_ACTIVE','WINDOW_SOURCE_BUDGET_WINDOW_UNAVAILABLE',
 'WINDOW_CURRENT_BUDGET_MISSING','WINDOW_CURRENT_BUDGET_CHANGED','WINDOW_CURRENT_BUDGET_NOT_ACTIVE','WINDOW_CURRENT_BUDGET_WINDOW_UNAVAILABLE',
 'WINDOW_PARENT_BUDGET_HEAD_CHANGED','WINDOW_SOURCE_PROVIDER_MISSING','WINDOW_SOURCE_PROVIDER_CHANGED',
 'WINDOW_CURRENT_PROVIDER_MISSING','WINDOW_CURRENT_PROVIDER_CHANGED'];
function requireValue(ok:unknown):asserts ok {if(!ok)throw new Error('初始策略来源或窗口不完整，请重新读取并核对');}
function row(value:unknown):Record<string,unknown>{requireValue(value!==null&&typeof value==='object'&&!Array.isArray(value));return value as Record<string,unknown>;}
function exact(value:Record<string,unknown>,fields:string[]){requireValue(Object.keys(value).length===fields.length&&fields.every(k=>Object.hasOwn(value,k)));}
function text(value:unknown,max=200):value is string{return typeof value==='string'&&value.length>0&&Array.from(value).length<=max&&value.trim()===value&&!/[\p{C}\p{Zl}\p{Zp}]/u.test(value);}
const positive=(v:unknown):v is number=>Number.isSafeInteger(v)&&Number(v)>0;
const hash=(v:unknown):v is string=>typeof v==='string'&&/^[0-9a-f]{64}$/.test(v);
function oneOf(v:unknown,allowed:string[]){return typeof v==='string'&&allowed.includes(v);}
function uiContext(){
 const t=getTenant();requireValue(t.orgId==='org-org'&&t.projectId==='dev-project'&&t.subject===HUMAN);
 // Display epoch only: cached subject never proves the server's OIDC identity.
 return JSON.stringify([t.orgId,t.projectId,t.subject,getAuthRevision(),getApiBase()]);
}
function tenant(value:unknown){const t=row(value);exact(t,['orgId','projectId']);requireValue(t.orgId==='org-org'&&t.projectId==='dev-project');}
function ref(value:unknown,kind:string){const r=row(value);exact(r,['assetType','assetId','revision','contentHash']);requireValue(r.assetType===kind&&text(r.assetId)&&positive(r.revision)&&hash(r.contentHash));}

// Microsecond input/display comparison only. No workstation-current-time or
// cryptographic authority is synthesized by this client.
function instant(value:unknown):bigint{
 requireValue(typeof value==='string');
 const m=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/.exec(value);
 requireValue(m);const [,y,mo,d,h,mi,se,fraction,zone]=m;
 requireValue(Number(y)>=1&&Number(mo)>=1&&Number(mo)<=12&&Number(d)>=1&&
  Number(d)<=new Date(Date.UTC(Number(y),Number(mo),0)).getUTCDate()&&Number(h)<24&&Number(mi)<60&&Number(se)<60&&
  (zone==='Z'||(Number(zone.slice(1,3))<24&&Number(zone.slice(4,6))<60)));
 const whole=Date.parse(`${y}-${mo}-${d}T${h}:${mi}:${se}${zone}`);requireValue(Number.isFinite(whole));
 return BigInt(whole)*1000n+BigInt((fraction??'').padEnd(6,'0'));
}
function utcMicros(value:string):string{
 const micro=instant(value),ms=micro>=0n?micro/1000n:-((-micro+999n)/1000n),remaining=micro-ms*1000n;
 const iso=new Date(Number(ms)).toISOString();requireValue(/^\d{4}-/.test(iso)&&Number(iso.slice(0,4))>=1);
 return iso.slice(0,-1)+String(remaining).padStart(3,'0')+'Z';
}
function canonicalBudgetTime(value:string){return utcMicros(value).replace(/\.000000Z$/,'Z');}
function period(t:Record<string,unknown>){requireValue(instant(t.effectiveFrom)<instant(t.effectiveUntil));}
function target(value:unknown,activeOnly:boolean){
 const t=row(value);exact(t,targetKeys);period(t);
 requireValue(text(t.budgetId,160)&&positive(t.revision)&&t.environment==='development'&&t.currency==='CNY'&&
  positive(t.dailyLimitMinor)&&positive(t.monthlyLimitMinor)&&t.monthlyLimitMinor>=t.dailyLimitMinor&&
  positive(t.alertThresholdPct)&&t.alertThresholdPct<=100&&t.hardStop===true&&t.unknownUsageBehavior==='block'&&
  text(t.owner,160)&&text(t.overBudgetApprover,160)&&oneOf(t.lifecycle,activeOnly?['active']:['draft','active','suspended','revoked','expired']));
}
function budget(value:unknown){
 if(value===null)return;const b=row(value);exact(b,[...targetKeys,'tenant','contentHash','createdBy','createdAt']);
 tenant(b.tenant);requireValue(hash(b.contentHash)&&text(b.createdBy));instant(b.createdAt);
 target(Object.fromEntries(targetKeys.map(k=>[k,b[k]])),false);
}
function provider(value:unknown){
 if(value===null)return;const p=row(value);exact(p,['tenant','ref','lifecycle']);tenant(p.tenant);ref(p.ref,'ProviderInstanceRevision');
 requireValue(oneOf(p.lifecycle,['draft','validated','active','suspended','revoked']));
}
function parent(value:unknown,id:string){
 const p=row(value);exact(p,['proposalId','proposalHash','proposal','decisionId','decision','revoked']);
 requireValue(p.proposalId===id&&hash(p.proposalHash)&&oneOf(p.decision,['approved','rejected','missing'])&&
  (p.decisionId===null?p.decision==='missing':text(p.decisionId,240)&&p.decision!=='missing')&&
  typeof p.revoked==='boolean'&&(!p.revoked||p.decision==='approved'));
 const q=row(p.proposal);exact(q,['schemaVersion','tenant','target','draftRevision','expectedHeadVersion','makerSubject','checkerSubject','basis']);tenant(q.tenant);target(q.target,true);
 const t=row(q.target);requireValue(q.schemaVersion===1&&positive(q.draftRevision)&&positive(q.expectedHeadVersion)&&
  BigInt(q.draftRevision)+1n===BigInt(t.revision as number)&&text(q.makerSubject)&&q.checkerSubject===HUMAN&&q.makerSubject!==HUMAN);
 const b=row(q.basis);exact(b,['kind','provider','providerModelId','perRequestRiskMinor','totalRiskMinor','maxRequests']);ref(b.provider,'ProviderInstanceRevision');
 requireValue(b.kind==='development_risk_proposal'&&text(b.providerModelId,240)&&positive(b.perRequestRiskMinor)&&positive(b.totalRiskMinor)&&positive(b.maxRequests)&&
  BigInt(b.perRequestRiskMinor)*BigInt(b.maxRequests)<=BigInt(b.totalRiskMinor)&&b.perRequestRiskMinor<=Number(t.dailyLimitMinor)&&b.totalRiskMinor<=Number(t.monthlyLimitMinor));
}
function consumption(value:unknown,p:PolicyWindowParent){
 if(value===null)return;const r=row(value);exact(r,['receiptId','requestHash','resultRef','createdBy']);
 requireValue(p.decision==='approved'&&hash(r.requestHash)&&r.receiptId==='budget-cost-consume-'+r.requestHash&&r.createdBy===p.proposal.makerSubject);
 const a=row(r.resultRef);exact(a,['resourceType','resourceId','revision','contentHash','proposalId','proposalHash','decisionId','receiptId']);
 requireValue(a.resourceType==='BudgetRevision'&&a.resourceId===p.proposal.target.budgetId&&positive(a.revision)&&a.revision===p.proposal.target.revision&&
  hash(a.contentHash)&&a.proposalId===p.proposalId&&a.proposalHash===p.proposalHash&&a.decisionId===p.decisionId&&a.receiptId===r.receiptId);
}
function same(a:unknown,b:unknown):boolean{
 if(a===b)return true;if(a===null||b===null||typeof a!=='object'||typeof b!=='object')return false;
 if(Array.isArray(a)!==Array.isArray(b))return false;
 const l=a as Record<string,unknown>,r=b as Record<string,unknown>,keys=Object.keys(l);
 return keys.length===Object.keys(r).length&&keys.every(k=>Object.hasOwn(r,k)&&same(l[k],r[k]));
}
function observedReasons(s:PolicyWindowSource){
 const reasons:string[]=[],p=s.parent,q=p.proposal;
 if(p.decision!=='approved')reasons.push('WINDOW_PARENT_APPROVAL_NOT_OBSERVED');
 if(p.revoked)reasons.push('WINDOW_PARENT_REVOKED');
 if(s.consumption===null)reasons.push('WINDOW_PARENT_CONSUMPTION_NOT_OBSERVED');
 const normalizedTarget={...q.target,effectiveFrom:canonicalBudgetTime(q.target.effectiveFrom),effectiveUntil:canonicalBudgetTime(q.target.effectiveUntil)};
 for(const [label,b] of [['SOURCE',s.sourceBudget],['CURRENT',s.currentBudget]] as const){
  if(b===null){reasons.push(`WINDOW_${label}_BUDGET_MISSING`);continue;}
  const body=Object.fromEntries(targetKeys.map(k=>[k,b[k as keyof PolicyWindowBudget]]));
  if(!same(body,normalizedTarget)||(s.consumption!==null&&b.contentHash!==s.consumption.resultRef.contentHash))reasons.push(`WINDOW_${label}_BUDGET_CHANGED`);
  if(b.lifecycle!=='active')reasons.push(`WINDOW_${label}_BUDGET_NOT_ACTIVE`);
  if(!(instant(b.effectiveFrom)<=instant(s.evaluatedAt)&&instant(s.evaluatedAt)<instant(b.effectiveUntil)))reasons.push(`WINDOW_${label}_BUDGET_WINDOW_UNAVAILABLE`);
 }
 if(s.currentBudgetHeadVersion===null||BigInt(s.currentBudgetHeadVersion)!==BigInt(q.expectedHeadVersion)+1n)reasons.push('WINDOW_PARENT_BUDGET_HEAD_CHANGED');
 for(const [label,pv] of [['SOURCE',s.sourceProvider],['CURRENT',s.currentProvider]] as const){
  if(pv===null)reasons.push(`WINDOW_${label}_PROVIDER_MISSING`);
  else if(!same(pv.ref,q.basis.provider)||pv.lifecycle!=='active')reasons.push(`WINDOW_${label}_PROVIDER_CHANGED`);
 }
 return reasons;
}

export function parsePolicyWindowSource(value:unknown,proposalId:string):PolicyWindowSource{
 const context=uiContext();requireValue(text(proposalId,160));
 const snapshot=structuredClone(value),v=row(snapshot);
 exact(v,['schemaVersion','tenant','evaluatedAt','parent','consumption','sourceBudget','currentBudget','currentBudgetHeadVersion',
  'sourceProvider','currentProvider','state','blockers','approvalVerified','activationEligible','nativeWriteAllowed','runtimeAdmissionAllowed','nativeParentVerification']);
 tenant(v.tenant);instant(v.evaluatedAt);parent(v.parent,proposalId);
 requireValue(v.schemaVersion==='aos.budget-policy-window.review-source/v1'&&
  v.approvalVerified===false&&v.activationEligible===false&&v.nativeWriteAllowed===false&&v.runtimeAdmissionAllowed===false&&
  v.nativeParentVerification==='not-performed'&&oneOf(v.state,['observed','blocked'])&&
  (v.currentBudgetHeadVersion===null||positive(v.currentBudgetHeadVersion)));
 budget(v.sourceBudget);budget(v.currentBudget);provider(v.sourceProvider);provider(v.currentProvider);
 consumption(v.consumption,v.parent as PolicyWindowParent);
 requireValue(Array.isArray(v.blockers)&&v.blockers.every(c=>typeof c==='string'&&blockers.includes(c)));
 const list=v.blockers as string[];requireValue(new Set(list).size===list.length&&list.every((c,i)=>i===0||blockers.indexOf(list[i-1])<blockers.indexOf(c)));
 const s=snapshot as PolicyWindowSource,reasons=observedReasons(s);
 // Opaque target-hash drift stays the backend's responsibility. A blocked view
 // may include those extra codes; it can never become an executable permit.
 const opaque=['WINDOW_SOURCE_BUDGET_CHANGED','WINDOW_CURRENT_BUDGET_CHANGED'];
 requireValue(reasons.every(c=>list.includes(c))&&list.every(c=>reasons.includes(c)||opaque.includes(c))&&
  s.state===(list.length?'blocked':'observed'));
 displayContexts.set(s,context);return s;
}

export async function readPolicyWindowSource(proposalId:string):Promise<PolicyWindowSource>{
 const context=uiContext();requireValue(text(proposalId,160));
 const value=await apiGetAuthoritative<unknown>('/v1/aip/budgets/cost-proposals/'+encodeURIComponent(proposalId)+'/policy-window-source');
 requireValue(uiContext()===context);return parsePolicyWindowSource(value,proposalId);
}

/** Explicit claims only. Private native Owner rechecks current facts and rights. */
export function policyWindowProposalCommand(source:PolicyWindowSource,key:string,from:string,until:string):PolicyWindowProposeCommand{
 requireValue(displayContexts.get(source)===uiContext()&&typeof key==='string'&&/^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$/.test(key));
 const s=parsePolicyWindowSource(source,source.parent.proposalId);
 requireValue(s.state==='observed'&&s.currentBudget!==null&&s.currentBudgetHeadVersion!==null&&s.consumption!==null&&s.parent.decisionId!==null);
 const start=instant(from),end=instant(until),budget=s.currentBudget;
 requireValue(instant(budget.effectiveFrom)<=start&&start<end&&end<instant(budget.effectiveUntil)&&instant(s.evaluatedAt)<end);
 return {schemaVersion:1,orgId:'org-org',projectId:'dev-project',idempotencyKey:key,
  parentCostProposalId:s.parent.proposalId,parentCostProposalHash:s.parent.proposalHash,parentCostDecisionId:s.parent.decisionId,
  parentConsumptionReceiptId:s.consumption.receiptId,
  expectedBudgetRef:{assetType:'BudgetRevision',assetId:budget.budgetId,revision:budget.revision,contentHash:budget.contentHash},
  expectedBudgetHeadVersion:s.currentBudgetHeadVersion,expectedProviderRef:structuredClone(s.parent.proposal.basis.provider),
  expectedProviderModelId:s.parent.proposal.basis.providerModelId,effectiveFrom:utcMicros(from),effectiveUntil:utcMicros(until)};
}

// Protected loopback AOS governance API; never a direct Provider/engine call.
export type WindowOperation='propose'|'decide'|'revoke'|'consume';
export type WindowRef={operation:WindowOperation;key:string};
type WindowBase={schemaVersion:1;orgId:'org-org';projectId:'dev-project';idempotencyKey:string};
export type WindowDecisionCommand=WindowBase&{proposalId:string;proposalHash:string;targetPairHash:string;decision:'approved'|'rejected'};
export type WindowRevocationCommand=WindowBase&{proposalId:string;proposalHash:string;originalDecisionId:string;originalDecisionHash:string;reason:string};
export type WindowConsumeCommand=WindowBase&{proposalId:string;proposalHash:string;decisionId:string;decisionHash:string;targetPairHash:string};
export type WindowCommand=PolicyWindowProposeCommand|WindowDecisionCommand|WindowRevocationCommand|WindowConsumeCommand;
type WindowRisk={perRequestRiskMinor:number;totalRiskMinor:number;maxRequests:number};
type WindowAuthorization={tenant:Tenant;provider:Ref<'ProviderInstanceRevision'>;providerModelId:string;approvalRef:string;environment:'development';effectiveFrom:string;effectiveUntil:string};
type WindowNativeParent={costProposalId:string;costProposalHash:string;costDecisionId:string;consumptionReceiptId:string;budgetRef:Ref<'BudgetRevision'>;budgetHeadVersion:number;providerRef:Ref<'ProviderInstanceRevision'>;providerModelId:string;owner:string;budgetWindow:{effectiveFrom:string;effectiveUntil:string};risk:WindowRisk;makerSubject:string;checkerSubject:string};
type WindowTargets={policy:{policyId:string;revision:1;environment:'development';effectiveFrom:string;effectiveUntil:string;owner:string;approvalRef:string;lifecycle:'active';developmentCostAuthorization:WindowAuthorization;budgetRevisionRef:Ref<'BudgetRevision'>;currency:'CNY';hardStop:true;unknownUsageBehavior:'block';unknownPriceBehavior:'block';allowZeroPrice:false;zeroPriceApprovalRef:null};price:{priceSnapshotId:string;currency:'CNY';inputTokenPrice:null;outputTokenPrice:null;cachedTokenPrice:null;tokenUnit:1000;effectiveFrom:string;effectiveUntil:string;lifecycle:'active';developmentCostAuthorization:WindowAuthorization}};
export type WindowNativeProposal={schemaVersion:1;operationFamily:'budget-policy-window/v1';tenant:Tenant;makerSubject:string;checkerSubject:string;request:PolicyWindowProposeCommand;requestHash:string;parent:WindowNativeParent;approvalSlot:string;targets:WindowTargets;targetPairHash:string;createdAt:string;expiresAt:string};
type WindowReceiptBase={operation:WindowOperation;command:WindowCommand;requestHash:string;proposalId:string;proposalHash:string;receiptId:string;activationEligible:false};
export type WindowProposeReceipt=WindowReceiptBase&{operation:'propose';status:'prepared';command:PolicyWindowProposeCommand;proposal:WindowNativeProposal;targetPairHash:string};
export type WindowDecisionReceipt=WindowReceiptBase&{operation:'decide';status:'observed';command:WindowDecisionCommand;decisionId:string;decisionHash:string;decision:'approved'|'rejected'};
export type WindowRevocationReceipt=WindowReceiptBase&{operation:'revoke';status:'observed';command:WindowRevocationCommand;decisionId:string;decisionHash:string;decision:'revoked'};
export type WindowConsumeReceipt=WindowReceiptBase&{operation:'consume';status:'observed';command:WindowConsumeCommand;decisionId:string;decisionHash:string;targetPairHash:string;budgetRef:Ref<'BudgetRevision'>;policyRef:Ref<'BudgetPolicyRevision'>;priceRef:Ref<'ModelPriceSnapshotRevision'>;bindingId:string;bindingHash:string};
export type WindowNativeReceipt=WindowProposeReceipt|WindowDecisionReceipt|WindowRevocationReceipt|WindowConsumeReceipt;
export type WindowObservation={status:'unknown'|'unresolved';ref:WindowRef;requestHash:string}|{status:'observed';ref:WindowRef;requestHash:string;receipt:WindowNativeReceipt};
type WindowFalseFlags={approvalVerified:false;activationEligible:false;nativeWriteAllowed:false;runtimeAdmissionAllowed:false};
export type WindowGatewayStatus=WindowFalseFlags&{schemaVersion:'aos.budget-policy-window.gateway-status/v1';tenant:Tenant;subject:string;writerEnabled:boolean};
export type WindowRequestIndex={operation:WindowOperation;idempotencyKey:string;requestHash:string};
export type WindowReceiptLinks={prepared?:WindowProposeReceipt;decision?:WindowDecisionReceipt};
const gatewayUrl='http://127.0.0.1:18468/v1/aip/budget-policy-window';
const operations:WindowOperation[]=['propose','decide','revoke','consume'];
const falseFlags=['approvalVerified','activationEligible','nativeWriteAllowed','runtimeAdmissionAllowed'];
const nativeMaker='postgres-service:aos_budget_renewal_maker_call';
function windowKey(value:unknown):value is string{return typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$/.test(value);}
function windowRef(value:unknown):WindowRef{const r=row(value);exact(r,['operation','key']);requireValue(oneOf(r.operation,operations)&&windowKey(r.key));return {operation:r.operation as WindowOperation,key:r.key};}
function falseObservation(v:Record<string,unknown>){requireValue(falseFlags.every(k=>v[k]===false));}
function windowId(value:unknown,kind:string):value is string{return typeof value==='string'&&new RegExp('^window-'+kind+'-[0-9a-f]{64}$').test(value);}
function canonicalWindowText(value:unknown,max=200):value is string{return text(value,max)&&!/[\p{Z}]/u.test(value.replaceAll(' ',''));}
function windowCommandRef(value:unknown,kind:string){ref(value,kind);requireValue(canonicalWindowText(row(value).assetId));}
function commandBase(key:string):WindowBase{requireValue(windowKey(key));return {schemaVersion:1,orgId:'org-org',projectId:'dev-project',idempotencyKey:key};}
function checkedWindowCommand(operation:WindowOperation,value:unknown):WindowCommand{
 requireValue(operations.includes(operation));const c=row(structuredClone(value));
 const fields=operation==='propose'?['parentCostProposalId','parentCostProposalHash','parentCostDecisionId','parentConsumptionReceiptId','expectedBudgetRef','expectedBudgetHeadVersion','expectedProviderRef','expectedProviderModelId','effectiveFrom','effectiveUntil']:
  operation==='decide'?['proposalId','proposalHash','targetPairHash','decision']:operation==='revoke'?['proposalId','proposalHash','originalDecisionId','originalDecisionHash','reason']:['proposalId','proposalHash','decisionId','decisionHash','targetPairHash'];
 exact(c,['schemaVersion','orgId','projectId','idempotencyKey',...fields]);requireValue(c.schemaVersion===1&&c.orgId==='org-org'&&c.projectId==='dev-project'&&windowKey(c.idempotencyKey));
 if(operation==='propose'){
  requireValue(canonicalWindowText(c.parentCostProposalId)&&hash(c.parentCostProposalHash)&&canonicalWindowText(c.parentCostDecisionId)&&canonicalWindowText(c.parentConsumptionReceiptId)&&positive(c.expectedBudgetHeadVersion)&&canonicalWindowText(c.expectedProviderModelId,240));
  windowCommandRef(c.expectedBudgetRef,'BudgetRevision');windowCommandRef(c.expectedProviderRef,'ProviderInstanceRevision');period(c);
  c.effectiveFrom=utcMicros(c.effectiveFrom as string);c.effectiveUntil=utcMicros(c.effectiveUntil as string);
 }else{
  requireValue(windowId(c.proposalId,'proposal')&&hash(c.proposalHash));
  if(operation==='decide')requireValue(hash(c.targetPairHash)&&oneOf(c.decision,['approved','rejected']));
  else if(operation==='revoke')requireValue(windowId(c.originalDecisionId,'approval')&&hash(c.originalDecisionHash)&&canonicalWindowText(c.reason,500));
  else requireValue(windowId(c.decisionId,'approval')&&hash(c.decisionHash)&&hash(c.targetPairHash));
 }
 return c as unknown as WindowCommand;
}
function nativeProposal(value:unknown,command:PolicyWindowProposeCommand,receipt:Record<string,unknown>){
 const p=row(value);exact(p,['schemaVersion','operationFamily','tenant','makerSubject','checkerSubject','request','requestHash','parent','approvalSlot','targets','targetPairHash','createdAt','expiresAt']);tenant(p.tenant);
 requireValue(p.schemaVersion===1&&p.operationFamily==='budget-policy-window/v1'&&p.makerSubject===nativeMaker&&p.checkerSubject===HUMAN&&same(p.request,command)&&p.requestHash===receipt.requestHash&&p.targetPairHash===receipt.targetPairHash&&windowId(receipt.proposalId,'proposal'));
 const suffix=(receipt.proposalId as string).slice('window-proposal-'.length);requireValue(p.approvalSlot==='window-approval-'+suffix);
 const b=row(p.parent);exact(b,['costProposalId','costProposalHash','costDecisionId','consumptionReceiptId','budgetRef','budgetHeadVersion','providerRef','providerModelId','owner','budgetWindow','risk','makerSubject','checkerSubject']);
 ref(b.budgetRef,'BudgetRevision');ref(b.providerRef,'ProviderInstanceRevision');requireValue(b.costProposalId===command.parentCostProposalId&&b.costProposalHash===command.parentCostProposalHash&&b.costDecisionId===command.parentCostDecisionId&&b.consumptionReceiptId===command.parentConsumptionReceiptId&&same(b.budgetRef,command.expectedBudgetRef)&&b.budgetHeadVersion===command.expectedBudgetHeadVersion&&same(b.providerRef,command.expectedProviderRef)&&b.providerModelId===command.expectedProviderModelId&&text(b.owner,160)&&text(b.makerSubject)&&text(b.checkerSubject)&&b.makerSubject!==b.checkerSubject);
 // These are original cost actors, not replacement identities for this child.
 const bw=row(b.budgetWindow);exact(bw,['effectiveFrom','effectiveUntil']);period(bw);
 requireValue(instant(bw.effectiveFrom)<=instant(command.effectiveFrom)&&instant(command.effectiveUntil)<instant(bw.effectiveUntil));
 const risk=row(b.risk);exact(risk,['perRequestRiskMinor','totalRiskMinor','maxRequests']);requireValue(positive(risk.perRequestRiskMinor)&&positive(risk.totalRiskMinor)&&positive(risk.maxRequests)&&BigInt(risk.perRequestRiskMinor)*BigInt(risk.maxRequests)<=BigInt(risk.totalRiskMinor));
 const pair=row(p.targets);exact(pair,['policy','price']);const policy=row(pair.policy),price=row(pair.price);
 exact(policy,['policyId','revision','environment','effectiveFrom','effectiveUntil','owner','approvalRef','lifecycle','developmentCostAuthorization','budgetRevisionRef','currency','hardStop','unknownUsageBehavior','unknownPriceBehavior','allowZeroPrice','zeroPriceApprovalRef']);
 exact(price,['priceSnapshotId','currency','inputTokenPrice','outputTokenPrice','cachedTokenPrice','tokenUnit','effectiveFrom','effectiveUntil','lifecycle','developmentCostAuthorization']);
 const from=canonicalBudgetTime(command.effectiveFrom),until=canonicalBudgetTime(command.effectiveUntil);
 for(const part of [policy,price])requireValue(part.effectiveFrom===from&&part.effectiveUntil===until&&part.currency==='CNY'&&part.lifecycle==='active');
 requireValue(policy.policyId==='window-policy-'+suffix&&policy.revision===1&&policy.environment==='development'&&policy.owner===b.owner&&policy.approvalRef===p.approvalSlot&&same(policy.budgetRevisionRef,b.budgetRef)&&policy.hardStop===true&&policy.unknownUsageBehavior==='block'&&policy.unknownPriceBehavior==='block'&&policy.allowZeroPrice===false&&policy.zeroPriceApprovalRef===null&&price.priceSnapshotId==='window-price-'+suffix&&price.inputTokenPrice===null&&price.outputTokenPrice===null&&price.cachedTokenPrice===null&&price.tokenUnit===1000);
 const auth=row(policy.developmentCostAuthorization);exact(auth,['tenant','provider','providerModelId','approvalRef','environment','effectiveFrom','effectiveUntil']);tenant(auth.tenant);
 requireValue(same(auth,price.developmentCostAuthorization)&&same(auth.provider,b.providerRef)&&auth.providerModelId===b.providerModelId&&auth.approvalRef===p.approvalSlot&&auth.environment==='development'&&auth.effectiveFrom===from&&auth.effectiveUntil===until);
 const created=instant(p.createdAt),expires=instant(p.expiresAt);requireValue(instant(bw.effectiveFrom)<=created&&created<expires&&expires<=created+1800000000n&&expires<=instant(command.effectiveUntil)&&expires<=instant(bw.effectiveUntil));
}
function checkedNativeReceipt(value:unknown,reference:WindowRef,requestHash:string,expected?:WindowCommand):WindowNativeReceipt{
 const r=row(value),op=reference.operation;const fields=op==='propose'?['proposal','targetPairHash']:op==='consume'?['decisionId','decisionHash','targetPairHash','budgetRef','policyRef','priceRef','bindingId','bindingHash']:['decisionId','decisionHash','decision'];
 exact(r,['status','operation','command','requestHash','proposalId','proposalHash','receiptId','activationEligible',...fields]);
 const c=checkedWindowCommand(op,r.command);requireValue(r.operation===op&&r.activationEligible===false&&r.requestHash===requestHash&&hash(requestHash)&&c.idempotencyKey===reference.key&&windowId(r.proposalId,'proposal')&&hash(r.proposalHash)&&windowId(r.receiptId,op)&&r.status===(op==='propose'?'prepared':'observed')&&same(c,r.command)&&(!expected||same(c,expected)));
 if(op==='propose'){requireValue(hash(r.targetPairHash));nativeProposal(r.proposal,c as PolicyWindowProposeCommand,r);}
 else{
  const command=c as WindowDecisionCommand|WindowRevocationCommand|WindowConsumeCommand;
  requireValue(command.proposalId===r.proposalId&&command.proposalHash===r.proposalHash&&hash(r.decisionHash));
  if(op==='decide')requireValue(r.decision===(c as WindowDecisionCommand).decision&&r.decisionId==='window-approval-'+(r.proposalId as string).slice('window-proposal-'.length));
  else if(op==='revoke')requireValue(r.decision==='revoked'&&r.decisionId===r.receiptId);
  else{
   const cc=c as WindowConsumeCommand;requireValue(r.decisionId===cc.decisionId&&r.decisionHash===cc.decisionHash&&r.targetPairHash===cc.targetPairHash&&windowId(r.bindingId,'binding')&&hash(r.bindingHash));
   ref(r.budgetRef,'BudgetRevision');ref(r.policyRef,'BudgetPolicyRevision');ref(r.priceRef,'ModelPriceSnapshotRevision');
   const suffix=(r.proposalId as string).slice('window-proposal-'.length),policy=row(r.policyRef),price=row(r.priceRef);
   requireValue(policy.revision===1&&price.revision===1&&policy.assetId==='window-policy-'+suffix&&price.assetId==='window-price-'+suffix);
  }
 }
 const result=r as unknown as WindowNativeReceipt;displayContexts.set(result,uiContext());return result;
}
function currentNativeReceipt<T extends WindowNativeReceipt>(value:T):T{
 requireValue(displayContexts.get(value)===uiContext());return checkedNativeReceipt(structuredClone(value),{operation:value.operation,key:value.command.idempotencyKey},value.requestHash) as T;
}
function receiptLinks(receipt:WindowNativeReceipt,links?:WindowReceiptLinks){
 requireValue(!links?.decision||links.prepared);
 if(!links?.prepared)return;const p=currentNativeReceipt(links.prepared);
 requireValue(receipt.proposalId===p.proposalId&&receipt.proposalHash===p.proposalHash);
 if(receipt.operation==='decide')requireValue(receipt.command.targetPairHash===p.targetPairHash&&receipt.decisionId===p.proposal.approvalSlot);
 if(receipt.operation==='consume')requireValue(receipt.targetPairHash===p.targetPairHash&&same(receipt.budgetRef,p.proposal.parent.budgetRef)&&receipt.policyRef.assetId===p.proposal.targets.policy.policyId&&receipt.priceRef.assetId===p.proposal.targets.price.priceSnapshotId);
 if(links.decision){const d=currentNativeReceipt(links.decision);requireValue(d.decision==='approved'&&d.proposalId===p.proposalId&&d.proposalHash===p.proposalHash&&d.decisionId===p.proposal.approvalSlot&&d.command.targetPairHash===p.targetPairHash);
  if(receipt.operation==='consume')requireValue(receipt.decisionId===d.decisionId&&receipt.decisionHash===d.decisionHash);
  if(receipt.operation==='revoke')requireValue(receipt.command.originalDecisionId===d.decisionId&&receipt.command.originalDecisionHash===d.decisionHash);
 }
}
export function parseWindowObservation(value:unknown,reference:WindowRef,expected?:WindowCommand,links?:WindowReceiptLinks):WindowObservation{
 const context=uiContext(),refValue=windowRef(reference),v=row(structuredClone(value));exact(v,['schemaVersion','observation',...falseFlags]);falseObservation(v);requireValue(v.schemaVersion==='aos.budget-policy-window.gateway-observation/v1');
 const o=row(v.observation);requireValue(o.operation===refValue.operation&&hash(o.requestHash)&&o.activationEligible===false);
 if(o.status==='unknown'){exact(o,['status','operation','requestHash','activationEligible']);return {status:'unknown',ref:refValue,requestHash:o.requestHash};}
 exact(o,['schemaVersion','operation','requestHash','activationEligible','result']);requireValue(o.schemaVersion===1);const r=row(o.result);requireValue(r.activationEligible===false);
 if(r.status==='unresolved'){exact(r,['status','activationEligible']);return {status:'unresolved',ref:refValue,requestHash:o.requestHash};}
 exact(r,['status','receipt','activationEligible']);requireValue(r.status==='observed');const receipt=checkedNativeReceipt(r.receipt,refValue,o.requestHash,expected);receiptLinks(receipt,links);
 const result:WindowObservation={status:'observed',ref:refValue,requestHash:o.requestHash,receipt};displayContexts.set(result,context);return result;
}
export function parseWindowGatewayStatus(value:unknown):WindowGatewayStatus{
 const context=uiContext(),v=row(structuredClone(value));exact(v,['schemaVersion','tenant','subject','writerEnabled',...falseFlags]);falseObservation(v);tenant(v.tenant);requireValue(v.schemaVersion==='aos.budget-policy-window.gateway-status/v1'&&v.subject===HUMAN&&typeof v.writerEnabled==='boolean');const result=v as unknown as WindowGatewayStatus;displayContexts.set(result,context);return result;
}
export function parseWindowRequestIndex(value:unknown):WindowRequestIndex[]{
 uiContext();const v=row(structuredClone(value));exact(v,['schemaVersion','requests',...falseFlags]);falseObservation(v);requireValue(v.schemaVersion==='aos.budget-policy-window.request-index/v1'&&Array.isArray(v.requests)&&v.requests.length<=4095);
 const seen=new Set<string>();return v.requests.map(item=>{const r=row(item);exact(r,['operation','idempotencyKey','requestHash']);requireValue(oneOf(r.operation,operations)&&windowKey(r.idempotencyKey)&&hash(r.requestHash));const key=JSON.stringify([r.operation,r.idempotencyKey]);requireValue(!seen.has(key));seen.add(key);return r as unknown as WindowRequestIndex;});
}
export function windowDecisionCommand(prepared:WindowProposeReceipt,key:string,decision:string):WindowDecisionCommand{
 const p=currentNativeReceipt(prepared);requireValue(p.operation==='propose'&&oneOf(decision,['approved','rejected']));return {...commandBase(key),proposalId:p.proposalId,proposalHash:p.proposalHash,targetPairHash:p.targetPairHash,decision:decision as 'approved'|'rejected'};
}
function matchingDecision(prepared:WindowProposeReceipt,decision:WindowDecisionReceipt){
 const p=currentNativeReceipt(prepared),d=currentNativeReceipt(decision);requireValue(p.operation==='propose'&&d.operation==='decide'&&d.decision==='approved'&&p.proposalId===d.proposalId&&p.proposalHash===d.proposalHash&&p.targetPairHash===d.command.targetPairHash&&d.decisionId===p.proposal.approvalSlot);return {p,d};
}
export function windowRevocationCommand(prepared:WindowProposeReceipt,decision:WindowDecisionReceipt,key:string,reason:string):WindowRevocationCommand{
 const {p,d}=matchingDecision(prepared,decision);requireValue(canonicalWindowText(reason,500));return {...commandBase(key),proposalId:p.proposalId,proposalHash:p.proposalHash,originalDecisionId:d.decisionId,originalDecisionHash:d.decisionHash,reason};
}
export function windowConsumeCommand(prepared:WindowProposeReceipt,decision:WindowDecisionReceipt,key:string,confirmed:boolean):WindowConsumeCommand{
 const {p,d}=matchingDecision(prepared,decision);requireValue(confirmed===true);return {...commandBase(key),proposalId:p.proposalId,proposalHash:p.proposalHash,decisionId:d.decisionId,decisionHash:d.decisionHash,targetPairHash:p.targetPairHash};
}
class WindowGatewayUnavailable extends Error{constructor(){super('原结果尚未确认，请核对身份和预算服务，并按原操作编号查询，勿重新发送');}}
async function windowWire<T>(path:string,method:'GET'|'POST',body:WindowCommand|undefined,parse:(v:unknown)=>T):Promise<T>{
 const context=uiContext(),controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
 try{
  const response=await fetch(gatewayUrl+path,{method,headers:tenantAuthHeaders(),mode:'cors',credentials:'omit',redirect:'error',cache:'no-store',signal:controller.signal,...(body?{body:JSON.stringify(body)}:{})});
  requireValue(response.headers.get('content-type')?.split(';')[0].trim().toLowerCase()==='application/json'&&(response.headers.get('content-encoding')??'identity')==='identity');
  const length=response.headers.get('content-length');if(length!==null)requireValue(/^\d{1,10}$/.test(length)&&Number(length)<=2097152);
  requireValue(response.body);const reader=response.body.getReader(),chunks:Uint8Array[]=[];let size=0;
  try{while(true){const next=await reader.read();if(next.done)break;size+=next.value.byteLength;if(size>2097152){await reader.cancel();throw new WindowGatewayUnavailable();}chunks.push(next.value);}}finally{reader.releaseLock();}
  const bytes=new Uint8Array(size);let cursor=0;for(const chunk of chunks){bytes.set(chunk,cursor);cursor+=chunk.byteLength;}
  const value:unknown=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));requireValue(uiContext()===context);
  if(response.status!==200){const error=row(value);exact(error,['schemaVersion','code',...falseFlags]);falseObservation(error);requireValue(error.schemaVersion==='aos.budget-policy-window.gateway-error/v1');throw new WindowGatewayUnavailable();}
  return parse(value);
 }catch{throw new WindowGatewayUnavailable();}finally{clearTimeout(timer);}
}
export function readWindowGatewayStatus(){return windowWire('/status','GET',undefined,parseWindowGatewayStatus);}
export function listWindowRequests(){return windowWire('/requests','GET',undefined,parseWindowRequestIndex);}
export function inquireWindowRequest(reference:WindowRef,links?:WindowReceiptLinks){const r=windowRef(reference);return windowWire('/requests/'+r.operation+'/'+r.key,'GET',undefined,v=>parseWindowObservation(v,r,undefined,links));}
export function submitWindowOperation(operation:WindowOperation,command:WindowCommand,links?:WindowReceiptLinks){
 const c=checkedWindowCommand(operation,command),r={operation,key:c.idempotencyKey};return windowWire('/'+operation,'POST',c,v=>parseWindowObservation(v,r,c,links));
}
export function restoreWindowReference(search:string):{ref:WindowRef;attempted:boolean}|null{
 try{const params=new URLSearchParams(search);for(const key of ['windowOperation','windowKey','windowAttempted'])requireValue(params.getAll(key).length<=1);const ref=windowRef({operation:params.get('windowOperation'),key:params.get('windowKey')});const marker=params.get('windowAttempted');requireValue(marker===null||marker==='0'||marker==='1');return {ref,attempted:marker==='1'};}catch{return null;}
}
export function saveWindowReference(reference:WindowRef,attempted:boolean){
 const r=windowRef(reference);requireValue(typeof attempted==='boolean');const params=new URLSearchParams(window.location.search);params.set('windowOperation',r.operation);params.set('windowKey',r.key);params.set('windowAttempted',attempted?'1':'0');window.history.replaceState(window.history.state,'',window.location.pathname+'?'+params+window.location.hash);
}
export function formatWindowRiskMinor(value:number){requireValue(positive(value));const minor=BigInt(value);return '¥'+minor/100n+'.'+String(minor%100n).padStart(2,'0');}
