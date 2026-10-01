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
