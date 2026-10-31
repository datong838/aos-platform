import {parseWindowObservation, parseWindowGatewayStatus, parseWindowRequestIndex, readWindowGatewayStatus, listWindowRequests, inquireWindowRequest, submitWindowOperation, windowDecisionCommand, windowRevocationCommand, windowConsumeCommand, restoreWindowReference, saveWindowReference, formatWindowRiskMinor} from './aipBudgetPolicyWindow';
// Synthetic backend DTO/native command vectors, not PG, real OIDC or consent.
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {apiGetAuthoritative, apiPostUnqueued} from './client';
import {getTenant, getAuthRevision, tenantAuthHeaders} from './tenant';
import {getApiBase} from './apiBase';
import {parsePolicyWindowSource, readPolicyWindowSource, policyWindowProposalCommand} from './aipBudgetPolicyWindow';
vi.mock('./client',()=>({apiGetAuthoritative:vi.fn(),apiPostUnqueued:vi.fn()}));
vi.mock('./tenant',()=>({getTenant:vi.fn(),getAuthRevision:vi.fn(),tenantAuthHeaders:vi.fn()}));
vi.mock('./apiBase',()=>({getApiBase:vi.fn()}));
const sourceVector = {
  "schemaVersion": "aos.budget-policy-window.review-source/v1",
  "tenant": {
    "orgId": "org-org",
    "projectId": "dev-project"
  },
  "evaluatedAt": "2026-10-18T00:00:00Z",
  "parent": {
    "proposalId": "unit-proposal",
    "proposalHash": "567240939e22a176905b2ebd17f72404ff8742c8640792e6fbad354374d110e2",
    "proposal": {
      "schemaVersion": 1,
      "tenant": {
        "orgId": "org-org",
        "projectId": "dev-project"
      },
      "target": {
        "budgetId": "unit-budget",
        "revision": 2,
        "environment": "development",
        "currency": "CNY",
        "dailyLimitMinor": 50,
        "monthlyLimitMinor": 500,
        "alertThresholdPct": 80,
        "hardStop": true,
        "unknownUsageBehavior": "block",
        "effectiveFrom": "2026-10-01T00:00:00Z",
        "effectiveUntil": "2026-11-01T00:00:00Z",
        "owner": "6f31cfdc-a26c-4f1f-ad6b-95a8559cc657",
        "overBudgetApprover": "6f31cfdc-a26c-4f1f-ad6b-95a8559cc657",
        "lifecycle": "active"
      },
      "draftRevision": 1,
      "expectedHeadVersion": 2,
      "makerSubject": "unit-machine",
      "checkerSubject": "6f31cfdc-a26c-4f1f-ad6b-95a8559cc657",
      "basis": {
        "kind": "development_risk_proposal",
        "provider": {
          "assetType": "ProviderInstanceRevision",
          "assetId": "unit-provider",
          "revision": 1,
          "contentHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        },
        "providerModelId": "unit-model",
        "perRequestRiskMinor": 10,
        "totalRiskMinor": 100,
        "maxRequests": 10
      }
    },
    "decisionId": "unit-decision",
    "decision": "approved",
    "revoked": false
  },
  "consumption": {
    "receiptId": "budget-cost-consume-1ec2f0f5329cbc7f588164ed35ddcb3e4e4922f1c051c56b907e53ad55cf473e",
    "requestHash": "1ec2f0f5329cbc7f588164ed35ddcb3e4e4922f1c051c56b907e53ad55cf473e",
    "resultRef": {
      "resourceType": "BudgetRevision",
      "resourceId": "unit-budget",
      "revision": 2,
      "contentHash": "f21615b40e0c97b42f8e48248e8cc524f3dd941e8a9931580dcd3e5fb598055a",
      "proposalId": "unit-proposal",
      "proposalHash": "567240939e22a176905b2ebd17f72404ff8742c8640792e6fbad354374d110e2",
      "decisionId": "unit-decision",
      "receiptId": "budget-cost-consume-1ec2f0f5329cbc7f588164ed35ddcb3e4e4922f1c051c56b907e53ad55cf473e"
    },
    "createdBy": "unit-machine"
  },
  "sourceBudget": {
    "budgetId": "unit-budget",
    "revision": 2,
    "environment": "development",
    "currency": "CNY",
    "dailyLimitMinor": 50,
    "monthlyLimitMinor": 500,
    "alertThresholdPct": 80,
    "hardStop": true,
    "unknownUsageBehavior": "block",
    "effectiveFrom": "2026-10-01T00:00:00Z",
    "effectiveUntil": "2026-11-01T00:00:00Z",
    "owner": "6f31cfdc-a26c-4f1f-ad6b-95a8559cc657",
    "overBudgetApprover": "6f31cfdc-a26c-4f1f-ad6b-95a8559cc657",
    "lifecycle": "active",
    "tenant": {
      "orgId": "org-org",
      "projectId": "dev-project"
    },
    "contentHash": "f21615b40e0c97b42f8e48248e8cc524f3dd941e8a9931580dcd3e5fb598055a",
    "createdBy": "unit-machine",
    "createdAt": "2026-10-01T00:01:00Z"
  },
  "currentBudget": {
    "budgetId": "unit-budget",
    "revision": 2,
    "environment": "development",
    "currency": "CNY",
    "dailyLimitMinor": 50,
    "monthlyLimitMinor": 500,
    "alertThresholdPct": 80,
    "hardStop": true,
    "unknownUsageBehavior": "block",
    "effectiveFrom": "2026-10-01T00:00:00Z",
    "effectiveUntil": "2026-11-01T00:00:00Z",
    "owner": "6f31cfdc-a26c-4f1f-ad6b-95a8559cc657",
    "overBudgetApprover": "6f31cfdc-a26c-4f1f-ad6b-95a8559cc657",
    "lifecycle": "active",
    "tenant": {
      "orgId": "org-org",
      "projectId": "dev-project"
    },
    "contentHash": "f21615b40e0c97b42f8e48248e8cc524f3dd941e8a9931580dcd3e5fb598055a",
    "createdBy": "unit-machine",
    "createdAt": "2026-10-01T00:01:00Z"
  },
  "currentBudgetHeadVersion": 3,
  "sourceProvider": {
    "tenant": {
      "orgId": "org-org",
      "projectId": "dev-project"
    },
    "ref": {
      "assetType": "ProviderInstanceRevision",
      "assetId": "unit-provider",
      "revision": 1,
      "contentHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    },
    "lifecycle": "active"
  },
  "currentProvider": {
    "tenant": {
      "orgId": "org-org",
      "projectId": "dev-project"
    },
    "ref": {
      "assetType": "ProviderInstanceRevision",
      "assetId": "unit-provider",
      "revision": 1,
      "contentHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    },
    "lifecycle": "active"
  },
  "approvalVerified": false,
  "activationEligible": false,
  "nativeWriteAllowed": false,
  "runtimeAdmissionAllowed": false,
  "nativeParentVerification": "not-performed",
  "state": "observed",
  "blockers": []
};
const commandVector = {
  "schemaVersion": 1,
  "orgId": "org-org",
  "projectId": "dev-project",
  "idempotencyKey": "unit-window-proposal",
  "parentCostProposalId": "unit-proposal",
  "parentCostProposalHash": "567240939e22a176905b2ebd17f72404ff8742c8640792e6fbad354374d110e2",
  "parentCostDecisionId": "unit-decision",
  "parentConsumptionReceiptId": "budget-cost-consume-1ec2f0f5329cbc7f588164ed35ddcb3e4e4922f1c051c56b907e53ad55cf473e",
  "expectedBudgetRef": {
    "assetType": "BudgetRevision",
    "assetId": "unit-budget",
    "revision": 2,
    "contentHash": "f21615b40e0c97b42f8e48248e8cc524f3dd941e8a9931580dcd3e5fb598055a"
  },
  "expectedBudgetHeadVersion": 3,
  "expectedProviderRef": {
    "assetType": "ProviderInstanceRevision",
    "assetId": "unit-provider",
    "revision": 1,
    "contentHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "expectedProviderModelId": "unit-model",
  "effectiveFrom": "2026-10-18T00:00:00.000001Z",
  "effectiveUntil": "2026-10-20T00:00:00.000002Z"
};
const HUMAN='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657';
function fixture():any{return structuredClone(sourceVector);}
beforeEach(()=>{vi.resetAllMocks();vi.mocked(getTenant).mockReturnValue({orgId:'org-org',projectId:'dev-project',workspaceName:'unit',subject:HUMAN});vi.mocked(getAuthRevision).mockReturnValue(1);vi.mocked(getApiBase).mockReturnValue('/api');});
it('parses backend wire without turning observations into permission',()=>{
 const s=parsePolicyWindowSource(fixture(),'unit-proposal');expect(s.state).toBe('observed');
 expect(s.nativeParentVerification).toBe('not-performed');
 for(const field of ['approvalVerified','activationEligible','nativeWriteAllowed','runtimeAdmissionAllowed'] as const)expect(s[field]).toBe(false);
 expect(s.parent.proposal.basis.totalRiskMinor).toBe(100);expect(s).not.toHaveProperty('remainingMinor');expect(s.parent.proposal).not.toHaveProperty('accounts');
});
it.each(['approvalVerified','activationEligible','nativeWriteAllowed','runtimeAdmissionAllowed'])('rejects permission coercion %s',field=>{
 for(const value of [true,0,'false',null]){const s=fixture();s[field]=value;expect(()=>parsePolicyWindowSource(s,'unit-proposal')).toThrow();}
});
it.each(['legacy','extra','missing','tenant','checker','sameMaker','hash','providerKind','receiptActor','receiptLink','wrongId','unknownBlocker'])('rejects invalid linked source %s',change=>{
 const s=fixture();
 if(change==='legacy')s.schemaVersion='aos.budget-policy-renewal.review-source/v1';
 else if(change==='extra')s.availableMinor=0;
 else if(change==='missing')delete s.currentBudget;
 else if(change==='tenant')s.currentBudget.tenant.orgId='dev-org';
 else if(change==='checker')s.parent.proposal.checkerSubject='other';
 else if(change==='sameMaker')s.parent.proposal.makerSubject=HUMAN;
 else if(change==='hash')s.parent.proposalHash='NOT-A-HASH';
 else if(change==='providerKind')s.sourceProvider.ref.assetType='BudgetRevision';
 else if(change==='receiptActor')s.consumption.createdBy='other';
 else if(change==='receiptLink')s.consumption.resultRef.proposalHash='e'.repeat(64);
 else if(change==='wrongId')s.parent.proposalId='other';
 else{s.state='blocked';s.blockers=['UNKNOWN_AUTHORITY_READY'];}
 expect(()=>parsePolicyWindowSource(s,'unit-proposal')).toThrow();
});
it.each([0,true,'100',1.5,Number.MAX_SAFE_INTEGER+1,NaN,Infinity])('rejects unsafe risk %s',value=>{
 const s=fixture();s.parent.proposal.basis.totalRiskMinor=value;expect(()=>parsePolicyWindowSource(s,'unit-proposal')).toThrow();
});
it('retains missing receipt as blocked, never defaults or builds a command',()=>{
 const s=fixture();s.consumption=null;s.state='blocked';s.blockers=['WINDOW_PARENT_CONSUMPTION_NOT_OBSERVED'];
 const parsed=parsePolicyWindowSource(s,'unit-proposal');expect(parsed.consumption).toBeNull();
 expect(()=>policyWindowProposalCommand(parsed,'unit-key','2026-10-18T00:00:00Z','2026-10-20T00:00:00Z')).toThrow();
});
it('retains server opaque-hash drift as blocked without recomputing authority',()=>{
 const s=fixture();s.currentBudget.contentHash='e'.repeat(64);s.state='blocked';s.blockers=['WINDOW_CURRENT_BUDGET_CHANGED'];
 expect(parsePolicyWindowSource(s,'unit-proposal').state).toBe('blocked');
});
it('matches Python native wire golden vector including UTC microseconds',()=>{
 const s=parsePolicyWindowSource(fixture(),'unit-proposal');
 expect(policyWindowProposalCommand(s,'unit-window-proposal','2026-10-18T08:00:00.000001+08:00','2026-10-20T08:00:00.000002+08:00')).toEqual(commandVector);
});
it.each([['','2026-10-20T00:00:00Z'],['2026-10-18T00:00:00','2026-10-20T00:00:00Z'],
 ['2026-02-30T00:00:00Z','2026-10-20T00:00:00Z'],['2026-09-30T23:59:59.999999Z','2026-10-20T00:00:00Z'],
 ['2026-10-18T00:00:00Z','2026-11-01T00:00:00Z'],['2026-10-18T00:00:00.000001Z','2026-10-18T00:00:00.000001Z'],
 ['2026-10-18T00:00:00Z','2026-10-18T00:00:00Z']])('requires explicit valid interval %s to %s',(from,until)=>{
 const s=parsePolicyWindowSource(fixture(),'unit-proposal');expect(()=>policyWindowProposalCommand(s,'unit-key',from,until)).toThrow();
});
it('preserves one microsecond of child interval and parent remainder',()=>{
 const s=parsePolicyWindowSource(fixture(),'unit-proposal');
 expect(policyWindowProposalCommand(s,'unit-key','2026-10-31T23:59:59.999998Z','2026-10-31T23:59:59.999999Z').effectiveUntil).toBe('2026-10-31T23:59:59.999999Z');
});
it('revalidates nested mutation instead of accepting prior parsed shape as authority',()=>{
 const s=parsePolicyWindowSource(fixture(),'unit-proposal');s.parent.proposal.basis.totalRiskMinor=0;
 expect(()=>policyWindowProposalCommand(s,'unit-key','2026-10-18T00:00:00Z','2026-10-20T00:00:00Z')).toThrow();
});
it.each(['auth','tenant','subject','base'])('rejects stale context after %s change',change=>{
 const s=parsePolicyWindowSource(fixture(),'unit-proposal');
 if(change==='auth')vi.mocked(getAuthRevision).mockReturnValue(2);
 else if(change==='base')vi.mocked(getApiBase).mockReturnValue('http://unit-other.invalid');
 else vi.mocked(getTenant).mockReturnValue({orgId:change==='tenant'?'dev-org':'org-org',projectId:'dev-project',workspaceName:'unit',subject:change==='subject'?'other':HUMAN});
 expect(()=>policyWindowProposalCommand(s,'unit-key','2026-10-18T00:00:00Z','2026-10-20T00:00:00Z')).toThrow();
});
it('uses authoritative GET only and rejects a late auth response',async()=>{
 let resolve!:(value:unknown)=>void;vi.mocked(apiGetAuthoritative).mockReturnValue(new Promise(r=>{resolve=r;}));
 const pending=readPolicyWindowSource('unit-proposal');vi.mocked(getAuthRevision).mockReturnValue(2);resolve(fixture());
 await expect(pending).rejects.toThrow();expect(apiGetAuthoritative).toHaveBeenCalledWith('/v1/aip/budgets/cost-proposals/unit-proposal/policy-window-source');expect(apiPostUnqueued).not.toHaveBeenCalled();
});
it('rejects wrong subject or malformed ID before network',async()=>{
 await expect(readPolicyWindowSource(' leading')).rejects.toThrow();
 vi.mocked(getTenant).mockReturnValue({orgId:'org-org',projectId:'dev-project',workspaceName:'unit',subject:'other'});
 await expect(readPolicyWindowSource('unit-proposal')).rejects.toThrow();expect(apiGetAuthoritative).not.toHaveBeenCalled();
});

it('isolates parsed snapshots from later changes to the incoming response',()=>{
 const input=fixture(),s=parsePolicyWindowSource(input,'unit-proposal');
 input.parent.proposal.basis.totalRiskMinor=0;
 expect(policyWindowProposalCommand(s,'unit-key','2026-10-18T00:00:00Z','2026-10-20T00:00:00Z').parentCostProposalHash).toBe(sourceVector.parent.proposalHash);
});
it('reads a fresh independent source and does not send a mutation',async()=>{
 const input=fixture();vi.mocked(apiGetAuthoritative).mockResolvedValue(input);
 const s=await readPolicyWindowSource('unit-proposal');expect(s).not.toBe(input);
 expect(apiGetAuthoritative).toHaveBeenCalledTimes(1);expect(apiPostUnqueued).not.toHaveBeenCalled();
});
it.each(['tenant','base'])('rejects a late response after %s changes',async change=>{
 let resolve!:(value:unknown)=>void;vi.mocked(apiGetAuthoritative).mockReturnValue(new Promise(r=>{resolve=r;}));
 const pending=readPolicyWindowSource('unit-proposal');
 if(change==='base')vi.mocked(getApiBase).mockReturnValue('http://unit-other.invalid');
 else vi.mocked(getTenant).mockReturnValue({orgId:'dev-org',projectId:'dev-project',workspaceName:'unit',subject:HUMAN});
 resolve(fixture());await expect(pending).rejects.toThrow();expect(apiPostUnqueued).not.toHaveBeenCalled();
});
it('cannot turn an unobserved head or revoked parent into a display command',()=>{
 for(const change of ['head','revoked']){
  const input=fixture();input.state='blocked';
  if(change==='head'){input.currentBudgetHeadVersion=null;input.blockers=['WINDOW_PARENT_BUDGET_HEAD_CHANGED'];}
  else{input.parent.revoked=true;input.blockers=['WINDOW_PARENT_REVOKED'];}
  const s=parsePolicyWindowSource(input,'unit-proposal');
  expect(()=>policyWindowProposalCommand(s,'unit-key','2026-10-18T00:00:00Z','2026-10-20T00:00:00Z')).toThrow();
 }
});
it.each(['',' leading','key/other','键', 'x'.repeat(121)])('rejects non-native idempotency key %s',key=>{
 const s=parsePolicyWindowSource(fixture(),'unit-proposal');
 expect(()=>policyWindowProposalCommand(s,key,'2026-10-18T00:00:00Z','2026-10-20T00:00:00Z')).toThrow();
});

// Synthetic linked wire; static native validator only, not native PG or consent.
const nativeWire = {
  "propose": {
    "schemaVersion": "aos.budget-policy-window.gateway-observation/v1",
    "observation": {
      "schemaVersion": 1,
      "operation": "propose",
      "requestHash": "6f08708b3eaa32ce5a1db24c2c980184a708e66299594b0f1cbf57703102d2e5",
      "activationEligible": false,
      "result": {
        "status": "observed",
        "receipt": {
          "status": "prepared",
          "operation": "propose",
          "command": {
            "schemaVersion": 1,
            "orgId": "org-org",
            "projectId": "dev-project",
            "idempotencyKey": "unit-window-proposal",
            "parentCostProposalId": "unit-proposal",
            "parentCostProposalHash": "567240939e22a176905b2ebd17f72404ff8742c8640792e6fbad354374d110e2",
            "parentCostDecisionId": "unit-decision",
            "parentConsumptionReceiptId": "budget-cost-consume-1ec2f0f5329cbc7f588164ed35ddcb3e4e4922f1c051c56b907e53ad55cf473e",
            "expectedBudgetRef": {
              "assetType": "BudgetRevision",
              "assetId": "unit-budget",
              "revision": 2,
              "contentHash": "f21615b40e0c97b42f8e48248e8cc524f3dd941e8a9931580dcd3e5fb598055a"
            },
            "expectedBudgetHeadVersion": 3,
            "expectedProviderRef": {
              "assetType": "ProviderInstanceRevision",
              "assetId": "unit-provider",
              "revision": 1,
              "contentHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            },
            "expectedProviderModelId": "unit-model",
            "effectiveFrom": "2026-10-18T00:00:00.000001Z",
            "effectiveUntil": "2026-10-20T00:00:00.000002Z"
          },
          "requestHash": "6f08708b3eaa32ce5a1db24c2c980184a708e66299594b0f1cbf57703102d2e5",
          "proposalId": "window-proposal-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
          "proposalHash": "19542603caf0019560547e558537fdf4541fcb0f56b2887fb5a980d2addbb142",
          "proposal": {
            "schemaVersion": 1,
            "operationFamily": "budget-policy-window/v1",
            "tenant": {
              "orgId": "org-org",
              "projectId": "dev-project"
            },
            "makerSubject": "postgres-service:aos_budget_renewal_maker_call",
            "checkerSubject": "6f31cfdc-a26c-4f1f-ad6b-95a8559cc657",
            "request": {
              "schemaVersion": 1,
              "orgId": "org-org",
              "projectId": "dev-project",
              "idempotencyKey": "unit-window-proposal",
              "parentCostProposalId": "unit-proposal",
              "parentCostProposalHash": "567240939e22a176905b2ebd17f72404ff8742c8640792e6fbad354374d110e2",
              "parentCostDecisionId": "unit-decision",
              "parentConsumptionReceiptId": "budget-cost-consume-1ec2f0f5329cbc7f588164ed35ddcb3e4e4922f1c051c56b907e53ad55cf473e",
              "expectedBudgetRef": {
                "assetType": "BudgetRevision",
                "assetId": "unit-budget",
                "revision": 2,
                "contentHash": "f21615b40e0c97b42f8e48248e8cc524f3dd941e8a9931580dcd3e5fb598055a"
              },
              "expectedBudgetHeadVersion": 3,
              "expectedProviderRef": {
                "assetType": "ProviderInstanceRevision",
                "assetId": "unit-provider",
                "revision": 1,
                "contentHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
              },
              "expectedProviderModelId": "unit-model",
              "effectiveFrom": "2026-10-18T00:00:00.000001Z",
              "effectiveUntil": "2026-10-20T00:00:00.000002Z"
            },
            "requestHash": "6f08708b3eaa32ce5a1db24c2c980184a708e66299594b0f1cbf57703102d2e5",
            "parent": {
              "costProposalId": "unit-proposal",
              "costProposalHash": "567240939e22a176905b2ebd17f72404ff8742c8640792e6fbad354374d110e2",
              "costDecisionId": "unit-decision",
              "consumptionReceiptId": "budget-cost-consume-1ec2f0f5329cbc7f588164ed35ddcb3e4e4922f1c051c56b907e53ad55cf473e",
              "budgetRef": {
                "assetType": "BudgetRevision",
                "assetId": "unit-budget",
                "revision": 2,
                "contentHash": "f21615b40e0c97b42f8e48248e8cc524f3dd941e8a9931580dcd3e5fb598055a"
              },
              "budgetHeadVersion": 3,
              "providerRef": {
                "assetType": "ProviderInstanceRevision",
                "assetId": "unit-provider",
                "revision": 1,
                "contentHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
              },
              "providerModelId": "unit-model",
              "owner": "6f31cfdc-a26c-4f1f-ad6b-95a8559cc657",
              "budgetWindow": {
                "effectiveFrom": "2026-10-01T00:00:00Z",
                "effectiveUntil": "2026-11-01T00:00:00Z"
              },
              "risk": {
                "perRequestRiskMinor": 10,
                "totalRiskMinor": 100,
                "maxRequests": 10
              },
              "makerSubject": "unit-machine",
              "checkerSubject": "6f31cfdc-a26c-4f1f-ad6b-95a8559cc657"
            },
            "approvalSlot": "window-approval-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
            "targets": {
              "policy": {
                "policyId": "window-policy-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
                "revision": 1,
                "environment": "development",
                "effectiveFrom": "2026-10-18T00:00:00.000001Z",
                "effectiveUntil": "2026-10-20T00:00:00.000002Z",
                "owner": "6f31cfdc-a26c-4f1f-ad6b-95a8559cc657",
                "approvalRef": "window-approval-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
                "lifecycle": "active",
                "developmentCostAuthorization": {
                  "tenant": {
                    "orgId": "org-org",
                    "projectId": "dev-project"
                  },
                  "provider": {
                    "assetType": "ProviderInstanceRevision",
                    "assetId": "unit-provider",
                    "revision": 1,
                    "contentHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                  },
                  "providerModelId": "unit-model",
                  "approvalRef": "window-approval-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
                  "environment": "development",
                  "effectiveFrom": "2026-10-18T00:00:00.000001Z",
                  "effectiveUntil": "2026-10-20T00:00:00.000002Z"
                },
                "budgetRevisionRef": {
                  "assetType": "BudgetRevision",
                  "assetId": "unit-budget",
                  "revision": 2,
                  "contentHash": "f21615b40e0c97b42f8e48248e8cc524f3dd941e8a9931580dcd3e5fb598055a"
                },
                "currency": "CNY",
                "hardStop": true,
                "unknownUsageBehavior": "block",
                "unknownPriceBehavior": "block",
                "allowZeroPrice": false,
                "zeroPriceApprovalRef": null
              },
              "price": {
                "priceSnapshotId": "window-price-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
                "currency": "CNY",
                "inputTokenPrice": null,
                "outputTokenPrice": null,
                "cachedTokenPrice": null,
                "tokenUnit": 1000,
                "effectiveFrom": "2026-10-18T00:00:00.000001Z",
                "effectiveUntil": "2026-10-20T00:00:00.000002Z",
                "lifecycle": "active",
                "developmentCostAuthorization": {
                  "tenant": {
                    "orgId": "org-org",
                    "projectId": "dev-project"
                  },
                  "provider": {
                    "assetType": "ProviderInstanceRevision",
                    "assetId": "unit-provider",
                    "revision": 1,
                    "contentHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                  },
                  "providerModelId": "unit-model",
                  "approvalRef": "window-approval-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
                  "environment": "development",
                  "effectiveFrom": "2026-10-18T00:00:00.000001Z",
                  "effectiveUntil": "2026-10-20T00:00:00.000002Z"
                }
              }
            },
            "targetPairHash": "cde56f39dcf300fa2f540dc15aff56692a21364ea572cd431206bc3245f92024",
            "createdAt": "2026-10-18T00:00:00.000000Z",
            "expiresAt": "2026-10-18T00:30:00.000000Z"
          },
          "targetPairHash": "cde56f39dcf300fa2f540dc15aff56692a21364ea572cd431206bc3245f92024",
          "receiptId": "window-propose-e39cecd9fbd89626fa20acf645a9191aba77ea02f86ab26acb23375f9f3d46e1",
          "activationEligible": false
        },
        "activationEligible": false
      }
    },
    "approvalVerified": false,
    "activationEligible": false,
    "nativeWriteAllowed": false,
    "runtimeAdmissionAllowed": false
  },
  "decide": {
    "schemaVersion": "aos.budget-policy-window.gateway-observation/v1",
    "observation": {
      "schemaVersion": 1,
      "operation": "decide",
      "requestHash": "1863de26e5e9c7ed9c1b1b3573a1f9b22161f97b7c48631b4749bdbc00613693",
      "activationEligible": false,
      "result": {
        "status": "observed",
        "receipt": {
          "status": "observed",
          "operation": "decide",
          "command": {
            "schemaVersion": 1,
            "orgId": "org-org",
            "projectId": "dev-project",
            "idempotencyKey": "unit-window-decide",
            "proposalId": "window-proposal-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
            "proposalHash": "19542603caf0019560547e558537fdf4541fcb0f56b2887fb5a980d2addbb142",
            "targetPairHash": "cde56f39dcf300fa2f540dc15aff56692a21364ea572cd431206bc3245f92024",
            "decision": "approved"
          },
          "requestHash": "1863de26e5e9c7ed9c1b1b3573a1f9b22161f97b7c48631b4749bdbc00613693",
          "proposalId": "window-proposal-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
          "proposalHash": "19542603caf0019560547e558537fdf4541fcb0f56b2887fb5a980d2addbb142",
          "decisionId": "window-approval-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
          "decisionHash": "9228219d0566fc718f66b1d320d75195dc8fffbb56c01177fa53d1311c30c76f",
          "decision": "approved",
          "receiptId": "window-decide-9b96c964397e4064a93eda9bdfbfb3feed0c02bc5bccb516df2ea03e3f506b14",
          "activationEligible": false
        },
        "activationEligible": false
      }
    },
    "approvalVerified": false,
    "activationEligible": false,
    "nativeWriteAllowed": false,
    "runtimeAdmissionAllowed": false
  },
  "consume": {
    "schemaVersion": "aos.budget-policy-window.gateway-observation/v1",
    "observation": {
      "schemaVersion": 1,
      "operation": "consume",
      "requestHash": "fdd40e1bf43dcb47d7796d0dfead1c2761628b8ce6c0cc18361c944f9032b06c",
      "activationEligible": false,
      "result": {
        "status": "observed",
        "receipt": {
          "status": "observed",
          "operation": "consume",
          "command": {
            "schemaVersion": 1,
            "orgId": "org-org",
            "projectId": "dev-project",
            "idempotencyKey": "unit-window-consume",
            "proposalId": "window-proposal-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
            "proposalHash": "19542603caf0019560547e558537fdf4541fcb0f56b2887fb5a980d2addbb142",
            "decisionId": "window-approval-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
            "decisionHash": "9228219d0566fc718f66b1d320d75195dc8fffbb56c01177fa53d1311c30c76f",
            "targetPairHash": "cde56f39dcf300fa2f540dc15aff56692a21364ea572cd431206bc3245f92024"
          },
          "requestHash": "fdd40e1bf43dcb47d7796d0dfead1c2761628b8ce6c0cc18361c944f9032b06c",
          "proposalId": "window-proposal-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
          "proposalHash": "19542603caf0019560547e558537fdf4541fcb0f56b2887fb5a980d2addbb142",
          "decisionId": "window-approval-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
          "decisionHash": "9228219d0566fc718f66b1d320d75195dc8fffbb56c01177fa53d1311c30c76f",
          "targetPairHash": "cde56f39dcf300fa2f540dc15aff56692a21364ea572cd431206bc3245f92024",
          "budgetRef": {
            "assetType": "BudgetRevision",
            "assetId": "unit-budget",
            "revision": 2,
            "contentHash": "f21615b40e0c97b42f8e48248e8cc524f3dd941e8a9931580dcd3e5fb598055a"
          },
          "policyRef": {
            "assetType": "BudgetPolicyRevision",
            "assetId": "window-policy-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
            "revision": 1,
            "contentHash": "446fb20e951a88e22900693568f681381529ffd916e1c8ab88d214cc0f06bdb1"
          },
          "priceRef": {
            "assetType": "ModelPriceSnapshotRevision",
            "assetId": "window-price-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
            "revision": 1,
            "contentHash": "a392ea4567d1d49d55a8a0544e291cb7996df6b53b9b0c1a94247ae025367b03"
          },
          "bindingId": "window-binding-cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
          "bindingHash": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
          "receiptId": "window-consume-f674993b937d0fca866aaa6aad78c2af0080d1173c118313aa893e72115cabc8",
          "activationEligible": false
        },
        "activationEligible": false
      }
    },
    "approvalVerified": false,
    "activationEligible": false,
    "nativeWriteAllowed": false,
    "runtimeAdmissionAllowed": false
  },
  "revoke": {
    "schemaVersion": "aos.budget-policy-window.gateway-observation/v1",
    "observation": {
      "schemaVersion": 1,
      "operation": "revoke",
      "requestHash": "0b639b747d3657d7095cfa21fe04b13f34ca73ca1f1cf02043479273b2d36b5a",
      "activationEligible": false,
      "result": {
        "status": "observed",
        "receipt": {
          "status": "observed",
          "operation": "revoke",
          "command": {
            "schemaVersion": 1,
            "orgId": "org-org",
            "projectId": "dev-project",
            "idempotencyKey": "unit-window-revoke",
            "proposalId": "window-proposal-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
            "proposalHash": "19542603caf0019560547e558537fdf4541fcb0f56b2887fb5a980d2addbb142",
            "originalDecisionId": "window-approval-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
            "originalDecisionHash": "9228219d0566fc718f66b1d320d75195dc8fffbb56c01177fa53d1311c30c76f",
            "reason": "withdraw this explicit window"
          },
          "requestHash": "0b639b747d3657d7095cfa21fe04b13f34ca73ca1f1cf02043479273b2d36b5a",
          "proposalId": "window-proposal-ee04181d1ac396e3774808948f4b0f3bb5bd8329ede23f8ffc06154e28e8f2c7",
          "proposalHash": "19542603caf0019560547e558537fdf4541fcb0f56b2887fb5a980d2addbb142",
          "decisionId": "window-revoke-3b5b8b90b0c099f01532e69d51aa427adef90b3c44855dda7396359e4410001b",
          "decisionHash": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
          "decision": "revoked",
          "receiptId": "window-revoke-3b5b8b90b0c099f01532e69d51aa427adef90b3c44855dda7396359e4410001b",
          "activationEligible": false
        },
        "activationEligible": false
      }
    },
    "approvalVerified": false,
    "activationEligible": false,
    "nativeWriteAllowed": false,
    "runtimeAdmissionAllowed": false
  }
} as const;

const windowFlags={approvalVerified:false,activationEligible:false,nativeWriteAllowed:false,runtimeAdmissionAllowed:false};
const gatewayStatus={schemaVersion:'aos.budget-policy-window.gateway-status/v1',tenant:{orgId:'org-org',projectId:'dev-project'},subject:HUMAN,writerEnabled:false,...windowFlags};
const nativeRef=(op:keyof typeof nativeWire)=>({operation:op,key:nativeWire[op].observation.result.receipt.command.idempotencyKey});
function nativeFixture(op:keyof typeof nativeWire='propose'):any{return structuredClone(nativeWire[op]);}
function prepared(){const o=parseWindowObservation(nativeFixture(),nativeRef('propose'));if(o.status!=='observed'||o.receipt.operation!=='propose')throw new Error('unit prepared missing');return o.receipt;}
function approved(){const o=parseWindowObservation(nativeFixture('decide'),nativeRef('decide'));if(o.status!=='observed'||o.receipt.operation!=='decide')throw new Error('unit decision missing');return o.receipt;}
beforeEach(()=>{vi.stubGlobal('fetch',vi.fn());vi.mocked(tenantAuthHeaders).mockReturnValue({Authorization:'Bearer unit-only-token','X-Org-Id':'org-org','X-Project-Id':'dev-project','Content-Type':'application/json'});});
afterEach(()=>{vi.unstubAllGlobals();vi.useRealTimers();});
it.each(['propose','decide','revoke','consume'] as const)('reads exact native %s receipt without granting authority',op=>{
 const r=parseWindowObservation(nativeFixture(op),nativeRef(op));expect(r.status).toBe('observed');
 if(r.status==='observed'){expect(r.receipt.operation).toBe(op);expect(r.receipt.activationEligible).toBe(false);}
});
it.each(['top','frame','receipt'] as const)('rejects coerced false at %s',level=>{
 for(const invalid of [0,true,'false',null]){const v=nativeFixture();const target=level==='top'?v:level==='frame'?v.observation:v.observation.result.receipt;target.activationEligible=invalid;expect(()=>parseWindowObservation(v,nativeRef('propose'))).toThrow();}
});
it.each(['price','authorization','budget','risk','maker','parentCost','pair','expiry','key','hash','policy'] as const)('refuses malformed native links %s',change=>{
 const v=nativeFixture(),r=v.observation.result.receipt,p=r.proposal;
 if(change==='price')p.targets.price.inputTokenPrice=0;
 else if(change==='authorization')p.targets.price.developmentCostAuthorization.approvalRef='other';
 else if(change==='budget')p.parent.budgetRef.contentHash='a'.repeat(64);
 else if(change==='risk')p.parent.risk.totalRiskMinor=0;
 else if(change==='maker')p.makerSubject=HUMAN;
 else if(change==='parentCost')p.parent.costProposalId='other';
 else if(change==='pair')r.targetPairHash='f'.repeat(64);
 else if(change==='expiry')p.expiresAt=p.createdAt;
 else if(change==='key')r.command.idempotencyKey='other';
 else if(change==='hash')r.requestHash='f'.repeat(64);
 else p.targets.policy.allowZeroPrice=true;
 expect(()=>parseWindowObservation(v,nativeRef('propose'))).toThrow();
});
it('requires the complete paired consume receipt and exact decision links',()=>{
 const v=nativeFixture('consume');delete v.observation.result.receipt.priceRef;
 expect(()=>parseWindowObservation(v,nativeRef('consume'))).toThrow();
 const w=nativeFixture('decide');w.observation.result.receipt.decision='rejected';
 expect(()=>parseWindowObservation(w,nativeRef('decide'))).toThrow();
});
it('preserves unknown and unresolved without inventing not_attempted',()=>{
 const ref=nativeRef('propose'),requestHash=nativeWire.propose.observation.requestHash;
 expect(parseWindowObservation({schemaVersion:'aos.budget-policy-window.gateway-observation/v1',...windowFlags,observation:{status:'unknown',operation:'propose',requestHash,activationEligible:false}},ref).status).toBe('unknown');
 const v=nativeFixture();v.observation.result={status:'unresolved',activationEligible:false};expect(parseWindowObservation(v,ref).status).toBe('unresolved');
 v.observation.result.status='not_attempted';expect(()=>parseWindowObservation(v,ref)).toThrow();
});
it('builds four-operation inputs from exact current linked observations without sending',()=>{
 const p=prepared(),d=approved();
 expect(windowDecisionCommand(p,'unit-window-decide','approved')).toEqual(nativeWire.decide.observation.result.receipt.command);
 expect(windowRevocationCommand(p,d,'unit-window-revoke','withdraw this explicit window')).toEqual(nativeWire.revoke.observation.result.receipt.command);
 expect(windowConsumeCommand(p,d,'unit-window-consume',true)).toEqual(nativeWire.consume.observation.result.receipt.command);
 expect(fetch).not.toHaveBeenCalled();
});
it('requires explicit decision, consumption confirmation and exact reason',()=>{
 const p=prepared(),d=approved();
 expect(()=>windowDecisionCommand(p,'key','')).toThrow();
 expect(()=>windowConsumeCommand(p,d,'key',false)).toThrow();
 expect(()=>windowRevocationCommand(p,d,'key',' leading')).toThrow();
});
it('rejects nested mutation and stale auth/base before deriving a new decision',()=>{
 const p=prepared();(p.proposal.targets.price as unknown as Record<string,unknown>).tokenUnit=1;
 expect(()=>windowDecisionCommand(p,'key','approved')).toThrow();
 const fresh=prepared();vi.mocked(getAuthRevision).mockReturnValue(2);expect(()=>windowDecisionCommand(fresh,'key','approved')).toThrow();
 vi.mocked(getAuthRevision).mockReturnValue(1);vi.mocked(getApiBase).mockReturnValue('/another-api');expect(()=>windowDecisionCommand(fresh,'key','approved')).toThrow();
});
it('reads gateway status and bounded unique request index with false permissions',()=>{
 expect(parseWindowGatewayStatus(gatewayStatus).writerEnabled).toBe(false);
 expect(()=>parseWindowGatewayStatus({...gatewayStatus,nativeWriteAllowed:true})).toThrow();
 const item={operation:'propose',idempotencyKey:'unit-window-proposal',requestHash:nativeWire.propose.observation.requestHash};
 expect(parseWindowRequestIndex({schemaVersion:'aos.budget-policy-window.request-index/v1',requests:[item],...windowFlags})).toEqual([item]);
 expect(()=>parseWindowRequestIndex({schemaVersion:'aos.budget-policy-window.request-index/v1',requests:[item,item],...windowFlags})).toThrow();
});
it('uses only the fixed private GET with current headers and no cookie or redirect',async()=>{
 vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(gatewayStatus),{headers:{'content-type':'application/json'}}));
 expect((await readWindowGatewayStatus()).writerEnabled).toBe(false);
 expect(fetch).toHaveBeenCalledWith('http://127.0.0.1:18468/v1/aip/budget-policy-window/status',expect.objectContaining({method:'GET',credentials:'omit',redirect:'error',cache:'no-store',mode:'cors'}));
 expect(apiPostUnqueued).not.toHaveBeenCalled();
});
it.each(['propose','decide','revoke','consume'] as const)('sends only exact %s body once and independently queries original key',async op=>{
 vi.mocked(fetch).mockImplementation(async()=>new Response(JSON.stringify(nativeWire[op]),{headers:{'content-type':'application/json'}}));
 const command=nativeWire[op].observation.result.receipt.command;
 expect((await submitWindowOperation(op,command)).status).toBe('observed');
 const sent=vi.mocked(fetch).mock.calls[0];expect(sent[0]).toBe('http://127.0.0.1:18468/v1/aip/budget-policy-window/'+op);
 expect(JSON.parse(sent[1]!.body as string)).toEqual(command);expect(sent[1]!.body).not.toContain('unit-only-token');
 expect((await inquireWindowRequest(nativeRef(op))).status).toBe('observed');
 expect(vi.mocked(fetch).mock.calls[1][0]).toBe('http://127.0.0.1:18468/v1/aip/budget-policy-window/requests/'+op+'/'+encodeURIComponent(command.idempotencyKey));
 expect(vi.mocked(fetch).mock.calls[1][1]!.method).toBe('GET');
});
it('rejects late gateway response when auth changes',async()=>{
 let resolve!:(v:Response)=>void;vi.mocked(fetch).mockReturnValue(new Promise(r=>{resolve=r;}));const promise=readWindowGatewayStatus();vi.mocked(getAuthRevision).mockReturnValue(2);resolve(new Response(JSON.stringify(gatewayStatus),{headers:{'content-type':'application/json'}}));await expect(promise).rejects.toThrow();
});
it('does not retry or leak untrusted error details after a failed POST',async()=>{
 vi.mocked(fetch).mockRejectedValue(new Error('sensitive-driver-raw-detail'));
 await expect(submitWindowOperation('propose',nativeWire.propose.observation.result.receipt.command)).rejects.not.toThrow('sensitive-driver-raw-detail');expect(fetch).toHaveBeenCalledTimes(1);
});
it('bounds response bytes and refuses redirects/non-JSON before accepting observations',async()=>{
 vi.mocked(fetch).mockResolvedValue(new Response('x'.repeat(2*1024*1024+1),{headers:{'content-type':'application/json'}}));await expect(readWindowGatewayStatus()).rejects.toThrow();
 vi.mocked(fetch).mockResolvedValue(new Response('<secret>',{headers:{'content-type':'text/html'}}));await expect(readWindowGatewayStatus()).rejects.toThrow();
});
it('persists only original public refs and restores only a query pointer',()=>{
 window.history.replaceState({},'', '/aip/capacity?budgetCostRef=keep');saveWindowReference(nativeRef('propose'),true);
 expect(restoreWindowReference(window.location.search)).toEqual({ref:nativeRef('propose'),attempted:true});expect(window.location.search).toContain('budgetCostRef=keep');
 for(const value of ['approved','unit-budget','unit-only-token',nativeWire.propose.observation.requestHash])expect(window.location.search).not.toContain(value);
 expect(restoreWindowReference('?windowOperation=propose&windowKey=one&windowKey=two')).toBeNull();
});
it('formats safe minor amounts without floating-point loss or missing-as-zero',()=>{
 expect(formatWindowRiskMinor(9007199254740991)).toBe('¥90071992547409.91');expect(()=>formatWindowRiskMinor(NaN)).toThrow();
});
it('lists request history without posting or creating a new intent',async()=>{
 vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({schemaVersion:'aos.budget-policy-window.request-index/v1',requests:[],...windowFlags}),{headers:{'content-type':'application/json'}}));expect(await listWindowRequests()).toEqual([]);expect(fetch).toHaveBeenCalledTimes(1);expect(vi.mocked(fetch).mock.calls[0][1]!.method).toBe('GET');
});

it('validates consume budget and target witnesses against the prepared proposal',()=>{
 const p=prepared(),d=approved(),v=nativeFixture('consume');v.observation.result.receipt.budgetRef.contentHash='f'.repeat(64);
 expect(()=>parseWindowObservation(v,nativeRef('consume'),undefined,{prepared:p,decision:d})).toThrow();
 const changed=nativeFixture('decide');changed.observation.result.receipt.command.targetPairHash='f'.repeat(64);
 const view=parseWindowObservation(changed,nativeRef('decide'));if(view.status!=='observed'||view.receipt.operation!=='decide')throw new Error('unit decision');
 const changedDecision=view.receipt;expect(()=>parseWindowObservation(nativeFixture('consume'),nativeRef('consume'),undefined,{prepared:p,decision:changedDecision})).toThrow();
 expect(()=>parseWindowObservation(nativeFixture('consume'),nativeRef('consume'),undefined,{decision:d})).toThrow();
});
it('aborts a bounded request once and never automatically retries',async()=>{
 vi.useFakeTimers();vi.mocked(fetch).mockImplementation((_url,options)=>new Promise((_resolve,reject)=>options!.signal!.addEventListener('abort',()=>reject(new Error('private abort detail')))));
 const pending=readWindowGatewayStatus(),check=expect(pending).rejects.toThrow('原结果尚未确认');await vi.advanceTimersByTimeAsync(20001);await check;expect(fetch).toHaveBeenCalledTimes(1);
});

it('keeps an allowed colon key as one canonical path segment for the strict gateway',async()=>{
 vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({schemaVersion:'aos.budget-policy-window.gateway-observation/v1',...windowFlags,observation:{status:'unknown',operation:'propose',requestHash:nativeWire.propose.observation.requestHash,activationEligible:false}}),{headers:{'content-type':'application/json'}}));
 await inquireWindowRequest({operation:'propose',key:'window:test-1'});expect(vi.mocked(fetch).mock.calls[0][0]).toBe('http://127.0.0.1:18468/v1/aip/budget-policy-window/requests/propose/window:test-1');
});
it('honors native Unicode character limits and rejects non-printable separator input',async()=>{
 const p=prepared(),d=approved();expect(()=>windowRevocationCommand(p,d,'key','withdraw\u00a0reason')).toThrow();
 const command={...nativeWire.propose.observation.result.receipt.command,expectedProviderModelId:'😀'.repeat(240),expectedProviderRef:{...nativeWire.propose.observation.result.receipt.command.expectedProviderRef,assetId:'😀'.repeat(200)}};
 vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({schemaVersion:'aos.budget-policy-window.gateway-observation/v1',...windowFlags,observation:{status:'unknown',operation:'propose',requestHash:nativeWire.propose.observation.requestHash,activationEligible:false}}),{headers:{'content-type':'application/json'}}));
 expect((await submitWindowOperation('propose',command)).status).toBe('unknown');expect(JSON.parse(vi.mocked(fetch).mock.calls[0][1]!.body as string).expectedProviderModelId).toBe(command.expectedProviderModelId);
});

it('keeps existing router history state when saving an original request pointer',()=>{
 const state={idx:7,key:'router-original',usr:{returnTo:'/workshop'}};window.history.replaceState(state,'','/aip/capacity?budgetCostRef=keep');
 saveWindowReference(nativeRef('propose'),true);expect(window.history.state).toEqual(state);expect(window.location.search).toContain('budgetCostRef=keep');
});
