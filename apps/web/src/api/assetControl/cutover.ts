import type { IdempotencyKey } from "./idempotency";
import type { RegistrationReceiptRef } from "./registrationStatus";
import type { JsonValue } from "./types";

export type CutoverPhase="prepare"|"pause"|"commit"|"validate"|"resume"|"rollback-prepare"|"rollback-commit";
export interface CutoverRef {resourceType:string;resourceId:string;revision:number;contentHash:string}
type Base={cutoverOperationId:string;idempotencyKey:IdempotencyKey};
type Prepare=Base & {cutoverGroupId:string;expectedGroupRevision:number;targetInstallationId:string;
  targetGeneration:string;targetExecutionEpoch:number;targetRuntimeRevision:number;policyRef:CutoverRef;
  approvalRef:CutoverRef;checkpoint:Record<string,JsonValue>;occurrenceWatermark?:string|null;
  pendingTargetReceiptRefs?:CutoverRef[];registrationReceiptRef:RegistrationReceiptRef};
type Rollback={rollbackOperationId:string;idempotencyKey:IdempotencyKey;activationOperationId:string;
  commitReceiptRef:CutoverRef;approvalRef:CutoverRef;failureReason:string};
export type CutoverCommand=(
  {phase:"prepare";request:Prepare}|{phase:"pause"|"commit";request:Base & {prepareReceiptRef:CutoverRef}}|
  {phase:"validate"|"resume";request:Base & {commitReceiptRef:CutoverRef}}|
  {phase:"rollback-prepare"|"rollback-commit";request:Rollback}
) & {validateReceiptRef?:CutoverRef|null};
export type CutoverReceipt=Record<string,unknown> & {receiptId:string;contentHash:string;requestHash:string};
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const HASH=/^sha256:[0-9a-f]{64}$/;
function check(ok:unknown):asserts ok {if(!ok)throw new Error("经营接管材料不一致，请核对原请求");}
function object(v:unknown):asserts v is Record<string,unknown>{check(v&&typeof v==="object"&&!Array.isArray(v));}
function positive(v:unknown){check(Number.isSafeInteger(v)&&Number(v)>0);}
function uuid(v:unknown){check(typeof v==="string"&&UUID.test(v));}
function reference(v:unknown,kind?:string){object(v);check(typeof v.resourceType==="string"&&v.resourceType.length>0&&(!kind||v.resourceType===kind));
  check(typeof v.resourceId==="string"&&v.resourceId.length>0&&v.resourceId.trim()===v.resourceId);positive(v.revision);check(typeof v.contentHash==="string"&&HASH.test(v.contentHash));}
function sameRef(a:unknown,b:unknown){reference(a);reference(b);const x=a as CutoverRef,y=b as CutoverRef;
  check(x.resourceType===y.resourceType&&x.resourceId===y.resourceId&&x.revision===y.revision&&x.contentHash===y.contentHash);}

/** Snapshot of the original product envelope. This grants no current authority. */
export function serializeCutover(input:CutoverCommand,installationId:string):CutoverCommand {
  object(input);object(input.request);uuid(installationId);
  check(Object.keys(input).every(k=>["phase","request","validateReceiptRef"].includes(k)));
  const c=JSON.parse(JSON.stringify(input)) as CutoverCommand,r=c.request;
  check(typeof r.idempotencyKey==="string"&&r.idempotencyKey.length>0&&r.idempotencyKey.length<=160&&
    r.idempotencyKey.trim()===r.idempotencyKey&&!/[\u0000-\u001f\u007f]/.test(r.idempotencyKey));
  let fields:string[];
  if(c.phase==="prepare"){
    const p=c.request;fields=["cutoverOperationId","idempotencyKey","cutoverGroupId","expectedGroupRevision","targetInstallationId",
      "targetGeneration","targetExecutionEpoch","targetRuntimeRevision","policyRef","approvalRef","checkpoint","occurrenceWatermark","pendingTargetReceiptRefs","registrationReceiptRef"];
    uuid(p.cutoverOperationId);uuid(p.cutoverGroupId);uuid(p.targetGeneration);check(p.targetInstallationId===installationId);
    positive(p.expectedGroupRevision);positive(p.targetExecutionEpoch);positive(p.targetRuntimeRevision);
    reference(p.policyRef);reference(p.approvalRef,"ActionApprovalEvent");object(p.checkpoint);
    reference(p.registrationReceiptRef);uuid(p.registrationReceiptRef.resourceId);
    check(["FirstDispatchRegistrationReceipt","SuccessorDispatchRegistrationReceipt"].includes(p.registrationReceiptRef.resourceType)&&p.registrationReceiptRef.revision===1);
    check(p.occurrenceWatermark===undefined||p.occurrenceWatermark===null||
      (typeof p.occurrenceWatermark==="string"&&/(?:Z|[+-]\d\d:\d\d)$/.test(p.occurrenceWatermark)&&Number.isFinite(Date.parse(p.occurrenceWatermark))));
    if(p.pendingTargetReceiptRefs!==undefined){check(Array.isArray(p.pendingTargetReceiptRefs));p.pendingTargetReceiptRefs.forEach(v=>reference(v));}
  }else if(c.phase==="pause"||c.phase==="commit"){
    fields=["cutoverOperationId","idempotencyKey","prepareReceiptRef"];uuid(c.request.cutoverOperationId);reference(c.request.prepareReceiptRef,"CutoverPrepareReceipt");
  }else if(c.phase==="validate"||c.phase==="resume"){
    fields=["cutoverOperationId","idempotencyKey","commitReceiptRef"];uuid(c.request.cutoverOperationId);reference(c.request.commitReceiptRef,"CutoverCommitReceipt");
  }else {
    check(c.phase==="rollback-prepare"||c.phase==="rollback-commit");
    fields=["rollbackOperationId","idempotencyKey","activationOperationId","commitReceiptRef","approvalRef","failureReason"];
    const p=c.request;uuid(p.rollbackOperationId);uuid(p.activationOperationId);reference(p.commitReceiptRef,"CutoverCommitReceipt");reference(p.approvalRef,"ActionApprovalEvent");
    check(typeof p.failureReason==="string"&&p.failureReason.trim()===p.failureReason&&p.failureReason.length>0&&p.failureReason.length<=1000);
  }
  check(Object.keys(r).every(k=>fields.includes(k)));
  if(c.phase==="resume")reference(c.validateReceiptRef,"CutoverValidateReceipt");else check(c.validateReceiptRef==null);
  return c;
}
function common(value:unknown,tenant:{orgId:string|null;projectId:string|null},operationId:string,rollback=false):CutoverReceipt{
  object(value);object(value.tenant);check(tenant.orgId&&tenant.projectId&&value.tenant.orgId===tenant.orgId&&value.tenant.projectId===tenant.projectId);
  uuid(value.receiptId);check(typeof value.contentHash==="string"&&HASH.test(value.contentHash)&&typeof value.requestHash==="string"&&HASH.test(value.requestHash));
  check(value[rollback?"rollbackOperationId":"cutoverOperationId"]===operationId&&typeof value.replayed==="boolean");
  return value as CutoverReceipt;
}
export function parseCutoverReceipt(value:unknown,c:CutoverCommand,tenant:{orgId:string|null;projectId:string|null}):CutoverReceipt{
  const rollback=c.phase==="rollback-prepare"||c.phase==="rollback-commit";
  const request=c.request as unknown as Record<string,unknown>;
  const v=common(value,tenant,String(request[rollback?"rollbackOperationId":"cutoverOperationId"]),rollback);
  if(c.phase==="prepare"){
    check(v.status==="prepared");const p=c.request;
    for(const k of ["targetInstallationId","targetGeneration","targetExecutionEpoch","targetRuntimeRevision","cutoverGroupId","expectedGroupRevision"] as const)check(v[k]===p[k]);
    sameRef(v.policyRef,p.policyRef);sameRef(v.approvalRef,p.approvalRef);sameRef(v.registrationReceiptRef,p.registrationReceiptRef);
  }else{
    const expected={pause:["pause","draining"],commit:["commit","committed"],validate:["validate","validated"],resume:["resume","resumed"],
      "rollback-prepare":["fence","draining"],"rollback-commit":["rollback","rolled_back"]}[c.phase];
    check(v.phase===expected[0]&&v.status===expected[1]);
    const key=c.phase==="pause"||c.phase==="commit"?"prepareReceiptRef":"commitReceiptRef";sameRef(v[key],request[key]);
    if(rollback){check(v.activationOperationId===request.activationOperationId&&v.failureReason===request.failureReason);sameRef(v.approvalRef,request.approvalRef);}
  }
  return v;
}
export function parseCutoverRead(value:unknown,installationId:string,operationId:string,
  tenant:{orgId:string|null;projectId:string|null},history:boolean):Record<string,unknown>{
  object(value);check(value.historical===true&&value.executable===false);uuid(operationId);
  if(history){check(value.schemaVersion==="aos.ecommerce.cutover-history/v1");object(value.activationReceipts);check(Array.isArray(value.rollbacks));}
  const prepare=history?(value.activationReceipts as Record<string,unknown>).prepare:value.receipt;
  const r=common(prepare,tenant,operationId);check(r.status==="prepared"&&r.targetInstallationId===installationId);
  return value;
}
