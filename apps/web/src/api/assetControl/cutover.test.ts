import { afterEach, expect, it, vi } from "vitest";
import { AssetControlClient } from "./client";
import { setConnectivity } from "../../lib/offlineStore";
import type { CutoverCommand, CutoverPhase } from "./cutover";
import type { IdempotencyKey } from "./idempotency";

const id="11111111-1111-4111-8111-111111111111", generation="22222222-2222-4222-8222-222222222222";
const hash=`sha256:${"1".repeat(64)}`;
const ref=(resourceType:string)=>({resourceType,resourceId:id,revision:1,contentHash:hash});
const tenant={orgId:"org-org",projectId:"dev-project"};
function command(phase:CutoverPhase="prepare"):CutoverCommand {
  const base={cutoverOperationId:id,idempotencyKey:"phase-key" as IdempotencyKey};
  if(phase==="prepare")return {phase,request:{...base,cutoverGroupId:id,expectedGroupRevision:2,
    targetInstallationId:id,targetGeneration:generation,targetExecutionEpoch:1,targetRuntimeRevision:3,
    policyRef:ref("RuntimePolicyRevision"),approvalRef:ref("ActionApprovalEvent"),checkpoint:{node:"new"},
    registrationReceiptRef:{...ref("SuccessorDispatchRegistrationReceipt"),resourceType:"SuccessorDispatchRegistrationReceipt",revision:1}}};
  if(phase==="pause"||phase==="commit")return {phase,request:{...base,prepareReceiptRef:ref("CutoverPrepareReceipt")}};
  if(phase==="validate"||phase==="resume")return {phase,request:{...base,commitReceiptRef:ref("CutoverCommitReceipt")},
    ...(phase==="resume"?{validateReceiptRef:ref("CutoverValidateReceipt")}: {})} as CutoverCommand;
  return {phase,request:{rollbackOperationId:id,idempotencyKey:base.idempotencyKey,activationOperationId:id,
    commitReceiptRef:ref("CutoverCommitReceipt"),approvalRef:ref("ActionApprovalEvent"),failureReason:"验证失败"}};
}
function receipt(c=command()) {
  const phases={prepare:[undefined,"prepared"],pause:["pause","draining"],commit:["commit","committed"],
    validate:["validate","validated"],resume:["resume","resumed"],"rollback-prepare":["fence","draining"],"rollback-commit":["rollback","rolled_back"]};
  return {tenant,receiptId:id,contentHash:hash,requestHash:hash,replayed:false,createdAt:"2026-10-31T00:00:00Z",
    ...structuredClone(c.request),phase:phases[c.phase][0],status:phases[c.phase][1]};
}
function harness(value:unknown=receipt()) {
  const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify(value),{status:201}));
  const auth={"X-Org-Id":tenant.orgId,"X-Project-Id":tenant.projectId,Authorization:"Bearer fixture"};
  const client=new AssetControlClient({fetch,getBaseUrl:()=>"http://test",getAuthHeaders:()=>auth});
  return {client,fetch,auth};
}
afterEach(()=>setConnectivity("unknown","cutover-test"));
// Golden envelopes serialized by the original backend model; no runtime evidence-file dependency.
const nativeCommands=[
  {
    "phase": "prepare",
    "request": {
      "cutoverOperationId": "11111111-1111-4111-8111-111111111111",
      "idempotencyKey": "phase-key",
      "cutoverGroupId": "11111111-1111-4111-8111-111111111111",
      "expectedGroupRevision": 2,
      "targetInstallationId": "11111111-1111-4111-8111-111111111111",
      "targetGeneration": "22222222-2222-4222-8222-222222222222",
      "targetExecutionEpoch": 1,
      "targetRuntimeRevision": 3,
      "policyRef": {
        "resourceType": "RuntimePolicyRevision",
        "resourceId": "11111111-1111-4111-8111-111111111111",
        "revision": 1,
        "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
      },
      "approvalRef": {
        "resourceType": "ActionApprovalEvent",
        "resourceId": "11111111-1111-4111-8111-111111111111",
        "revision": 1,
        "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
      },
      "checkpoint": {
        "node": "new"
      },
      "occurrenceWatermark": null,
      "pendingTargetReceiptRefs": [],
      "registrationReceiptRef": {
        "resourceType": "SuccessorDispatchRegistrationReceipt",
        "resourceId": "11111111-1111-4111-8111-111111111111",
        "revision": 1,
        "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
      }
    },
    "validateReceiptRef": null
  },
  {
    "phase": "pause",
    "request": {
      "cutoverOperationId": "11111111-1111-4111-8111-111111111111",
      "idempotencyKey": "phase-key",
      "prepareReceiptRef": {
        "resourceType": "CutoverPrepareReceipt",
        "resourceId": "11111111-1111-4111-8111-111111111111",
        "revision": 1,
        "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
      }
    },
    "validateReceiptRef": null
  },
  {
    "phase": "commit",
    "request": {
      "cutoverOperationId": "11111111-1111-4111-8111-111111111111",
      "idempotencyKey": "phase-key",
      "prepareReceiptRef": {
        "resourceType": "CutoverPrepareReceipt",
        "resourceId": "11111111-1111-4111-8111-111111111111",
        "revision": 1,
        "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
      }
    },
    "validateReceiptRef": null
  },
  {
    "phase": "validate",
    "request": {
      "cutoverOperationId": "11111111-1111-4111-8111-111111111111",
      "idempotencyKey": "phase-key",
      "commitReceiptRef": {
        "resourceType": "CutoverCommitReceipt",
        "resourceId": "11111111-1111-4111-8111-111111111111",
        "revision": 1,
        "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
      }
    },
    "validateReceiptRef": null
  },
  {
    "phase": "resume",
    "request": {
      "cutoverOperationId": "11111111-1111-4111-8111-111111111111",
      "idempotencyKey": "phase-key",
      "commitReceiptRef": {
        "resourceType": "CutoverCommitReceipt",
        "resourceId": "11111111-1111-4111-8111-111111111111",
        "revision": 1,
        "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
      }
    },
    "validateReceiptRef": {
      "resourceType": "CutoverValidateReceipt",
      "resourceId": "11111111-1111-4111-8111-111111111111",
      "revision": 1,
      "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
    }
  },
  {
    "phase": "rollback-prepare",
    "request": {
      "rollbackOperationId": "11111111-1111-4111-8111-111111111111",
      "idempotencyKey": "phase-key",
      "activationOperationId": "11111111-1111-4111-8111-111111111111",
      "commitReceiptRef": {
        "resourceType": "CutoverCommitReceipt",
        "resourceId": "11111111-1111-4111-8111-111111111111",
        "revision": 1,
        "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
      },
      "approvalRef": {
        "resourceType": "ActionApprovalEvent",
        "resourceId": "11111111-1111-4111-8111-111111111111",
        "revision": 1,
        "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
      },
      "failureReason": "验证失败"
    },
    "validateReceiptRef": null
  },
  {
    "phase": "rollback-commit",
    "request": {
      "rollbackOperationId": "11111111-1111-4111-8111-111111111111",
      "idempotencyKey": "phase-key",
      "activationOperationId": "11111111-1111-4111-8111-111111111111",
      "commitReceiptRef": {
        "resourceType": "CutoverCommitReceipt",
        "resourceId": "11111111-1111-4111-8111-111111111111",
        "revision": 1,
        "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
      },
      "approvalRef": {
        "resourceType": "ActionApprovalEvent",
        "resourceId": "11111111-1111-4111-8111-111111111111",
        "revision": 1,
        "contentHash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
      },
      "failureReason": "验证失败"
    },
    "validateReceiptRef": null
  }
] as CutoverCommand[];
it.each(nativeCommands)("accepts original backend serialization for $phase",async c=>{
  const {client,fetch}=harness(receipt(c));await client.executeCutover(id,c,5);
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(c);
});
it.each(["prepare","pause","commit","validate","resume","rollback-prepare","rollback-commit"] as const)("sends only the selected original %s phase",async phase=>{
  const c=command(phase),{client,fetch}=harness(receipt(c));
  await client.executeCutover(id,c,5);
  expect(fetch).toHaveBeenCalledTimes(1);
  const [url,init]=fetch.mock.calls[0];
  expect(url).toBe(`http://test/v1/bundle-runtime-installations/${id}/ecommerce-growth-cutovers/commands`);
  expect(init.method).toBe("POST");expect(init.headers.get("If-Match")).toBe('"5"');
  expect(init.headers.get("Idempotency-Key")).toBe("phase-key");expect(JSON.parse(init.body)).toEqual(c);
});
it.each(["tenant","operation","phase","reference"])("rejects %s response drift",async defect=>{
  const c=command("commit"),r=receipt(c);
  if(defect==="tenant")r.tenant={...tenant,orgId:"foreign"};
  if(defect==="operation")Object.assign(r,{cutoverOperationId:generation});
  if(defect==="phase")r.phase="pause";
  if(defect==="reference")Object.assign(r,{prepareReceiptRef:{...ref("CutoverPrepareReceipt"),contentHash:`sha256:${"2".repeat(64)}`}});
  await expect(harness(r).client.executeCutover(id,c,5)).rejects.toThrow();
});
it("keeps sent request and tenant snapshots",async()=>{
  const c=command(),original=structuredClone(c),{client,fetch,auth}=harness();let finish!:(r:Response)=>void;
  fetch.mockImplementationOnce(()=>new Promise<Response>(r=>{finish=r;}));
  const pending=client.executeCutover(id,c,5);c.request.idempotencyKey="changed" as IdempotencyKey;auth["X-Org-Id"]="foreign";
  finish(new Response(JSON.stringify(receipt(original)),{status:201}));await pending;
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(original);
});
it("does not retry unknown or automatically advance",async()=>{
  const {client,fetch}=harness();fetch.mockRejectedValue(new Error("timeout"));
  await expect(client.executeCutover(id,command(),5)).rejects.toThrow();expect(fetch).toHaveBeenCalledTimes(1);
});
it("blocks offline mutation before sending",async()=>{
  const {client,fetch}=harness();setConnectivity("offline","fixture");
  expect(()=>client.executeCutover(id,command(),5)).toThrow();expect(fetch).not.toHaveBeenCalled();
});
it("requires resume validation and exact target before sending",()=>{
  const {client,fetch}=harness();const c=command("resume");delete c.validateReceiptRef;
  expect(()=>client.executeCutover(id,c,5)).toThrow();
  expect(()=>client.executeCutover(generation,command(),5)).toThrow();expect(fetch).not.toHaveBeenCalled();
});
it("reads original prepare key without a state-changing call",async()=>{
  const {client,fetch}=harness({receipt:receipt(),historical:true,executable:false});
  await client.readCutoverPrepare(id,"original-prepare-key" as IdempotencyKey,id);
  const [url,init]=fetch.mock.calls[0];expect(url).toMatch(/cutovers\/receipt$/);expect(init.method).toBe("GET");
  expect(init.headers.get("Idempotency-Key")).toBe("original-prepare-key");expect(init.headers.has("If-Match")).toBe(false);
});
it("history remains evidence and cannot become an execution authorization",async()=>{
  const history={schemaVersion:"aos.ecommerce.cutover-history/v1",historical:true,executable:false,
    observedStatus:"prepared",activationReceipts:{prepare:receipt()},rollbacks:[]};
  await harness(history).client.readCutoverHistory(id,"original-prepare-key" as IdempotencyKey,id);
  await expect(harness({...history,executable:true}).client.readCutoverHistory(id,"original-prepare-key" as IdempotencyKey,id)).rejects.toThrow();
});
