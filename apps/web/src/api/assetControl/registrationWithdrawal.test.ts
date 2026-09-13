import { expect, it } from "vitest";
import { createWithdrawalIntent, parseWithdrawalReceipt } from "./registrationWithdrawal";
import { createIdempotentCommand, idempotencyKeyFor } from "./idempotency";
import type { RegistrationStatus } from "./registrationStatus";
const id="11111111-1111-4111-8111-111111111111";
const status: RegistrationStatus={schemaVersion:"aos.ecommerce.first-dispatch-status/v1",installationId:id,state:"registered",registrationReceiptRef:{resourceType:"FirstDispatchRegistrationReceipt",resourceId:id,revision:1,contentHash:"sha256:"+"a".repeat(64)},withdrawalReceiptId:null,allowedActions:["withdraw"],executable:false,expectedInstallationEtag:5,withdrawalReason:"unused_origin"};
it("freezes an exact intent and rejects an unrelated success",()=>{
  const intent=createWithdrawalIntent(status,idempotencyKeyFor(createIdempotentCommand()));
  expect(Object.isFrozen(intent)).toBe(true);
  const receipt={schemaVersion:"aos.ecommerce.first-dispatch-withdrawal-receipt/v1",receiptId:id,installationId:id,idempotencyKey:intent.idempotencyKey,registrationReceiptRef:status.registrationReceiptRef,executable:false,releasedOperationCount:9,contentHash:"sha256:"+"b".repeat(64)};
  expect(parseWithdrawalReceipt(receipt,intent).receiptId).toBe(id);
  expect(()=>parseWithdrawalReceipt({...receipt,idempotencyKey:"other"},intent)).toThrow();
  expect(()=>parseWithdrawalReceipt({...receipt,executable:true},intent)).toThrow();
});
it("does not create an intent for a blocked hint",()=>{
  expect(()=>createWithdrawalIntent({...status,allowedActions:[],withdrawalReason:"dependent_history"},idempotencyKeyFor(createIdempotentCommand()))).toThrow();
});
