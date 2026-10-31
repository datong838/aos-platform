// Synthetic React grammar only; no native identity, budget COMMIT or human consent.
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {beforeEach,afterEach,describe,it,expect,vi} from 'vitest';
import {BudgetPolicyRenewalReviewPanel} from './BudgetPolicyRenewalReviewPanel';
import * as transport from '../../api/client';
import {setTenant,setAccessToken} from '../../api/tenant';
import {saveRenewalReference} from '../../api/aipBudgetPolicyRenewal';
(globalThis as {IS_REACT_ACT_ENVIRONMENT?:boolean}).IS_REACT_ACT_ENVIRONMENT=true;
function fixture(): any { return {
  "schemaVersion": "aos.budget-policy-renewal.review-source/v1",
  "tenant": {
    "orgId": "org-org",
    "projectId": "dev-project"
  },
  "evaluatedAt": "2026-10-16T00:00:00Z",
  "sourcePolicy": {
    "tenant": {
      "orgId": "org-org",
      "projectId": "dev-project"
    },
    "policyId": "fixture-policy",
    "revision": 13,
    "contentHash": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "createdBy": "unit-fixture",
    "createdAt": "2026-09-01T00:00:00Z",
    "environment": "development",
    "effectiveFrom": "2026-09-01T00:00:00Z",
    "effectiveUntil": "2026-09-25T00:00:00Z",
    "owner": "unit-fixture",
    "approvalRef": "unit-fixture-old-approval",
    "lifecycle": "active",
    "budgetRevisionRef": {
      "assetType": "BudgetRevision",
      "assetId": "fixture-budget",
      "revision": 1,
      "contentHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    },
    "currency": "CNY",
    "hardStop": true,
    "unknownUsageBehavior": "block",
    "unknownPriceBehavior": "block",
    "allowZeroPrice": false,
    "zeroPriceApprovalRef": null
  },
  "sourceHeadVersion": 13,
  "sourceBudget": {
    "tenant": {
      "orgId": "org-org",
      "projectId": "dev-project"
    },
    "budgetId": "fixture-budget",
    "revision": 1,
    "contentHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "createdBy": "unit-fixture",
    "createdAt": "2026-09-01T00:00:00Z",
    "environment": "development",
    "currency": "CNY",
    "dailyLimitMinor": 1000,
    "monthlyLimitMinor": 20000,
    "alertThresholdPct": 80,
    "hardStop": true,
    "unknownUsageBehavior": "block",
    "effectiveFrom": "2026-09-01T00:00:00Z",
    "effectiveUntil": "2027-01-01T00:00:00Z",
    "owner": "unit-fixture",
    "overBudgetApprover": "unit-fixture-checker",
    "lifecycle": "active"
  },
  "currentBudget": {
    "tenant": {
      "orgId": "org-org",
      "projectId": "dev-project"
    },
    "budgetId": "fixture-budget",
    "revision": 1,
    "contentHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "createdBy": "unit-fixture",
    "createdAt": "2026-09-01T00:00:00Z",
    "environment": "development",
    "currency": "CNY",
    "dailyLimitMinor": 1000,
    "monthlyLimitMinor": 20000,
    "alertThresholdPct": 80,
    "hardStop": true,
    "unknownUsageBehavior": "block",
    "effectiveFrom": "2026-09-01T00:00:00Z",
    "effectiveUntil": "2027-01-01T00:00:00Z",
    "owner": "unit-fixture",
    "overBudgetApprover": "unit-fixture-checker",
    "lifecycle": "active"
  },
  "sourceProvider": null,
  "currentProvider": null,
  "sourceWindow": "expired",
  "budgetWindow": "effective",
  "state": "blocked",
  "blockers": [
    "RENEWAL_SOURCE_COST_AUTHORIZATION_MISSING"
  ],
  "approvalVerified": false,
  "activationEligible": false
}; }

 function providerFixture(): any {
  const b=fixture();
  const ref=(assetType:string,assetId:string)=>({assetType,assetId,revision:1,contentHash:'d'.repeat(64)});
  const p={tenant:b.tenant,providerInstanceId:'unit-provider',revision:1,contentHash:'d'.repeat(64),
   createdBy:'unit-fixture',createdAt:'2026-09-01T00:00:00Z',
   pluginRef:ref('ProviderPluginRevision','unit-plugin'),
   endpointProfile:{baseUrl:'https://example.invalid',region:'unit-region',timeoutMs:1000,metadata:{}},
   secretRef:'vault://unit-reference-not-a-credential',secretVersion:'unit-v1',
   egressPolicyRef:ref('EgressPolicyRevision','unit-egress'),
   dataClassificationPolicyRef:ref('DataClassificationPolicyRevision','unit-data'),lifecycle:'active'};
  b.sourcePolicy.developmentCostAuthorization={tenant:b.tenant,provider:ref('ProviderInstanceRevision','unit-provider'),
   providerModelId:'unit-model',approvalRef:b.sourcePolicy.approvalRef,environment:'development',
   effectiveFrom:'2026-09-01T00:00:00Z',effectiveUntil:'2026-09-25T00:00:00Z'};
  b.sourceProvider=p;b.currentProvider=structuredClone(p);b.state='ready';b.blockers=[];return b;
 }

 function command(): any { return {schemaVersion:1,orgId:'org-org',projectId:'dev-project',
  idempotencyKey:'unit-propose',sourcePolicyId:'fixture-policy',expectedSourceRevision:13,
  expectedHeadVersion:13,expectedSourceHash:'c'.repeat(64),
  effectiveFrom:'2026-10-16T00:00:00Z',effectiveUntil:'2026-11-01T00:00:00Z'}; }

 function prepared(): any {
  const s=providerFixture(),request=command(),slot='renewal-approval-unit';
  const target=structuredClone(s.sourcePolicy);
  for(const k of ['tenant','contentHash','createdBy','createdAt'])delete target[k];
  Object.assign(target,{revision:14,effectiveFrom:request.effectiveFrom,effectiveUntil:request.effectiveUntil,
    approvalRef:slot,lifecycle:'active',developmentCostAuthorization:{...target.developmentCostAuthorization,
     approvalRef:slot,effectiveFrom:request.effectiveFrom,effectiveUntil:request.effectiveUntil}});
  const draft={...target,lifecycle:'draft'},human='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657',maker='postgres-service:aos_budget_renewal_maker_call';
  const proposal={schemaVersion:1,tenant:s.tenant,makerSubject:maker,checkerSubject:human,
   sourceRef:{assetType:'BudgetPolicyRevision',assetId:'fixture-policy',revision:13,contentHash:'c'.repeat(64)},
   sourceHeadVersion:13,budgetRef:s.sourcePolicy.budgetRevisionRef,providerRef:s.sourcePolicy.developmentCostAuthorization.provider,
   sourcePolicy:s.sourcePolicy,sourceBudget:s.sourceBudget,sourceProvider:s.sourceProvider,targetDraft:draft,targetActive:target,
   approvalSlot:slot,contract:{schemaVersion:1,tenant:s.tenant,sourcePolicy:s.sourcePolicy,targetPolicy:draft,
    expectedHeadVersion:13,makerSubject:maker,checkerSubject:human},contractHash:'a'.repeat(64),request,requestHash:'e'.repeat(64)};
  return {schemaVersion:'aos.budget-policy-renewal.gateway-operation/v1',operation:'propose',
   idempotencyKey:request.idempotencyKey,requestHash:proposal.requestHash,state:'prepared',approvalVerified:false,activationEligible:false,
   recoveryPath:'/v1/aip/budget-policy-renewal/requests/propose/unit-propose',
   receipt:{status:'prepared',operation:'propose',requestHash:proposal.requestHash,proposalId:'renewal-proposal-unit',
    proposalHash:'f'.repeat(64),targetActiveHash:'1'.repeat(64),targetDraft:draft,proposal,activationEligible:false}};
 }

 function decisionFixture(revoke=false): any {
  const b=prepared(),op=revoke?'revoke':'decide',key=revoke?'unit-revoke':'unit-decision';
  const c={schemaVersion:1,orgId:'org-org',projectId:'dev-project',idempotencyKey:key,
   proposalId:b.receipt.proposalId,proposalHash:b.receipt.proposalHash,...(revoke?
    {decisionId:'renewal-decision-unit',decisionHash:'2'.repeat(64),reasonCode:'approval_withdrawn'}:
    {targetActiveHash:b.receipt.targetActiveHash,decision:'approved'})};
  const payload={proposalId:c.proposalId,proposalHash:c.proposalHash,targetActiveHash:b.receipt.targetActiveHash,
   actorSubject:'6f31cfdc-a26c-4f1f-ad6b-95a8559cc657',decision:revoke?'revoked':'approved',command:c,
   issuerReceiptId:'renewal-'+op+'-unit',expiresAt:command().effectiveUntil,...(revoke?
    {originalDecisionId:'renewal-decision-unit',originalDecisionHash:'2'.repeat(64),reasonCode:'approval_withdrawn'}:{})};
  return {...b,operation:op,idempotencyKey:key,state:'observed',recoveryPath:'/v1/aip/budget-policy-renewal/requests/'+op+'/'+key,
   receipt:{operation:op,status:'observed',requestHash:b.requestHash,proposalId:c.proposalId,proposalHash:c.proposalHash,
    decisionId:revoke?'renewal-revocation-unit':'renewal-decision-unit',decisionHash:'2'.repeat(64),decisionPayload:payload,
    targetActiveHash:b.receipt.targetActiveHash,actorSubject:payload.actorSubject,activationEligible:false}};
 }

 function publicationFixture(): any {
  const b=prepared(),d=decisionFixture(),key='unit-consume';
  const c={schemaVersion:1,orgId:'org-org',projectId:'dev-project',idempotencyKey:key,
   proposalId:d.receipt.proposalId,proposalHash:d.receipt.proposalHash,decisionId:d.receipt.decisionId,decisionHash:d.receipt.decisionHash};
  const policy={...b.receipt.proposal.targetActive,tenant:{orgId:'org-org',projectId:'dev-project'},contentHash:b.receipt.targetActiveHash,
   createdBy:'postgres-service:aos_budget_renewal_consumer_call',createdAt:'2026-10-16T00:00:00Z'};
  return {...b,operation:'consume',idempotencyKey:key,state:'observed',recoveryPath:'/v1/aip/budget-policy-renewal/requests/consume/'+key,
   receipt:{operation:'consume',status:'observed',requestHash:b.requestHash,proposalId:c.proposalId,proposalHash:c.proposalHash,
    decisionId:c.decisionId,decisionHash:c.decisionHash,command:c,policy,
    ref:{assetType:'BudgetPolicyRevision',assetId:policy.policyId,revision:14,contentHash:policy.contentHash},
    actorSubject:policy.createdBy,headVersionBefore:13,headVersionAfter:14,activationEligible:false}};
 }

 function chainFixture(): any { return {schemaVersion:'aos.budget-policy-renewal.gateway-chain/v1',proposalId:'renewal-proposal-unit',
  decisionIdempotencyKey:'unit-decision',consumeIdempotencyKey:'unit-consume',decision:decisionFixture(),publication:publicationFixture(),
  state:'published',approvalVerified:false,activationEligible:false,recoveryPath:'/v1/aip/budget-policy-renewal/chains/renewal-proposal-unit'}; }

describe('renewal explicit review and original recovery',()=>{
 let host:HTMLDivElement,root:Root,proposal:any,chain:any;
 beforeEach(()=>{
  window.history.replaceState({},'','/aip/capacity');setTenant({orgId:'org-org',projectId:'dev-project',subject:'6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'});
  host=document.createElement('div');document.body.append(host);root=createRoot(host);proposal=prepared();chain=chainFixture();
 });
 afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.restoreAllMocks();setAccessToken(null);setTenant({subject:undefined});});
 const button=(name:string)=>[...host.querySelectorAll('button')].find(n=>n.textContent===name)!;
 async function input(label:string,value:string){await act(async()=>{const n=host.querySelector<HTMLInputElement>(`[aria-label="${label}"]`)!;
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(n,value);n.dispatchEvent(new Event('input',{bubbles:true}));});}
 async function select(label:string,value:string){await act(async()=>{const n=host.querySelector<HTMLSelectElement>(`[aria-label="${label}"]`)!;n.value=value;n.dispatchEvent(new Event('change',{bubbles:true}));});}
 async function click(name:string){await act(async()=>button(name).click());}
 async function render(){await act(async()=>root.render(<BudgetPolicyRenewalReviewPanel/>));}
 function mockGet(source=providerFixture()){
  return vi.spyOn(transport,'apiGetAuthoritative').mockImplementation(async path=>{
   if(path.endsWith('/renewal-source'))return source;
   if(path.endsWith('/status'))return {schemaVersion:'aos.budget-policy-renewal.gateway-status/v1',tenant:source.tenant,
    writerEnabled:true,state:'configured',approvalVerified:false,activationEligible:false};
   if(path.includes('/requests/propose/'))return proposal;
   if(path.includes('/chains/'))return chain;
   throw new Error('unexpected synthetic GET');
  });
 }
 function mockPost(){return vi.spyOn(transport,'apiPostUnqueued').mockImplementation(async(path,raw)=>{
  expect(window.location.search).toContain('budgetRenewalAttempted=1');
  const c=raw as any;
  if(path.endsWith('/propose')){
   proposal=prepared();proposal.idempotencyKey=c.idempotencyKey;proposal.receipt.proposal.request=c;
   proposal.recoveryPath='/v1/aip/budget-policy-renewal/requests/propose/'+c.idempotencyKey;return proposal;
  }
  if(path.endsWith('/decide')||path.endsWith('/revoke')){
   const op=path.endsWith('/revoke')?'revoke':'decide',d=decisionFixture(op==='revoke');
   d.idempotencyKey=c.idempotencyKey;d.recoveryPath='/v1/aip/budget-policy-renewal/requests/'+op+'/'+c.idempotencyKey;
   d.receipt.decisionPayload.command=c;if(op==='decide')d.receipt.decisionPayload.decision=c.decision;return d;
  }
  if(path.endsWith('/consume')){const p=publicationFixture();p.idempotencyKey=c.idempotencyKey;p.receipt.command=c;
   p.recoveryPath='/v1/aip/budget-policy-renewal/requests/consume/'+c.idempotencyKey;return p;}
  if(path.endsWith('/decide-and-publish')){
   chain=chainFixture();chain.decisionIdempotencyKey=c.decisionCommand.idempotencyKey;chain.consumeIdempotencyKey=c.consumeIdempotencyKey;
   chain.decision.idempotencyKey=c.decisionCommand.idempotencyKey;chain.decision.receipt.decisionPayload.command=c.decisionCommand;
   chain.decision.recoveryPath='/v1/aip/budget-policy-renewal/requests/decide/'+c.decisionCommand.idempotencyKey;
   chain.publication.idempotencyKey=c.consumeIdempotencyKey;chain.publication.receipt.command.idempotencyKey=c.consumeIdempotencyKey;
   chain.publication.recoveryPath='/v1/aip/budget-policy-renewal/requests/consume/'+c.consumeIdempotencyKey;return chain;
  }
  if(path.endsWith('/continue'))return chain;
  throw new Error('unexpected synthetic POST');
 });}
 async function loadAndPrepare(){await input('续期策略 ID','fixture-policy');await click('读取续期来源');
  await input('续期开始时间',command().effectiveFrom);await input('续期结束时间',command().effectiveUntil);await click('准备续期提案');}
 it('has empty windows and no default decision or background requests',async()=>{
  const get=mockGet(),post=mockPost();await render();
  expect((host.querySelector('[aria-label="续期开始时间"]') as HTMLInputElement).value).toBe('');
  expect((host.querySelector('[aria-label="续期结束时间"]') as HTMLInputElement).value).toBe('');
  expect(button('准备续期提案').disabled).toBe(true);expect(get).not.toHaveBeenCalled();expect(post).not.toHaveBeenCalled();
 });
 it('shows complete source targets hashes and difference without editable amounts',async()=>{
  mockGet();const post=mockPost();await render();await loadAndPrepare();
  expect(post).toHaveBeenCalledTimes(1);expect(host.textContent).toContain('日上限 ¥10.00');expect(host.textContent).toContain('月上限 ¥200.00');
  expect(host.textContent).toContain('renewal-approval-unit');expect(host.textContent).toContain('unit-model');
  expect(host.textContent).toContain('候选第 14 版');expect(host.textContent).toContain('f'.repeat(64));
  expect(host.querySelector('[aria-label="完整续期待审内容"]')).not.toBeNull();
  expect((host.querySelector('[aria-label="续期复核选择"]') as HTMLSelectElement).value).toBe('');
  expect(button('提交续期复核').disabled).toBe(true);
 });
 it('does not resend unknown prepare after doubleclick changed fields or readonly query',async()=>{
  mockGet();const post=vi.spyOn(transport,'apiPostUnqueued').mockRejectedValue(new Error('lost response'));
  await render();await input('续期策略 ID','fixture-policy');await click('读取续期来源');
  await input('续期开始时间',command().effectiveFrom);await input('续期结束时间',command().effectiveUntil);
  await act(async()=>{button('准备续期提案').click();button('准备续期提案').click();});
  expect(post).toHaveBeenCalledTimes(1);expect(button('准备续期提案').disabled).toBe(true);
  await input('续期结束时间','2026-12-01T00:00:00Z');expect(button('准备续期提案').disabled).toBe(true);
  expect(window.location.search).toContain('budgetRenewalAttempted=1');
 });
 it('rejects only after explicit choice and never consumes on rejection or reading',async()=>{
  mockGet();const post=mockPost();await render();await loadAndPrepare();
  await select('续期复核选择','rejected');await click('提交续期复核');
  expect(post).toHaveBeenCalledTimes(2);expect(post.mock.calls[1][0]).toBe('/v1/aip/budget-policy-renewal/decide');
  expect(post.mock.calls[1][1]).toMatchObject({decision:'rejected'});
  expect(post.mock.calls.some(c=>c[0].endsWith('/consume'))).toBe(false);
 });
 it('approval alone never publishes and separate publication needs explicit confirmation',async()=>{
  mockGet();const post=mockPost();await render();await loadAndPrepare();
  await select('续期复核选择','approved');await click('提交续期复核');expect(post).toHaveBeenCalledTimes(2);
  expect(button('发布已批准续期').disabled).toBe(true);await select('续期发布确认','publish');await click('发布已批准续期');
  expect(post).toHaveBeenCalledTimes(3);expect(post.mock.calls[2][0]).toBe('/v1/aip/budget-policy-renewal/consume');
  expect(host.textContent).toContain('不代表模型或业务已经运行');
 });
 it('persists exact two-key combined chain and performs no followup automatic POST',async()=>{
  mockGet();const post=mockPost();await render();await loadAndPrepare();
  await select('续期复核选择','approve-and-publish');await click('批准并有界发布');
  expect(post).toHaveBeenCalledTimes(2);const body=post.mock.calls[1][1] as any;
  expect(post.mock.calls[1][0]).toBe('/v1/aip/budget-policy-renewal/decide-and-publish');
  expect(body.decisionCommand.idempotencyKey).not.toBe(body.consumeIdempotencyKey);
  expect(window.location.search).toContain('budgetRenewalKind=chain');expect(window.location.search).not.toContain('approved');
 });
 it('warns for an expired candidate at the server read time without another POST',async()=>{
  const source=providerFixture();source.evaluatedAt=command().effectiveUntil;
  saveRenewalReference({kind:'operation',operation:'propose',key:'unit-propose',proposalKey:'unit-propose'});
  mockGet(source);const post=mockPost();await render();
  expect(host.querySelector('[role="alert"]')?.textContent).toContain('候选续期窗口已过期');
  expect(host.textContent).toContain(source.evaluatedAt);
  expect(host.querySelector('[aria-label="完整续期待审内容"]')).not.toBeNull();
  expect(button('准备续期提案').disabled).toBe(true);expect(post).not.toHaveBeenCalled();
  expect(window.location.search).toContain('budgetRenewalKey=unit-propose');
 });
 it('does not label a future candidate expired or use the workstation clock',async()=>{
  const source=providerFixture();source.evaluatedAt='2026-10-15T23:59:59Z';
  vi.spyOn(Date,'now').mockReturnValue(Date.parse('2099-01-01T00:00:00Z'));
  saveRenewalReference({kind:'operation',operation:'propose',key:'unit-propose',proposalKey:'unit-propose'});
  mockGet(source);const post=mockPost();await render();
  expect(host.textContent).not.toContain('候选续期窗口已过期');expect(post).not.toHaveBeenCalled();
 });
 it('restores original proposal using GET only after reload and never generates another prepare',async()=>{
  saveRenewalReference({kind:'operation',operation:'propose',key:'unit-propose',proposalKey:'unit-propose'});
  const get=mockGet(),post=mockPost();await render();
  expect(get.mock.calls[0][0]).toBe('/v1/aip/budget-policy-renewal/requests/propose/unit-propose');
  expect(post).not.toHaveBeenCalled();expect(button('准备续期提案').disabled).toBe(true);expect(host.textContent).toContain('候选第 14 版');
 });
 it('freezes malformed URL and foreign identity even when a synthetic source reports ready',async()=>{
  window.history.replaceState({},'','/aip/capacity?budgetRenewalKind=broken');setTenant({subject:'another-user'});
  mockGet();const post=mockPost();await render();await input('续期策略 ID','fixture-policy');await click('读取续期来源');
  await input('续期开始时间',command().effectiveFrom);await input('续期结束时间',command().effectiveUntil);
  expect(button('准备续期提案').disabled).toBe(true);expect(post).not.toHaveBeenCalled();expect(host.textContent).toContain('恢复地址不完整');
 });
 it('clears choice on auth change and on source head drift while retaining original request',async()=>{
  const source=providerFixture();mockGet(source);const post=mockPost();await render();await loadAndPrepare();
  await select('续期复核选择','approved');const search=window.location.search;
  source.sourceHeadVersion=14;await click('读取续期来源');
  expect(button('提交续期复核').disabled).toBe(true);expect(window.location.search).toBe(search);
  await act(async()=>setAccessToken('synthetic-auth-change-only'));expect(button('准备续期提案').disabled).toBe(true);
  expect(post).toHaveBeenCalledTimes(1);
 });
 it('does not dispatch if saving the recovery address fails',async()=>{
  mockGet();const post=mockPost();await render();await input('续期策略 ID','fixture-policy');await click('读取续期来源');
  await input('续期开始时间',command().effectiveFrom);await input('续期结束时间',command().effectiveUntil);
  vi.spyOn(window.history,'replaceState').mockImplementation(()=>{throw new Error('history unavailable');});
  await click('准备续期提案');expect(post).not.toHaveBeenCalled();expect(button('准备续期提案').disabled).toBe(true);
 });
 it('keeps malformed or out-of-budget windows unattempted so they can be corrected',async()=>{
  mockGet();const post=mockPost();await render();await input('续期策略 ID','fixture-policy');await click('读取续期来源');
  await input('续期开始时间','2026-10-16T00:00:00');await input('续期结束时间','2028-01-01T00:00:00Z');
  expect(button('准备续期提案').disabled).toBe(true);expect(window.location.search).toBe('');
  await input('续期开始时间',command().effectiveFrom);await input('续期结束时间',command().effectiveUntil);
  expect(button('准备续期提案').disabled).toBe(false);expect(post).not.toHaveBeenCalled();
 });
 it('restores known-not-attempted chain without POST and continues only its existing keys once',async()=>{
  chain.state='publication-not-attempted';chain.publication=null;
  saveRenewalReference({kind:'chain',proposalId:chain.proposalId,decisionKey:'unit-decision',consumeKey:'unit-consume',proposalKey:'unit-propose'});
  mockGet();const post=mockPost();await render();expect(post).not.toHaveBeenCalled();
  expect(button('继续原续期请求').disabled).toBe(true);
  await select('续期继续确认','continue');await click('继续原续期请求');
  expect(post).toHaveBeenCalledTimes(1);expect(post).toHaveBeenCalledWith('/v1/aip/budget-policy-renewal/chains/renewal-proposal-unit/continue',
   {decisionIdempotencyKey:'unit-decision'},{});
  await select('续期继续确认','continue');expect(button('继续原续期请求').disabled).toBe(true);
 });
 it('keeps restored unknown chain query-only even with an apparent previous approval',async()=>{
  chain.state='unknown';chain.publication=null;
  saveRenewalReference({kind:'chain',proposalId:chain.proposalId,decisionKey:'unit-decision',consumeKey:'unit-consume',proposalKey:'unit-propose'});
  mockGet();const post=mockPost();await render();await select('续期继续确认','continue');
  expect(button('继续原续期请求').disabled).toBe(true);
  expect(button('准备续期提案').disabled).toBe(true);expect(button('提交续期复核').disabled).toBe(true);
  expect(button('撤销续期批准').disabled).toBe(true);expect(button('发布已批准续期').disabled).toBe(true);expect(post).not.toHaveBeenCalled();
 });
 it('requires a reason for revocation and does not label it as rollback or new publication',async()=>{
  mockGet();const post=mockPost();await render();await loadAndPrepare();
  await select('续期复核选择','approved');await click('提交续期复核');
  expect(button('撤销续期批准').disabled).toBe(true);await select('续期撤销原因','approval_withdrawn');await click('撤销续期批准');
  expect(post).toHaveBeenCalledTimes(3);expect(post.mock.calls[2][0]).toBe('/v1/aip/budget-policy-renewal/revoke');
  expect(post.mock.calls[2][1]).toMatchObject({decisionId:'renewal-decision-unit',decisionHash:'2'.repeat(64),reasonCode:'approval_withdrawn'});
  expect(host.textContent).toContain('不会回滚已发布策略');expect(post.mock.calls.some(c=>c[0].endsWith('/consume'))).toBe(false);
 });
 it('clears stale choice on same-tenant token changes and discards pending prepare response',async()=>{
  mockGet();let finish!:(v:unknown)=>void;
  const post=vi.spyOn(transport,'apiPostUnqueued').mockImplementation(async(_path,raw)=>{
   const c=raw as any;proposal.idempotencyKey=c.idempotencyKey;proposal.receipt.proposal.request=c;
   proposal.recoveryPath='/v1/aip/budget-policy-renewal/requests/propose/'+c.idempotencyKey;
   return new Promise(resolve=>{finish=resolve;});
  });
  await render();await input('续期策略 ID','fixture-policy');await click('读取续期来源');
  await input('续期开始时间',command().effectiveFrom);await input('续期结束时间',command().effectiveUntil);
  await act(async()=>button('准备续期提案').click());await act(async()=>setAccessToken('synthetic-epoch-change'));
  await act(async()=>finish(proposal));expect(host.textContent).not.toContain('候选第 14 版');
  expect(post).toHaveBeenCalledTimes(1);expect(window.location.search).toContain('budgetRenewalAttempted=1');
 });
 it('never enables mutation for a foreign subject even with well-formed synthetic ready data',async()=>{
  setTenant({subject:'another-subject'});mockGet();const post=mockPost();await render();
  await input('续期策略 ID','fixture-policy');await click('读取续期来源');await input('续期开始时间',command().effectiveFrom);await input('续期结束时间',command().effectiveUntil);
  expect(button('准备续期提案').disabled).toBe(true);expect(post).not.toHaveBeenCalled();
 });
 it('does not let a cached approval enable publication after the latest original query becomes unknown',async()=>{
  const get=mockGet();const post=mockPost();await render();await loadAndPrepare();
  await select('续期复核选择','approved');await click('提交续期复核');
  const c=post.mock.calls[1][1] as any;
  get.mockImplementation(async path=>{
   if(path.includes('/requests/propose/'))return proposal;
   if(path.includes('/requests/decide/'))return {schemaVersion:'aos.budget-policy-renewal.gateway-operation/v1',operation:'decide',
    idempotencyKey:c.idempotencyKey,requestHash:'e'.repeat(64),approvalVerified:false,activationEligible:false,state:'unknown',receipt:null,
    recoveryPath:'/v1/aip/budget-policy-renewal/requests/decide/'+c.idempotencyKey};
   if(path.endsWith('/renewal-source'))return providerFixture();
   return {schemaVersion:'aos.budget-policy-renewal.gateway-status/v1',tenant:providerFixture().tenant,
    writerEnabled:true,state:'configured',approvalVerified:false,activationEligible:false};
  });
  await click('查询续期原请求');await select('续期发布确认','publish');
  expect(button('发布已批准续期').disabled).toBe(true);expect(post).toHaveBeenCalledTimes(2);
 });
 it('does not start another request when a published observation lacks its complete original proposal',async()=>{
  saveRenewalReference({kind:'chain',proposalId:chain.proposalId,decisionKey:'unit-decision',consumeKey:'unit-consume',proposalKey:'unit-propose'});
  proposal={...proposal,state:'unknown',receipt:null};mockGet();const post=mockPost();await render();
  expect(host.querySelector('[aria-label="完整续期待审内容"]')).toBeNull();
  expect([...host.querySelectorAll('button')].some(n=>n.textContent==='开始另一份续期申请')).toBe(false);
  expect(post).not.toHaveBeenCalled();
 });
 it('does not continue a cached unattempted publication chain after its approval was explicitly revoked',async()=>{
  chain.state='publication-not-attempted';chain.publication=null;
  saveRenewalReference({kind:'chain',proposalId:chain.proposalId,decisionKey:'unit-decision',consumeKey:'unit-consume',proposalKey:'unit-propose'});
  mockGet();const post=mockPost();await render();
  await select('续期撤销原因','approval_withdrawn');await click('撤销续期批准');
  await select('续期继续确认','continue');expect(button('继续原续期请求').disabled).toBe(true);expect(post).toHaveBeenCalledTimes(1);
 });
});
