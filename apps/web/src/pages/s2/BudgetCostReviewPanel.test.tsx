import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { BudgetCostReviewPanel } from './BudgetCostReviewPanel';
import { parseCostReview, parseCostResult, restoreCostReference } from '../../api/aipBudgetCost';
import * as transport from '../../api/client';
import { setTenant, setAccessToken } from '../../api/tenant';
(globalThis as {IS_REACT_ACT_ENVIRONMENT?:boolean}).IS_REACT_ACT_ENVIRONMENT=true;
const target={budgetId:'b',revision:2,environment:'development',currency:'CNY',dailyLimitMinor:500,monthlyLimitMinor:5000,
 alertThresholdPct:80,hardStop:true,unknownUsageBehavior:'block',effectiveFrom:'2026-01-01T00:00:00Z',effectiveUntil:'2099-01-01T00:00:00Z',owner:'maker',overBudgetApprover:'checker',lifecycle:'active'};
const proposal={schemaVersion:1,tenant:{orgId:'org-org',projectId:'dev-project'},target,draftRevision:1,expectedHeadVersion:1,makerSubject:'maker',checkerSubject:'checker',
 basis:{kind:'development_risk_proposal',provider:{assetType:'ProviderInstanceRevision',assetId:'provider',revision:1,contentHash:'b'.repeat(64)},providerModelId:'model',perRequestRiskMinor:10,totalRiskMinor:100,maxRequests:10},
 accounts:{daily:'b:daily',pilot:'b:pilot'},currency:'CNY',period:{start:target.effectiveFrom,end:target.effectiveUntil}};
const createdAt=Date.now();
const saved={proposalId:'p',proposalHash:'a'.repeat(64),proposal,status:'proposed',sourceVerification:'pending',activationEligible:false,createdAt:new Date(createdAt).toISOString(),expiresAt:new Date(createdAt+1800000).toISOString()};
const view={proposal:saved,decision:null,revocation:null};
let host:HTMLDivElement,root:Root;
beforeEach(()=>{setTenant({orgId:'org-org',projectId:'dev-project',subject:'checker'});window.history.replaceState({},'', '/aip/capacity');host=document.createElement('div');document.body.append(host);root=createRoot(host);});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.restoreAllMocks();setAccessToken(null);setTenant({subject:undefined});});
const button=(s:string)=>[...host.querySelectorAll('button')].find(b=>b.textContent===s)!;
async function input(s:string,v:string){await act(async()=>{const n=host.querySelector<HTMLInputElement>(`[aria-label="${s}"]`)!;Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(n,v);n.dispatchEvent(new Event('input',{bubbles:true}));});}
async function select(s:string,v:string){await act(async()=>{const n=host.querySelector<HTMLSelectElement>(`[aria-label="${s}"]`)!;n.value=v;n.dispatchEvent(new Event('change',{bubbles:true}));});}
async function render(){await act(async()=>root.render(<BudgetCostReviewPanel/>));}
function reads(snapshot:unknown=view){vi.spyOn(transport,'apiGetAuthoritative').mockImplementation(async p=>p.endsWith('/review')?snapshot:{status:'not_attempted'});}
async function load(){await input('费用提议 ID','p');await act(async()=>button('读取费用提议').click());}
it('requires explicit choice and preserves unknown without duplicate sends',async()=>{
 reads();const post=vi.spyOn(transport,'apiPostUnqueued').mockRejectedValue(new Error('lost response'));
 await render();expect(button('提交费用复核').disabled).toBe(true);await load();expect(button('提交费用复核').disabled).toBe(true);
 await select('费用复核意见','approved');expect(button('提交费用复核').disabled).toBe(false);
 await act(async()=>{button('提交费用复核').click();button('提交费用复核').click();});
 expect(post).toHaveBeenCalledTimes(1);expect(post).toHaveBeenCalledWith('/v1/aip/budgets/cost-proposals/p/review-requests/decide',{proposalHash:saved.proposalHash,decision:'approved'},{});
 await act(async()=>button('查询费用原请求').click());expect(button('提交费用复核').disabled).toBe(true);
 expect(window.location.search).not.toContain(saved.proposalHash);expect(window.location.search).not.toContain('approved');
});
it('restores only an original inquiry and never auto-submits',async()=>{
 window.history.replaceState({},'', '/aip/capacity?budgetCostRef=p&budgetCostOperation=decide&budgetCostAttempted=1');
 reads();const post=vi.spyOn(transport,'apiPostUnqueued');await render();
 expect(transport.apiGetAuthoritative).toHaveBeenCalledTimes(1);expect(post).not.toHaveBeenCalled();expect(button('提交费用复核').disabled).toBe(true);
});
it('drops a late source after auth changes',async()=>{
 let finish!:(v:unknown)=>void;vi.spyOn(transport,'apiGetAuthoritative').mockReturnValue(new Promise(resolve=>{finish=resolve;}));
 await render();await input('费用提议 ID','p');await act(async()=>button('读取费用提议').click());
 await act(async()=>setAccessToken('changed-only-in-test'));await act(async()=>finish(view));
 expect(host.textContent).not.toContain('单次风险');expect(button('提交费用复核').disabled).toBe(true);
});
it('maker can withdraw an approved snapshot with explicit reason',async()=>{
 setTenant({subject:'maker'});reads({...view,decision:{decisionId:'d',proposalId:'p',proposalHash:saved.proposalHash,checkerSubject:'checker',decision:'approved',expiresAt:saved.expiresAt,activationEligible:false}});
 const post=vi.spyOn(transport,'apiPostUnqueued').mockResolvedValue({status:'observed',result:{revocationId:'r',decisionId:'d',activationEligible:false},activationEligible:false});
 await render();await select('费用审核操作','revoke');await load();expect(button('撤销费用批准').disabled).toBe(true);
 await input('费用撤销原因','withdraw');await act(async()=>button('撤销费用批准').click());
 expect(post).toHaveBeenCalledWith('/v1/aip/budgets/cost-proposals/p/review-requests/revoke',{proposalHash:saved.proposalHash,reason:'withdraw'},{});
 expect(host.textContent).toContain('原记录：r');expect(window.location.search).not.toContain('withdraw');
});
it('rejects partial, wrong tenant, authority flags and malformed references',()=>{
 expect(()=>parseCostReview({...view,extra:true},'p')).toThrow();
 expect(()=>parseCostReview({...view,proposal:{...saved,activationEligible:true}},'p')).toThrow();
 expect(()=>parseCostReview({...view,proposal:{...saved,proposal:{...proposal,tenant:{orgId:'dev-org',projectId:'dev-project'}}}},'p')).toThrow();
 expect(restoreCostReference('?budgetCostRef=p&budgetCostRef=q&budgetCostOperation=decide')).toBeNull();
 expect(()=>parseCostResult({status:'not_attempted'},{id:'p',operation:'decide'},false)).toThrow();
 expect(()=>parseCostResult({status:'observed',result:{decisionId:'d',decision:'approved',proposalHash:'a'.repeat(64),activationEligible:true},activationEligible:false},{id:'p',operation:'decide'},false)).toThrow();
});

it('accepts the contract maximum model identity and rejects oversized identities',()=>{
 const source=(model:string)=>({...view,proposal:{...saved,proposal:{...proposal,basis:{...proposal.basis,providerModelId:model}}}});
 expect(parseCostReview(source('m'.repeat(240)),'p').proposal.proposal.basis.providerModelId).toHaveLength(240);
 expect(()=>parseCostReview(source('m'.repeat(241)),'p')).toThrow();
});

it('maker cannot decide and an existing decision cannot be signed again',async()=>{
 setTenant({subject:'maker'});reads();const post=vi.spyOn(transport,'apiPostUnqueued');
 await render();await load();await select('费用复核意见','approved');expect(button('提交费用复核').disabled).toBe(true);
 await act(async()=>setTenant({subject:'checker'}));
 vi.mocked(transport.apiGetAuthoritative).mockImplementation(async path=>path.endsWith('/review')?{...view,decision:{decisionId:'d',proposalId:'p',proposalHash:saved.proposalHash,checkerSubject:'checker',decision:'rejected',expiresAt:saved.expiresAt,activationEligible:false}}:{status:'not_attempted'});
 await load();await select('费用复核意见','approved');expect(button('提交费用复核').disabled).toBe(true);expect(post).not.toHaveBeenCalled();
});

const approvedView={...view,decision:{decisionId:'d',proposalId:'p',proposalHash:saved.proposalHash,checkerSubject:'checker',decision:'approved',expiresAt:saved.expiresAt,activationEligible:false}};
const consumption={status:'observed',activationEligible:false,receipt:{resourceType:'BudgetRevision',resourceId:'b',revision:2,contentHash:'c'.repeat(64),proposalId:'p',proposalHash:saved.proposalHash,decisionId:'d',receiptId:'budget-cost-consume-'+'d'.repeat(64)}};
it('maker explicitly enables approved budget once and unknown stays inquiry-only',async()=>{
 setTenant({subject:'maker'});reads(approvedView);const post=vi.spyOn(transport,'apiPostUnqueued').mockRejectedValue(new Error('lost response'));
 await render();await select('费用审核操作','consume');await load();expect(button('启用已批准预算').disabled).toBe(true);
 await select('预算启用确认','consume');expect(button('启用已批准预算').disabled).toBe(false);
 await act(async()=>{button('启用已批准预算').click();button('启用已批准预算').click();});
 expect(post).toHaveBeenCalledTimes(1);expect(post).toHaveBeenCalledWith('/v1/aip/budgets/cost-proposals/p/consumption-request',{proposalHash:saved.proposalHash,decisionId:'d'},{});
 await act(async()=>button('查询费用原请求').click());expect(button('启用已批准预算').disabled).toBe(true);
 expect(window.location.search).not.toContain(saved.proposalHash);
});
it('restored consumption only queries and never posts',async()=>{
 window.history.replaceState({},'', '/aip/capacity?budgetCostRef=p&budgetCostOperation=consume&budgetCostAttempted=1');
 reads();const post=vi.spyOn(transport,'apiPostUnqueued');await render();
 expect(transport.apiGetAuthoritative).toHaveBeenCalledWith('/v1/aip/budgets/cost-proposals/p/consumption-request');
 expect(post).not.toHaveBeenCalled();expect(button('启用已批准预算').disabled).toBe(true);
});
it('consumption receipt must match the proposal, decision and budget',()=>{
 const ref={id:'p',operation:'consume' as const};
 expect(parseCostResult(consumption,ref,false,approvedView as never)).toMatchObject({status:'observed',id:consumption.receipt.receiptId});
 for(const [field,value] of [['proposalId','other'],['decisionId','other'],['resourceId','other'],['revision',3],['contentHash','invalid'],['receiptId','invalid']]){
  expect(()=>parseCostResult({...consumption,receipt:{...consumption.receipt,[field]:value}},ref,false,approvedView as never)).toThrow();
 }
});
it.each(['checker','revoked','expired'])('blocks consumption for %s',async kind=>{
 setTenant({subject:kind==='checker'?'checker':'maker'});
 const expired=new Date(Date.now()-1000).toISOString();
 const snapshot=kind==='expired'?{...approvedView,proposal:{...saved,createdAt:new Date(Date.now()-1801000).toISOString(),expiresAt:expired},decision:{...approvedView.decision,expiresAt:expired}}:
 kind==='revoked'?{...approvedView,revocation:{revocationId:'r',decisionId:'d',actorSubject:'maker',reason:'withdraw',createdAt:new Date().toISOString()}}:approvedView;
 reads(snapshot);const post=vi.spyOn(transport,'apiPostUnqueued');await render();await select('费用审核操作','consume');await load();await select('预算启用确认','consume');
 expect(button('启用已批准预算').disabled).toBe(true);expect(post).not.toHaveBeenCalled();
});


const configuration={status:'observed',activationEligible:false,receipt:{proposalId:'p',proposalHash:saved.proposalHash,decisionId:'d',receiptId:'cost-configuration-'+'e'.repeat(64),
 budgetRef:{assetType:'BudgetRevision',assetId:'b',revision:2,contentHash:'c'.repeat(64)},
 priceRef:{assetType:'ModelPriceSnapshotRevision',assetId:'cost-price-'+'e'.repeat(64),revision:1,contentHash:'f'.repeat(64)},
 policyRef:{assetType:'BudgetPolicyRevision',assetId:'cost-policy-'+'e'.repeat(64),revision:1,contentHash:'1'.repeat(64)}}};
function configurationReads(consumed:unknown=consumption){vi.spyOn(transport,'apiGetAuthoritative').mockImplementation(async path=>path.endsWith('/review')?approvedView:path.endsWith('/consumption-request')?consumed:{status:'not_attempted'});}
it('configures only after observed consumption and explicit maker confirmation',async()=>{
 setTenant({subject:'maker'});configurationReads();const post=vi.spyOn(transport,'apiPostUnqueued').mockResolvedValue(configuration);
 await render();await select('费用审核操作','configure');await load();
 expect(button('生成费用配置').disabled).toBe(true);await select('费用配置确认','configure');
 expect(button('生成费用配置').disabled).toBe(false);await act(async()=>button('生成费用配置').click());
 expect(post).toHaveBeenCalledWith('/v1/aip/budgets/cost-proposals/p/configuration-request',{proposalHash:saved.proposalHash,decisionId:'d'},{});
 expect(host.textContent).toContain('费用配置的历史回执');expect(host.textContent).toContain(configuration.receipt.priceRef.assetId);
 expect(button('生成费用配置').disabled).toBe(true);
});
it.each(['not_attempted','unresolved','conflict'])('missing consumed authority %s blocks configuration',async status=>{
 setTenant({subject:'maker'});configurationReads({status});const post=vi.spyOn(transport,'apiPostUnqueued');
 await render();await select('费用审核操作','configure');await load();await select('费用配置确认','configure');
 expect(button('生成费用配置').disabled).toBe(true);expect(post).not.toHaveBeenCalled();
});
it('restored configuration queries without submission',async()=>{
 window.history.replaceState({},'', '/aip/capacity?budgetCostRef=p&budgetCostOperation=configure&budgetCostAttempted=1');
 reads();const post=vi.spyOn(transport,'apiPostUnqueued');await render();
 expect(transport.apiGetAuthoritative).toHaveBeenCalledWith('/v1/aip/budgets/cost-proposals/p/configuration-request');
 expect(post).not.toHaveBeenCalled();expect(button('生成费用配置').disabled).toBe(true);
});
it('unknown configuration never resends even when queried as not attempted',async()=>{
 setTenant({subject:'maker'});configurationReads();const post=vi.spyOn(transport,'apiPostUnqueued').mockRejectedValue(new Error('lost'));
 await render();await select('费用审核操作','configure');await load();await select('费用配置确认','configure');
 await act(async()=>{button('生成费用配置').click();button('生成费用配置').click();});
 await act(async()=>button('查询费用原请求').click());expect(button('生成费用配置').disabled).toBe(true);expect(post).toHaveBeenCalledTimes(1);
 expect(window.location.search).toContain('budgetCostOperation=configure');expect(window.location.search).toContain('budgetCostAttempted=1');
 expect(window.location.search).not.toContain(saved.proposalHash);
});
it('configuration receipt rejects drift against consumed budget and exact proposal',()=>{
 const ref={id:'p',operation:'configure' as const},source=parseCostReview(approvedView,'p'),consumed=parseCostResult(consumption,{id:'p',operation:'consume'},true,source);
 expect(parseCostResult(configuration,ref,true,source,undefined,consumed)).toMatchObject({status:'observed',priceRef:configuration.receipt.priceRef});
 for(const [key,field,value] of [['priceRef','assetId','other'],['policyRef','revision',2],['budgetRef','contentHash','f'.repeat(64)],['budgetRef','assetId','other'],['priceRef','revision',true]]){
  const copy=structuredClone(configuration);(copy.receipt as unknown as Record<string,Record<string,unknown>>)[String(key)][String(field)]=value;
  expect(()=>parseCostResult(copy,ref,true,source,undefined,consumed)).toThrow();
 }
 expect(()=>parseCostResult({...configuration,receipt:{...configuration.receipt,decisionId:'other'}},ref,true,source)).toThrow();
 expect(()=>parseCostResult(consumption,ref,true,source)).toThrow();
});
it('identity change invalidates an already loaded consumed receipt',async()=>{
 setTenant({subject:'maker'});configurationReads();const post=vi.spyOn(transport,'apiPostUnqueued');
 await render();await select('费用审核操作','configure');await load();await select('费用配置确认','configure');
 expect(button('生成费用配置').disabled).toBe(false);await act(async()=>setAccessToken('new-test-identity'));
 expect(button('生成费用配置').disabled).toBe(true);expect(host.textContent).not.toContain('已观察到对应预算启用回执');expect(post).not.toHaveBeenCalled();
});
it('mismatched consumed budget cannot open configuration',async()=>{
 setTenant({subject:'maker'});configurationReads({...consumption,receipt:{...consumption.receipt,resourceId:'other'}});
 const post=vi.spyOn(transport,'apiPostUnqueued');await render();await select('费用审核操作','configure');await load();await select('费用配置确认','configure');
 expect(button('生成费用配置').disabled).toBe(true);expect(post).not.toHaveBeenCalled();
});
it.each(['checker','revoked','expired'])('configuration cannot use %s approval',async kind=>{
 setTenant({subject:kind==='checker'?'checker':'maker'});
 const expired=new Date(Date.now()-1000).toISOString();
 const snapshot=kind==='expired'?{...approvedView,proposal:{...saved,createdAt:new Date(Date.now()-1801000).toISOString(),expiresAt:expired},decision:{...approvedView.decision,expiresAt:expired}}:
 kind==='revoked'?{...approvedView,revocation:{revocationId:'r',decisionId:'d',actorSubject:'maker',reason:'withdraw',createdAt:new Date().toISOString()}}:approvedView;
 vi.spyOn(transport,'apiGetAuthoritative').mockImplementation(async path=>path.endsWith('/review')?snapshot:path.endsWith('/consumption-request')?consumption:{status:'not_attempted'});
 const post=vi.spyOn(transport,'apiPostUnqueued');await render();await select('费用审核操作','configure');await load();await select('费用配置确认','configure');
 expect(button('生成费用配置').disabled).toBe(true);expect(post).not.toHaveBeenCalled();
});
