// Synthetic UI vectors only, not PG, actual OIDC, human approval or business proof.
import {act} from 'react';
import {createRoot,type Root} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {BudgetPolicyWindowReviewPanel} from './BudgetPolicyWindowReviewPanel';
import * as api from '../../api/aipBudgetPolicyWindow';
import {setTenant,setAccessToken} from '../../api/tenant';
(globalThis as {IS_REACT_ACT_ENVIRONMENT?:boolean}).IS_REACT_ACT_ENVIRONMENT=true;
const sourceWire={
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
const nativeWires={
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
};

const HUMAN='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657';
let host:HTMLDivElement,root:Root;
beforeEach(()=>{setTenant({orgId:'org-org',projectId:'dev-project',subject:HUMAN});setAccessToken('unit-panel-only');window.history.replaceState({},'', '/aip/capacity');vi.spyOn(Date,'now').mockReturnValue(Date.parse('2026-10-18T00:05:00Z'));host=document.createElement('div');document.body.append(host);root=createRoot(host);});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.restoreAllMocks();setAccessToken(null);setTenant({subject:undefined});});
const button=(name:string)=>[...host.querySelectorAll('button')].find(b=>b.textContent===name)!;
async function input(name:string,value:string){await act(async()=>{const n=host.querySelector<HTMLInputElement>(`[aria-label="${name}"]`)!;Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(n,value);n.dispatchEvent(new Event('input',{bubbles:true}));});}
async function select(name:string,value:string){await act(async()=>{const n=host.querySelector<HTMLSelectElement>(`[aria-label="${name}"]`)!;n.value=value;n.dispatchEvent(new Event('change',{bubbles:true}));});}
async function render(){await act(async()=>root.render(<BudgetPolicyWindowReviewPanel/>));}
const nativeRef=(op:keyof typeof nativeWires)=>({operation:op,key:nativeWires[op].observation.result.receipt.command.idempotencyKey});
function readMocks(writer=true){vi.spyOn(api,'readWindowGatewayStatus').mockImplementation(async()=>api.parseWindowGatewayStatus({schemaVersion:'aos.budget-policy-window.gateway-status/v1',tenant:{orgId:'org-org',projectId:'dev-project'},subject:HUMAN,writerEnabled:writer,approvalVerified:false,activationEligible:false,nativeWriteAllowed:false,runtimeAdmissionAllowed:false}));vi.spyOn(api,'readPolicyWindowSource').mockImplementation(async id=>api.parsePolicyWindowSource(sourceWire,id));}
async function ready(){await act(async()=>button('核对审核入口').click());await input('父费用提议编号','unit-proposal');await act(async()=>button('读取父预算来源').click());await input('策略开始时间','2026-10-18T00:00:00.000001Z');await input('策略结束时间','2026-10-20T00:00:00.000002Z');await input('策略操作编号','unit-window-proposal');}
function postMocks(){return vi.spyOn(api,'submitWindowOperation').mockImplementation(async(op,command,links)=>api.parseWindowObservation(nativeWires[op],{operation:op,key:command.idempotencyKey},command,links));}
async function propose(){await ready();await act(async()=>button('提交策略提议').click());}
it('starts blank with no default dates, consent or requests',async()=>{
 const read=vi.spyOn(api,'readWindowGatewayStatus'),source=vi.spyOn(api,'readPolicyWindowSource'),post=vi.spyOn(api,'submitWindowOperation');await render();
 expect(read).not.toHaveBeenCalled();expect(source).not.toHaveBeenCalled();expect(post).not.toHaveBeenCalled();expect(button('提交策略提议').disabled).toBe(true);
 expect(host.querySelector<HTMLInputElement>('[aria-label="策略开始时间"]')!.value).toBe('');expect(host.textContent).toContain('不增加预算');
});
it('keeps every paired-window request disabled until a current OIDC session exists',async()=>{
 const status=vi.spyOn(api,'readWindowGatewayStatus'),history=vi.spyOn(api,'listWindowRequests'),source=vi.spyOn(api,'readPolicyWindowSource'),post=vi.spyOn(api,'submitWindowOperation');
 setAccessToken(null);await render();
 expect(button('核对审核入口').disabled).toBe(true);expect(button('读取原操作列表').disabled).toBe(true);expect(button('读取父预算来源').disabled).toBe(true);expect(button('提交策略提议').disabled).toBe(true);
 expect(status).not.toHaveBeenCalled();expect(history).not.toHaveBeenCalled();expect(source).not.toHaveBeenCalled();expect(post).not.toHaveBeenCalled();
 await act(async()=>setAccessToken('restored-human-session'));
 expect(button('核对审核入口').disabled).toBe(false);expect(button('读取原操作列表').disabled).toBe(false);
 expect(status).not.toHaveBeenCalled();expect(history).not.toHaveBeenCalled();
 await act(async()=>setAccessToken(null));
 expect(button('核对审核入口').disabled).toBe(true);expect(button('读取原操作列表').disabled).toBe(true);
 expect(status).not.toHaveBeenCalled();expect(history).not.toHaveBeenCalled();expect(post).not.toHaveBeenCalled();
});
it('makes four explicit operations with no automatic approval or consumption',async()=>{
 readMocks();const post=postMocks();await render();await propose();expect(post).toHaveBeenCalledTimes(1);expect(host.textContent).toContain('未知价格不代表免费');
 await select('策略操作','decide');await input('策略操作编号','unit-window-decide');expect(button('提交策略决定').disabled).toBe(true);await select('策略审核意见','approved');
 await act(async()=>button('提交策略决定').click());expect(post).toHaveBeenCalledTimes(2);expect(post.mock.calls[1][0]).toBe('decide');
 await select('策略操作','consume');await input('策略操作编号','unit-window-consume');expect(button('生成成对策略与价格').disabled).toBe(true);await select('策略配置确认','consume');await act(async()=>button('生成成对策略与价格').click());
 expect(post).toHaveBeenCalledTimes(3);expect(host.textContent).toContain('配置历史');expect(host.textContent).toContain('不代表模型或业务已运行');
 await select('策略操作','revoke');await input('策略操作编号','unit-window-revoke');expect(button('撤销策略批准').disabled).toBe(true);await input('策略撤销原因','withdraw this explicit window');await act(async()=>button('撤销策略批准').click());expect(post).toHaveBeenCalledTimes(4);
});
it('unknown double click is sent once, frozen and only queried with original ref',async()=>{
 readMocks();const post=vi.spyOn(api,'submitWindowOperation').mockRejectedValue(new Error('lost response'));const query=vi.spyOn(api,'inquireWindowRequest').mockImplementation(async ref=>({status:'unresolved',ref,requestHash:'a'.repeat(64)}));await render();await ready();await act(async()=>{button('提交策略提议').click();button('提交策略提议').click();});expect(post).toHaveBeenCalledTimes(1);
 expect(button('提交策略提议').disabled).toBe(true);expect(host.querySelector<HTMLInputElement>('[aria-label="策略操作编号"]')!.disabled).toBe(true);await act(async()=>button('查询原策略操作').click());expect(query).toHaveBeenCalledWith(nativeRef('propose'),expect.anything());expect(post).toHaveBeenCalledTimes(1);
 for(const raw of ['approved',sourceWire.parent.proposalHash,'unit-panel-only'])expect(window.location.search).not.toContain(raw);
});
it('restores only the original inquiry and never posts or opens writer on mount',async()=>{
 window.history.replaceState({},'', '/aip/capacity?windowOperation=propose&windowKey=unit-window-proposal&windowAttempted=1');const query=vi.spyOn(api,'inquireWindowRequest').mockImplementation(async ref=>api.parseWindowObservation(nativeWires.propose,ref));const post=vi.spyOn(api,'submitWindowOperation');await render();expect(query).toHaveBeenCalledTimes(1);expect(post).not.toHaveBeenCalled();expect(button('提交策略提议').disabled).toBe(true);
});
it('a closed gateway cannot submit even with complete source inputs',async()=>{
 readMocks(false);const post=postMocks();await render();await ready();expect(button('提交策略提议').disabled).toBe(true);expect(post).not.toHaveBeenCalled();
});
it('drops a late native response after identity change',async()=>{
 readMocks();let resolve!:(v:api.WindowObservation)=>void;const post=vi.spyOn(api,'submitWindowOperation').mockReturnValue(new Promise(r=>{resolve=r;}));await render();await ready();await act(async()=>button('提交策略提议').click());expect(post).toHaveBeenCalledTimes(1);const saved=api.parseWindowObservation(nativeWires.propose,nativeRef('propose'));await act(async()=>setTenant({subject:'other'}));await act(async()=>resolve(saved));
 expect(host.querySelector('[aria-label="原生策略提议"]')).toBeNull();expect(button('提交策略提议').disabled).toBe(true);
});
it('loads original history only and never treats the index as approval',async()=>{
 vi.spyOn(api,'listWindowRequests').mockResolvedValue([{operation:'decide',idempotencyKey:'unit-window-decide',requestHash:'b'.repeat(64)}]);const post=vi.spyOn(api,'submitWindowOperation');await render();await act(async()=>button('读取原操作列表').click());expect(host.textContent).toContain('unit-window-decide');expect(post).not.toHaveBeenCalled();expect(button('提交策略提议').disabled).toBe(true);
});
it('expires conservatively before a decision and rechecks expiry at the click',async()=>{
 readMocks();const post=postMocks();await render();await propose();await select('策略操作','decide');await input('策略操作编号','unit-window-decide');await select('策略审核意见','approved');expect(button('提交策略决定').disabled).toBe(false);
 vi.mocked(Date.now).mockReturnValue(Date.parse('2026-10-18T00:31:00Z'));await act(async()=>button('提交策略决定').click());expect(post).toHaveBeenCalledTimes(1);
});
it('requires an observed approval for configuration and never assumes one',async()=>{
 readMocks();const post=postMocks();await render();await propose();await select('策略操作','consume');await input('策略操作编号','unit-window-consume');await select('策略配置确认','consume');expect(button('生成成对策略与价格').disabled).toBe(true);expect(post).toHaveBeenCalledTimes(1);
});
it('keeps known revocation when an old prepared record is read again',async()=>{
 readMocks();const post=postMocks();await render();await propose();await select('策略操作','decide');await input('策略操作编号','unit-window-decide');await select('策略审核意见','approved');await act(async()=>button('提交策略决定').click());await select('策略操作','revoke');await input('策略操作编号','unit-window-revoke');await input('策略撤销原因','withdraw this explicit window');await act(async()=>button('撤销策略批准').click());
 vi.spyOn(api,'listWindowRequests').mockResolvedValue([{operation:'propose',idempotencyKey:'unit-window-proposal',requestHash:'a'.repeat(64)}]);vi.spyOn(api,'inquireWindowRequest').mockImplementation(async ref=>api.parseWindowObservation(nativeWires.propose,ref));await act(async()=>button('读取原操作列表').click());await act(async()=>button('propose / unit-window-proposal').click());expect(host.querySelector('[aria-label="策略撤销历史"]')).not.toBeNull();await select('策略操作','consume');await input('策略操作编号','new-config-key');await select('策略配置确认','consume');expect(button('生成成对策略与价格').disabled).toBe(true);expect(post).toHaveBeenCalledTimes(3);
});
it('clears explicit choices when recovering another original observation',async()=>{
 readMocks();postMocks();await render();await propose();await select('策略操作','decide');await input('策略操作编号','unit-window-decide');await select('策略审核意见','approved');
 vi.spyOn(api,'listWindowRequests').mockResolvedValue([{operation:'propose',idempotencyKey:'unit-window-proposal',requestHash:'a'.repeat(64)}]);vi.spyOn(api,'inquireWindowRequest').mockImplementation(async ref=>api.parseWindowObservation(nativeWires.propose,ref));await act(async()=>button('读取原操作列表').click());await act(async()=>button('propose / unit-window-proposal').click());await select('策略操作','decide');expect((host.querySelector('[aria-label="策略审核意见"]') as HTMLSelectElement).value).toBe('');
});
it('blocked parent observations remain unable to submit with unknown values',async()=>{
 readMocks();const blocked={...structuredClone(sourceWire),state:'blocked',sourceBudget:null,blockers:['WINDOW_SOURCE_BUDGET_MISSING']};vi.mocked(api.readPolicyWindowSource).mockImplementation(async id=>api.parsePolicyWindowSource(blocked,id));const post=postMocks();await render();await ready();expect(button('提交策略提议').disabled).toBe(true);expect(post).not.toHaveBeenCalled();
});
it('does not leak raw transport failure text to the panel',async()=>{
 readMocks();vi.spyOn(api,'submitWindowOperation').mockRejectedValue(new Error('driver_private_unit_secret'));await render();await propose();expect(host.textContent).not.toContain('driver_private_unit_secret');expect(host.textContent).toContain('只能查询原操作');
});
