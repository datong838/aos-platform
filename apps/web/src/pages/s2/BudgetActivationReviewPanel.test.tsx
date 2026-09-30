import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { BudgetActivationReviewPanel } from './BudgetActivationReviewPanel';
import { parseBudgetResult, restoreBudgetReference } from '../../api/aipBudgetActivation';
import * as transport from '../../api/client';
import { getTenant, setTenant, setAccessToken } from '../../api/tenant';
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const target = { budgetId:'budget-1',revision:2,environment:'development',currency:'CNY',dailyLimitMinor:500,
 monthlyLimitMinor:5000,alertThresholdPct:80,hardStop:true,unknownUsageBehavior:'block',
 effectiveFrom:'2026-01-01T00:00:00Z',effectiveUntil:'2099-01-01T00:00:00Z',owner:'owner',overBudgetApprover:'reviewer',lifecycle:'active' };
const candidate = { headVersion:1,draftRevision:1,target,activationEligible:false };

describe('budget review product', () => {
 let host:HTMLDivElement,root:Root;
 beforeEach(()=>{window.history.replaceState({},'', '/aip/capacity');host=document.createElement('div');document.body.append(host);root=createRoot(host);});
 afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.restoreAllMocks();setAccessToken(null);setTenant({subject:undefined});});
 const button=(text:string)=>[...host.querySelectorAll('button')].find(x=>x.textContent===text)!;
 async function input(label:string,value:string){await act(async()=>{const node=host.querySelector<HTMLInputElement>(`[aria-label="${label}"]`)!;Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(node,value);node.dispatchEvent(new Event('input',{bubbles:true}));});}
 async function render(){await act(async()=>root.render(<BudgetActivationReviewPanel/>));}
 it('does not submit unknown outcome twice even when later query reports missing',async()=>{
  vi.spyOn(transport,'apiGetAuthoritative').mockImplementation(async(path)=>path.includes('activation-candidates')?candidate:{status:'not_attempted'});
  const post=vi.spyOn(transport,'apiPostUnqueued').mockRejectedValue(new Error('lost response'));
  await render();expect(button('生成预算预览').disabled).toBe(true);
  await input('预算或审批记录 ID','budget-1');await input('独立审核人账号','checker-other');
  await act(async()=>button('读取审批对象').click());
  expect(button('生成预算预览').disabled).toBe(false);
  await act(async()=>{button('生成预算预览').click();button('生成预算预览').click();});
  expect(post).toHaveBeenCalledTimes(1);expect(button('生成预算预览').disabled).toBe(true);
  await act(async()=>button('查询原请求结果').click());
  expect(button('生成预算预览').disabled).toBe(true);expect(post).toHaveBeenCalledTimes(1);
  expect(window.location.search).not.toContain('checker-other');
 });
 it('restores safe references only with GET and keeps writes frozen',async()=>{
  window.history.replaceState({},'', '/aip/capacity?budgetReviewMode=preview&budgetReviewRef=budget-1&budgetReviewRevision=2&budgetReviewHead=1&budgetAttempted=1');
  const get=vi.spyOn(transport,'apiGetAuthoritative').mockResolvedValue({status:'observed',previewId:'preview-1',previewHash:'a'.repeat(64),activationEligible:false});
  const post=vi.spyOn(transport,'apiPostUnqueued');await render();
  expect(get).toHaveBeenCalledTimes(1);expect(post).not.toHaveBeenCalled();
  expect(host.textContent).toContain('preview-1');expect(button('生成预算预览').disabled).toBe(true);
 });
 it('rejects authority-shaped or incomplete result and malformed URL refs',()=>{
  expect(()=>parseBudgetResult({status:'observed',previewId:'p',activationEligible:true},'preview',false)).toThrow();
  expect(()=>parseBudgetResult({status:'not_attempted'},'preview',false)).toThrow();
  expect(restoreBudgetReference('?budgetReviewMode=preview&budgetReviewRef=b&budgetReviewRevision=-1&budgetReviewHead=1')).toBeNull();
 });
 async function select(label:string,value:string){await act(async()=>{const node=host.querySelector<HTMLSelectElement>(`[aria-label="${label}"]`)!;node.value=value;node.dispatchEvent(new Event('change',{bubbles:true}));});}
 function previewRecord(){return {previewId:'preview-1',previewHash:'a'.repeat(64),budgetId:'budget-1',targetRevision:2,
  targetHash:'b'.repeat(64),expectedHeadVersion:1,makerSubject:'maker',checkerSubject:getTenant().subject,
  externalUsageProven:false,activationEligible:false,target,internalLedgerCheckedAt:'2026-01-01T00:00:00Z',expiresAt:'2099-01-01T00:00:00Z'};}
 it('requires an explicit independent decision and submits the reviewed preview only',async()=>{
  setTenant({subject:'checker'});const p=previewRecord();
  vi.spyOn(transport,'apiGetAuthoritative').mockImplementation(async(path)=>path.endsWith('decision-intent')?{status:'not_attempted'}:p);
  const post=vi.spyOn(transport,'apiPostUnqueued').mockResolvedValue({status:'observed',decisionId:'decision-1',activationEligible:false});
  await render();await select('预算审批操作','decision');await input('预算或审批记录 ID','preview-1');
  await act(async()=>button('读取审批对象').click());expect(button('提交复核决定').disabled).toBe(true);
  await select('预算复核意见','rejected');expect(button('提交复核决定').disabled).toBe(false);
  await act(async()=>button('提交复核决定').click());
  expect(post).toHaveBeenCalledWith('/v1/aip/budgets/activation-previews/preview-1/decision-intent',{decision:'rejected'},{});
  expect(host.textContent).toContain('decision-1');expect(host.textContent).toContain('不表示预算已经生效');
 });
 it('reads approval content before revocation and keeps reason outside URL',async()=>{
  setTenant({subject:'checker'});const p=previewRecord();
  const d={decisionId:'decision-1',previewId:p.previewId,previewHash:p.previewHash,targetHash:p.targetHash,
   checkerSubject:p.checkerSubject,decision:'approved',activationEligible:false,expiresAt:p.expiresAt};
  vi.spyOn(transport,'apiGetAuthoritative').mockImplementation(async(path)=>path.endsWith('revocation-intent')?{status:'not_attempted'}:{decision:d,preview:p,revoked:false});
  const post=vi.spyOn(transport,'apiPostUnqueued').mockResolvedValue({status:'observed',revocationId:'revoke-1',activationEligible:false});
  await render();await select('预算审批操作','revoke');await input('预算或审批记录 ID','decision-1');
  await act(async()=>button('读取审批对象').click());expect(button('撤销此批准').disabled).toBe(true);
  await input('预算撤销原因','配置已变更');await act(async()=>button('撤销此批准').click());
  expect(post).toHaveBeenCalledWith('/v1/aip/budgets/activation-decisions/decision-1/revocation-intent',{reason:'配置已变更'},{});
  expect(window.location.search).not.toContain(encodeURIComponent('配置已变更'));expect(host.textContent).toContain('revoke-1');
 });
 it('discards late response after identity changes',async()=>{
  let resolve!:(value:unknown)=>void;
  const get=vi.spyOn(transport,'apiGetAuthoritative').mockReturnValue(new Promise(done=>{resolve=done;}));
  await render();await input('预算或审批记录 ID','budget-1');await act(async()=>button('读取审批对象').click());
  await act(async()=>setAccessToken('different-identity'));
  await act(async()=>resolve(candidate));
  expect(host.textContent).not.toContain('候选第 2 版');expect(button('生成预算预览').disabled).toBe(true);
  expect(get).toHaveBeenCalledTimes(1);expect(window.location.search).toBe('');
 });
 it('rejects mismatched preview source and never enables decision',async()=>{
  setTenant({subject:'checker'});
  vi.spyOn(transport,'apiGetAuthoritative').mockResolvedValue({...previewRecord(),previewId:'another-preview'});
  const post=vi.spyOn(transport,'apiPostUnqueued');
  await render();await select('预算审批操作','decision');await input('预算或审批记录 ID','preview-1');
  await select('预算复核意见','approved');await act(async()=>button('读取审批对象').click());
  expect(button('提交复核决定').disabled).toBe(true);expect(post).not.toHaveBeenCalled();
 });

});
