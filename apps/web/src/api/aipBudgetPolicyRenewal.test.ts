// Pure response/request unit fixtures, never real identity or budget consent.
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiGetAuthoritative, apiPostUnqueued } from './client';
import { getTenant, getAuthRevision } from './tenant';
import { getApiBase } from './apiBase';
import { parseRenewalSource, readRenewalSource, parseRenewalCommand, parseRenewalStatus,
  parseRenewalOperation, parseRenewalChain, parseRenewalHistory, postRenewalOperation,
  readRenewalOperation, readRenewalStatus, readRenewalChain, readRenewalHistory,
  postRenewalDecisionAndPublish, continueRenewalChain, assertRenewalPreparedSource,
  assertRenewalDecisionProposal, assertRenewalPublicationProposal, restoreRenewalReference,
  saveRenewalReference, readRenewalRecovery, clearRenewalReference, renewalTargetWindow } from './aipBudgetPolicyRenewal';
vi.mock('./client', () => ({ apiGetAuthoritative: vi.fn(), apiPostUnqueued: vi.fn() }));
vi.mock('./tenant', () => ({ getTenant: vi.fn(), getAuthRevision: vi.fn() }));
vi.mock('./apiBase', () => ({ getApiBase: vi.fn() }));
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
beforeEach(() => { vi.resetAllMocks(); vi.mocked(getApiBase).mockReturnValue('/api'); vi.mocked(getAuthRevision).mockReturnValue(0); vi.mocked(getTenant).mockReturnValue({orgId:'org-org',projectId:'dev-project',workspaceName:'默认工作区',subject:'unit-fixture-only',roles:['unit-role']}); });
describe('renewal source readonly parsing', () => {
 it('keeps the old active policy expiry separate from effective Budget and CAS head', () => {
  const body=fixture(); body.sourceHeadVersion=17;
  const parsed=parseRenewalSource(body,'fixture-policy');
  expect(parsed.sourcePolicy.revision).toBe(13); expect(parsed.sourceHeadVersion).toBe(17);
  expect(parsed.sourceWindow).toBe('expired'); expect(parsed.budgetWindow).toBe('effective');
  expect(parsed.sourceBudget?.dailyLimitMinor).toBe(1000); expect(parsed.state).toBe('blocked');
  expect(parsed.approvalVerified).toBe(false); expect(parsed.activationEligible).toBe(false);
 });
 it.each(['activationEligible','approvalVerified'])('rejects promoted or coerced %s', field => {
  for(const value of [true,0,'false']) {const b=fixture();b[field]=value;expect(()=>parseRenewalSource(b,'fixture-policy')).toThrow();}
 });
 it.each(['head','money','hash','unknown','tenant','id','date','window','ready','blockers','unsafe-revision'])('rejects malformed %s', kind=>{
  const b=fixture();
  if(kind==='head')b.sourceHeadVersion=true;
  if(kind==='money')b.sourceBudget.dailyLimitMinor=Number.MAX_SAFE_INTEGER+1;
  if(kind==='hash')b.sourcePolicy.contentHash='bad';
  if(kind==='unknown')b.sourcePolicy.actor='forged';
  if(kind==='tenant')b.currentBudget.tenant.projectId='other';
  if(kind==='id')b.sourcePolicy.policyId='other-policy';
  if(kind==='date')b.evaluatedAt='2026-02-30T00:00:00Z';
  if(kind==='window')b.sourceWindow='effective';
  if(kind==='ready'){b.state='ready';b.blockers=[];}
  if(kind==='blockers')b.blockers=[];
  if(kind==='unsafe-revision')b.sourcePolicy.revision=Number.MAX_SAFE_INTEGER+1;
  expect(()=>parseRenewalSource(b,'fixture-policy')).toThrow();
 });
 it('preserves a truthful missing dependency without manufacturing a zero object',()=>{
  const b=fixture();b.sourceBudget=null;b.currentBudget=null;b.budgetWindow='unknown';
  b.blockers=['RENEWAL_SOURCE_BUDGET_MISSING','RENEWAL_CURRENT_BUDGET_MISSING','RENEWAL_SOURCE_COST_AUTHORIZATION_MISSING'];
  const parsed=parseRenewalSource(b,'fixture-policy');expect(parsed.sourceBudget).toBeNull();expect(parsed.currentBudget).toBeNull();
 });
 it('preserves blocked exact/current drift for inspection',()=>{
  const b=fixture();b.currentBudget.revision=2;b.blockers.unshift('RENEWAL_CURRENT_BUDGET_CHANGED');
  expect(parseRenewalSource(b,'fixture-policy').currentBudget?.revision).toBe(2);
 });
 it('uses server microsecond clock when classifying a window',()=>{
  const b=fixture();b.evaluatedAt='2026-09-25T00:00:00.000001Z';b.sourcePolicy.effectiveUntil='2026-09-25T00:00:00.000002Z';b.sourceWindow='effective';
  expect(parseRenewalSource(b,'fixture-policy').sourceWindow).toBe('effective');
 });
 it('reads only the original exact source GET',async()=>{
  vi.mocked(apiGetAuthoritative).mockResolvedValue(fixture());await readRenewalSource('fixture-policy');
  expect(apiGetAuthoritative).toHaveBeenCalledTimes(1);expect(apiGetAuthoritative).toHaveBeenCalledWith('/v1/aip/model-governance-policies/budgets/fixture-policy/renewal-source');
 });
 it('rejects invalid or changed tenant before network and response acceptance',async()=>{
  vi.mocked(getTenant).mockReturnValue({orgId:'dev-org',projectId:'dev-project',workspaceName:'隔离fixture'});
  await expect(readRenewalSource('fixture-policy')).rejects.toThrow();expect(apiGetAuthoritative).not.toHaveBeenCalled();
  expect(()=>parseRenewalSource(fixture(),'fixture-policy')).toThrow();
 });
 it('rejects a late response after the current tenant changes',async()=>{
  let finish!:(value:unknown)=>void;
  vi.mocked(apiGetAuthoritative).mockReturnValue(new Promise(resolve=>{finish=resolve;}));
  const pending=readRenewalSource('fixture-policy');
  vi.mocked(getTenant).mockReturnValue({orgId:'org-org',projectId:'other',workspaceName:'changed'});
  finish(fixture());await expect(pending).rejects.toThrow();expect(apiGetAuthoritative).toHaveBeenCalledTimes(1);
 });
 it.each(['../policy','policy?revision=1','has space','中文策略','p'.repeat(201)])('rejects unsafe source id before network: %s',async id=>{
  await expect(readRenewalSource(id)).rejects.toThrow();expect(apiGetAuthoritative).not.toHaveBeenCalled();
 });
 it.each(['2026-02-29T00:00:00Z','2026-10-16T24:00:00Z','2026-10-16T00:00:00+24:00','2026-10-16T00:00:00'])('rejects malformed aware time %s',value=>{
  const b=fixture();b.evaluatedAt=value;expect(()=>parseRenewalSource(b,'fixture-policy')).toThrow();
 });
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
 it('preserves complete Provider and cost metadata while ready remains nonauthorizing',()=>{
  const b=providerFixture(),parsed=parseRenewalSource(b,'fixture-policy');
  expect(parsed.sourceProvider?.secretRef).toBe('vault://unit-reference-not-a-credential');
  expect(parsed.sourcePolicy.developmentCostAuthorization?.providerModelId).toBe('unit-model');
  expect(parsed.state).toBe('ready');expect(parsed.activationEligible).toBe(false);expect(parsed.approvalVerified).toBe(false);
 });
 it('shows a blocked current Provider drift without fabricating a matching reference',()=>{
  const b=providerFixture();b.currentProvider.revision=2;b.currentProvider.contentHash='e'.repeat(64);
  b.state='blocked';b.blockers=['RENEWAL_CURRENT_PROVIDER_CHANGED'];
  expect(parseRenewalSource(b,'fixture-policy').currentProvider?.revision).toBe(2);
 });
 it.each(['tenant','secret','extra','authorization','ready-drift','ready-missing'])('rejects malformed Provider %s',kind=>{
  const b=providerFixture();
  if(kind==='tenant')b.sourceProvider.tenant={orgId:'dev-org',projectId:'dev-project'};
  if(kind==='secret')b.sourceProvider.secretRef='plaintext-unit-fixture';
  if(kind==='extra')b.sourceProvider.endpointProfile.apiKey=''; // Forbidden even when empty.
  if(kind==='authorization')b.sourcePolicy.developmentCostAuthorization.approvalRef='other';
  if(kind==='ready-drift')b.currentProvider.revision=2;
  if(kind==='ready-missing')b.sourceProvider=null;
  expect(()=>parseRenewalSource(b,'fixture-policy')).toThrow();
 });

 // Synthetic SQL-shaped grammar fixtures: these hashes are opaque unit strings,
 // never native receipts, financial authority, real identities or user consent.
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
 it('accepts a complete SQL-shaped proposal without adding target Owner metadata or promoting permission',()=>{
  const b=prepared(),parsed=parseRenewalOperation(b,'propose','unit-propose',command());
  expect(parsed.receipt).toEqual(b.receipt);expect(parsed.activationEligible).toBe(false);
  expect(Object.keys(b.receipt.proposal.targetActive)).not.toContain('contentHash');
 });
 it.each(['amount','owner','model','provider','revision','zero-price','window','budget-bound','source-ref','slot',
  'contract','request','hash','metadata','checker','extra'])('rejects prepared %s mismatch',kind=>{
   const b=prepared(),p=b.receipt.proposal;
   if(kind==='amount')p.sourceBudget.monthlyLimitMinor=Number.MAX_SAFE_INTEGER+1;
   if(kind==='owner')p.targetActive.owner='different-owner';
   if(kind==='model')p.targetActive.developmentCostAuthorization.providerModelId='different-model';
   if(kind==='provider')p.providerRef={...p.providerRef,revision:2};
   if(kind==='revision')p.targetActive.revision=15;
   if(kind==='zero-price')p.targetActive.allowZeroPrice=true;
   if(kind==='window')p.targetActive.effectiveFrom='2026-09-01T00:00:00Z';
   if(kind==='budget-bound')p.request.effectiveUntil='2028-01-01T00:00:00Z';
   if(kind==='source-ref')p.sourceRef={...p.sourceRef,revision:12};
   if(kind==='slot')p.approvalSlot=p.sourcePolicy.approvalRef;
   if(kind==='contract')p.contract={...p.contract,expectedHeadVersion:12};
   if(kind==='request')p.request={...p.request,expectedSourceHash:'9'.repeat(64)};
   if(kind==='hash')b.receipt.requestHash='9'.repeat(64);
   if(kind==='metadata')p.targetActive.contentHash='9'.repeat(64);
   if(kind==='checker')p.checkerSubject='another-person';
   if(kind==='extra')p.token='must-not-be-accepted';
   expect(()=>parseRenewalOperation(b,'propose','unit-propose')).toThrow();
 });
 it.each(['actor','target','key','version','tenant','time'])('rejects unsafe command %s before network',kind=>{
  const c=command();if(kind==='actor')c.actorSubject='forged';if(kind==='target')c.targetBody={};
  if(kind==='key')c.idempotencyKey='../new';if(kind==='version')c.schemaVersion=true;
  if(kind==='tenant')c.orgId='dev-org';if(kind==='time')c.effectiveUntil='2026-10-15T00:00:00Z';
  expect(()=>parseRenewalCommand('propose',c)).toThrow();
 });
 it('keeps unknown and unresolved truthful and limits recovery to original exact request',()=>{
  const b=prepared();b.state='unknown';b.receipt=null;
  expect(parseRenewalOperation(b,'propose','unit-propose').receipt).toBeNull();
  b.state='unresolved';b.receipt={operation:'propose',requestHash:b.requestHash,status:'unresolved',activationEligible:false};
  expect(parseRenewalOperation(b,'propose','unit-propose').state).toBe('unresolved');
  b.recoveryPath='https://evil.invalid';expect(()=>parseRenewalOperation(b,'propose','unit-propose')).toThrow();
 });
 it('requires exact status flags and writer observation without approval promotion',()=>{
  const s={schemaVersion:'aos.budget-policy-renewal.gateway-status/v1',tenant:{orgId:'org-org',projectId:'dev-project'},
   writerEnabled:false,state:'closed',approvalVerified:false,activationEligible:false};
  expect(parseRenewalStatus(s).state).toBe('closed');
  expect(()=>parseRenewalStatus({...s,writerEnabled:true})).toThrow();
  expect(()=>parseRenewalStatus({...s,approvalVerified:true})).toThrow();
 });
 it('does not treat an empty not-attempted chain as published and requires distinct keys',()=>{
  const c={schemaVersion:'aos.budget-policy-renewal.gateway-chain/v1',proposalId:'renewal-proposal-unit',
   decisionIdempotencyKey:'unit-decision',consumeIdempotencyKey:'unit-consume',decision:null,publication:null,
   state:'decision-not-attempted',approvalVerified:false,activationEligible:false,
   recoveryPath:'/v1/aip/budget-policy-renewal/chains/renewal-proposal-unit'};
  expect(parseRenewalChain(c,'renewal-proposal-unit').state).toBe('decision-not-attempted');
  expect(()=>parseRenewalChain({...c,state:'published'},'renewal-proposal-unit')).toThrow();
  expect(()=>parseRenewalChain({...c,consumeIdempotencyKey:'unit-decision'},'renewal-proposal-unit')).toThrow();
 });
 it('bounds history and original next page without inventing chronology',()=>{
  const h={schemaVersion:'aos.budget-policy-renewal.gateway-history/v1',items:[prepared()],nextPage:5,approvalVerified:false,activationEligible:false};
  expect(parseRenewalHistory(h).items).toHaveLength(1);
  expect(()=>parseRenewalHistory({...h,nextPage:1})).toThrow();
  expect(()=>parseRenewalHistory({...h,items:Array(6).fill(prepared())})).toThrow();
 });
 it('uses one unqueued command submission and original-key GET only for recovery',async()=>{
  vi.mocked(apiPostUnqueued).mockResolvedValue(prepared());await postRenewalOperation('propose',command());
  expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
  expect(apiPostUnqueued).toHaveBeenCalledWith('/v1/aip/budget-policy-renewal/propose',command(),{});
  vi.mocked(apiGetAuthoritative).mockResolvedValue(prepared());await readRenewalOperation('propose','unit-propose');
  expect(apiGetAuthoritative).toHaveBeenCalledTimes(1);
  expect(apiGetAuthoritative).toHaveBeenCalledWith('/v1/aip/budget-policy-renewal/requests/propose/unit-propose');
 });
 it('rejects late auth changes and never retries a failed submission',async()=>{
  let finish!:(value:unknown)=>void;vi.mocked(apiPostUnqueued).mockReturnValue(new Promise(r=>{finish=r;}));
  const pending=postRenewalOperation('propose',command());vi.mocked(getAuthRevision).mockReturnValue(1);finish(prepared());
  await expect(pending).rejects.toThrow();expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
  vi.mocked(apiPostUnqueued).mockRejectedValue(new Error('connection lost'));
  await expect(postRenewalOperation('propose',command())).rejects.toThrow('connection lost');
  expect(apiPostUnqueued).toHaveBeenCalledTimes(2);
 });
 it('accepts server UTC normalization of an explicitly supplied timezone without changing its instant',()=>{
  const expected=command();expected.effectiveFrom='2026-10-16T08:00:00+08:00';
  expect(parseRenewalOperation(prepared(),'propose','unit-propose',expected).state).toBe('prepared');
  expected.effectiveFrom='2026-10-16T09:00:00+08:00';
  expect(()=>parseRenewalOperation(prepared(),'propose','unit-propose',expected)).toThrow();
 });
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
 it.each(['decide','revoke','consume'] as const)('accepts complete native-shaped %s observations as nonauthorizing',op=>{
  const b=op==='consume'?publicationFixture():decisionFixture(op==='revoke');
  expect(parseRenewalOperation(b,op,b.idempotencyKey).receipt).toEqual(b.receipt);
 });
 it.each(['actor','decision','proposal','target','key','expiry','extra'])('rejects issuer %s mismatch',kind=>{
  const b=decisionFixture(),p=b.receipt.decisionPayload;
  if(kind==='actor')p.actorSubject='fake-person';if(kind==='decision')p.decision='rejected';
  if(kind==='proposal')p.proposalHash='3'.repeat(64);if(kind==='target')p.targetActiveHash='3'.repeat(64);
  if(kind==='key')p.command.idempotencyKey='new-key';if(kind==='expiry')p.expiresAt='2026-02-30T00:00:00Z';
  if(kind==='extra')p.token='forbidden';
  expect(()=>parseRenewalOperation(b,'decide','unit-decision')).toThrow();
 });
 it.each(['reason','original-id','original-hash'])('rejects revoked %s mismatch',kind=>{
  const b=decisionFixture(true),p=b.receipt.decisionPayload;
  if(kind==='reason')p.reasonCode='scope_changed';if(kind==='original-id')p.originalDecisionId='other';
  if(kind==='original-hash')p.originalDecisionHash='3'.repeat(64);
  expect(()=>parseRenewalOperation(b,'revoke','unit-revoke')).toThrow();
 });
 it.each(['head','actor','reference','policy-scope','command','extra'])('rejects publication %s mismatch',kind=>{
  const b=publicationFixture(),p=b.receipt;
  if(kind==='head')p.headVersionAfter=15;if(kind==='actor')p.actorSubject='wrong';
  if(kind==='reference')p.ref.revision=15;if(kind==='policy-scope')p.policy.tenant.orgId='dev-org';
  if(kind==='command')p.command.decisionHash='3'.repeat(64);if(kind==='extra')p.privateConfig='forbidden';
  expect(()=>parseRenewalOperation(b,'consume','unit-consume')).toThrow();
 });
 function chainFixture(): any { return {schemaVersion:'aos.budget-policy-renewal.gateway-chain/v1',proposalId:'renewal-proposal-unit',
  decisionIdempotencyKey:'unit-decision',consumeIdempotencyKey:'unit-consume',decision:decisionFixture(),publication:publicationFixture(),
  state:'published',approvalVerified:false,activationEligible:false,recoveryPath:'/v1/aip/budget-policy-renewal/chains/renewal-proposal-unit'}; }
 it('accepts a fully linked historical chain without granting runtime permission',()=>{
  expect(parseRenewalChain(chainFixture(),'renewal-proposal-unit').state).toBe('published');
 });
 it.each(['decision-hash','different-proposal','rejected','not-observed','missing','unknown-published'])('rejects chain %s mismatch',kind=>{
  const b=chainFixture();
  if(kind==='decision-hash')b.decision.receipt.decisionHash='3'.repeat(64);
  if(kind==='different-proposal'){b.publication.receipt.proposalId='other';b.publication.receipt.command.proposalId='other';}
  if(kind==='rejected'){b.decision.receipt.decisionPayload.decision='rejected';b.decision.receipt.decisionPayload.command.decision='rejected';}
  if(kind==='not-observed'){b.decision.state='decided';b.decision.receipt.status='decided';}
  if(kind==='missing')b.decision=null;if(kind==='unknown-published')b.state='unknown';
  expect(()=>parseRenewalChain(b,'renewal-proposal-unit')).toThrow();
 });
 it.each(['+00:00', '.000000Z'])('links equivalent Provider metadata timestamps (%s) without changing source facts',suffix=>{
  const b=prepared().receipt,source=providerFixture();
  b.proposal.sourceProvider.createdAt=source.sourceProvider.createdAt.replace('Z',suffix);
  expect(()=>assertRenewalPreparedSource(b,source)).not.toThrow();
 });
 it.each(['createdAt','createdBy','contentHash','secretVersion'])('rejects actual Provider source drift in %s',field=>{
  const b=prepared().receipt,source=providerFixture();
  b.proposal.sourceProvider[field]=field==='createdAt' ? source.sourceProvider.createdAt.replace('Z','.000001+00:00') :
   field==='contentHash' ? '9'.repeat(64) : 'different-original-source';
  expect(()=>assertRenewalPreparedSource(b,source)).toThrow();
 });
 it.each([
  ['2026-10-31T23:59:59.999999Z','effective'],
  ['2026-11-01T00:00:00Z','expired'],
  ['2026-11-01T08:00:00.000000+08:00','expired'],
  ['2026-10-15T23:59:59.999999Z','not-yet-effective'],
 ] as const)('reports the candidate window at exact source time %s', (time,expected)=>{
  const source=providerFixture();source.evaluatedAt=time;
  expect(renewalTargetWindow(prepared().receipt,source)).toBe(expected);
 });
 it('does not label an unlinked source or malformed time as an expired candidate',()=>{
  const source=providerFixture();source.sourceHeadVersion=14;
  expect(()=>renewalTargetWindow(prepared().receipt,source)).toThrow();
  source.sourceHeadVersion=13;source.evaluatedAt='not-an-aware-time';
  expect(()=>renewalTargetWindow(prepared().receipt,source)).toThrow();
 });
 it('links the visible exact source decision and publication to one complete proposal',()=>{
  const b=prepared().receipt;
  expect(()=>assertRenewalPreparedSource(b,providerFixture())).not.toThrow();
  expect(()=>assertRenewalDecisionProposal(decisionFixture().receipt,b)).not.toThrow();
  expect(()=>assertRenewalPublicationProposal(publicationFixture().receipt,b)).not.toThrow();
  const changed=providerFixture();changed.sourceHeadVersion=14;
  expect(()=>assertRenewalPreparedSource(b,changed)).toThrow();
  const d=decisionFixture();d.receipt.decisionPayload.expiresAt='2026-11-02T00:00:00Z';
  expect(()=>assertRenewalDecisionProposal(d.receipt,b)).toThrow();
  const p=publicationFixture();p.receipt.policy.owner='different-owner';
  expect(()=>assertRenewalPublicationProposal(p.receipt,b)).toThrow();
 });
 it('does not coerce enum arrays into source lifecycle or a human decision',()=>{
  const s=fixture();s.sourcePolicy.lifecycle=['active'];expect(()=>parseRenewalSource(s,'fixture-policy')).toThrow();
  const c=decisionFixture().receipt.decisionPayload.command;c.decision=['approved'];
  expect(()=>parseRenewalCommand('decide',c)).toThrow();
 });
 it('makes only explicit chain POSTs and only GETs for status history and chain recovery',async()=>{
  const chain=chainFixture(),c=decisionFixture().receipt.decisionPayload.command;
  vi.mocked(apiPostUnqueued).mockResolvedValue(chain);
  await postRenewalDecisionAndPublish(c,'unit-consume');
  expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
  expect(apiPostUnqueued).toHaveBeenCalledWith('/v1/aip/budget-policy-renewal/decide-and-publish',
   {decisionCommand:c,consumeIdempotencyKey:'unit-consume'},{});
  vi.mocked(apiGetAuthoritative).mockResolvedValue(chain);await readRenewalChain('renewal-proposal-unit');
  vi.mocked(apiGetAuthoritative).mockResolvedValue({schemaVersion:'aos.budget-policy-renewal.gateway-status/v1',
   tenant:{orgId:'org-org',projectId:'dev-project'},writerEnabled:false,state:'closed',approvalVerified:false,activationEligible:false});
  await readRenewalStatus();
  vi.mocked(apiGetAuthoritative).mockResolvedValue({schemaVersion:'aos.budget-policy-renewal.gateway-history/v1',
   items:[],nextPage:null,approvalVerified:false,activationEligible:false});await readRenewalHistory(5);
  expect(vi.mocked(apiGetAuthoritative).mock.calls.map(c=>c[0])).toEqual([
   '/v1/aip/budget-policy-renewal/chains/renewal-proposal-unit','/v1/aip/budget-policy-renewal/status',
   '/v1/aip/budget-policy-renewal/requests/page/5']);
  expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
 });
 it('continues only known-not-attempted original chain and cannot substitute either key',async()=>{
  const b=chainFixture();b.state='publication-not-attempted';b.publication=null;
  vi.mocked(apiPostUnqueued).mockResolvedValue(chainFixture());
  await continueRenewalChain(b);
  expect(apiPostUnqueued).toHaveBeenCalledWith('/v1/aip/budget-policy-renewal/chains/renewal-proposal-unit/continue',
   {decisionIdempotencyKey:'unit-decision'},{});
  expect(()=>continueRenewalChain(chainFixture())).toThrow();
  const u=chainFixture();u.state='unknown';u.publication=null;
  expect(()=>continueRenewalChain(u)).toThrow();
  const wrong=chainFixture();wrong.consumeIdempotencyKey='replacement';wrong.publication.idempotencyKey='replacement';
  wrong.publication.recoveryPath='/v1/aip/budget-policy-renewal/requests/consume/replacement';wrong.publication.receipt.command.idempotencyKey='replacement';
  vi.mocked(apiPostUnqueued).mockResolvedValue(wrong);
  await expect(continueRenewalChain(b)).rejects.toThrow();expect(apiPostUnqueued).toHaveBeenCalledTimes(2);
 });
 it('rejects a rejected combined decision unsafe locator and invalid history before all network',()=>{
  const c=decisionFixture().receipt.decisionPayload.command;c.decision='rejected';
  expect(()=>postRenewalDecisionAndPublish(c,'unit-consume')).toThrow();
  expect(()=>readRenewalOperation('propose','../replacement')).toThrow();
  expect(()=>readRenewalChain('https://evil.invalid')).toThrow();
  expect(()=>readRenewalHistory(1)).toThrow();expect(apiGetAuthoritative).not.toHaveBeenCalled();
  expect(apiPostUnqueued).not.toHaveBeenCalled();
 });
 it('detaches command fields from form mutation and rejects late source identity changes',async()=>{
  let finish!:(value:unknown)=>void;
  vi.mocked(apiPostUnqueued).mockReturnValue(new Promise(r=>{finish=r;}));
  const c=command(),pending=postRenewalOperation('propose',c);c.expectedSourceRevision=999;
  finish(prepared());await expect(pending).resolves.toMatchObject({state:'prepared'});
  expect(vi.mocked(apiPostUnqueued).mock.calls[0][1]).toMatchObject({expectedSourceRevision:13});
  vi.mocked(apiGetAuthoritative).mockImplementation(async()=>{vi.mocked(getAuthRevision).mockReturnValue(2);return fixture();});
  await expect(readRenewalSource('fixture-policy')).rejects.toThrow();
 });
 it.each(['https://untrusted.invalid','http://127.0.0.1:18080','/other-api'])('blocks private calls under an overridden API base %s before network',async base=>{
  vi.mocked(getApiBase).mockReturnValue(base);
  vi.mocked(apiGetAuthoritative).mockResolvedValue({schemaVersion:'aos.budget-policy-renewal.gateway-status/v1',
   tenant:{orgId:'org-org',projectId:'dev-project'},writerEnabled:false,state:'closed',approvalVerified:false,activationEligible:false});
  vi.mocked(apiPostUnqueued).mockResolvedValue(prepared());
  await expect(readRenewalStatus()).rejects.toThrow();
  await expect(postRenewalOperation('propose',command())).rejects.toThrow();
  expect(apiGetAuthoritative).not.toHaveBeenCalled();expect(apiPostUnqueued).not.toHaveBeenCalled();
 });
 it('rejects a base change during an already dispatched request without another dispatch',async()=>{
  vi.mocked(apiPostUnqueued).mockImplementation(async()=>{vi.mocked(getApiBase).mockReturnValue('/changed');return prepared();});
  await expect(postRenewalOperation('propose',command())).rejects.toThrow();
  expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
 });
 it('stores only original bounded recovery locators before network and preserves other panels and hash',()=>{
  window.history.replaceState({},'', '/aip/capacity?budgetReviewRef=other&tab=usage#review');
  const ref={kind:'operation' as const,operation:'propose' as const,key:'unit-propose',proposalKey:'unit-propose'};
  saveRenewalReference(ref);
  expect(restoreRenewalReference(window.location.search)).toEqual({state:'ready',ref});
  expect(window.location.search).toContain('budgetRenewalAttempted=1');
  expect(window.location.search).toContain('budgetReviewRef=other');expect(window.location.hash).toBe('#review');
  expect(apiGetAuthoritative).not.toHaveBeenCalled();expect(apiPostUnqueued).not.toHaveBeenCalled();
  clearRenewalReference();expect(window.location.search).toBe('?budgetReviewRef=other&tab=usage');
 });
 it.each(['?budgetRenewalKind=operation','?budgetRenewalKind=operation&budgetRenewalKind=chain',
  '?budgetRenewalKind=operation&budgetRenewalOp=propose&budgetRenewalKey=../unsafe&budgetRenewalProposalKey=p&budgetRenewalAttempted=1',
  '?budgetRenewalKind=operation&budgetRenewalOp=propose&budgetRenewalKey=p&budgetRenewalProposalKey=other&budgetRenewalAttempted=1',
  '?budgetRenewalKind=operation&budgetRenewalOp=propose&budgetRenewalKey=p&budgetRenewalProposalKey=p&budgetRenewalAttempted=0',
  '?budgetRenewalSecret=x'])('freezes malformed reserved recovery URL %s instead of treating it as empty',query=>{
  expect(restoreRenewalReference(query).state).toBe('invalid');
 });
 it('restores absent parameters as none and exact two-key chain as ready',()=>{
  expect(restoreRenewalReference('?tab=usage')).toEqual({state:'none'});
  const ref={kind:'chain' as const,proposalId:'renewal-proposal-unit',decisionKey:'unit-decision',consumeKey:'unit-consume',proposalKey:'unit-propose'};
  saveRenewalReference(ref);expect(restoreRenewalReference(window.location.search)).toEqual({state:'ready',ref});
  expect(()=>saveRenewalReference({...ref,consumeKey:'unit-decision'})).toThrow();
 });
 it('reads original proposal and original chain only and checks all linked observations',async()=>{
  const ref={kind:'chain' as const,proposalId:'renewal-proposal-unit',decisionKey:'unit-decision',consumeKey:'unit-consume',proposalKey:'unit-propose'};
  vi.mocked(apiGetAuthoritative).mockImplementation(async path=>path.includes('/requests/propose/')?prepared():chainFixture());
  const restored=await readRenewalRecovery(ref);
  expect(restored.result).toMatchObject({state:'published'});expect(apiPostUnqueued).not.toHaveBeenCalled();
  expect(vi.mocked(apiGetAuthoritative).mock.calls.map(c=>c[0])).toEqual([
   '/v1/aip/budget-policy-renewal/requests/propose/unit-propose','/v1/aip/budget-policy-renewal/chains/renewal-proposal-unit']);
  const wrong=chainFixture();wrong.consumeIdempotencyKey='another';wrong.publication=null;wrong.state='publication-not-attempted';
  vi.mocked(apiGetAuthoritative).mockImplementation(async path=>path.includes('/requests/propose/')?prepared():wrong);
  await expect(readRenewalRecovery(ref)).rejects.toThrow();
 });
});
