import type { IdempotencyKey } from "./idempotency";
import { parseRegistrationStatus, type RegistrationStatus, type RegistrationReceiptRef } from "./registrationStatus";
export interface WithdrawalIntent {
  readonly installationId: string;
  readonly registrationReceiptRef: RegistrationReceiptRef;
  readonly expectedInstallationEtag: number;
  readonly idempotencyKey: IdempotencyKey;
}
export interface WithdrawalReceipt { receiptId: string; contentHash: string; }
export function createWithdrawalIntent(raw: RegistrationStatus, key: IdempotencyKey): WithdrawalIntent {
  const status=parseRegistrationStatus(raw);
  if(!status.allowedActions.includes("withdraw") || !status.registrationReceiptRef || status.expectedInstallationEtag===null) throw new Error("Withdrawal is not available");
  return Object.freeze({installationId:status.installationId,registrationReceiptRef:Object.freeze({...status.registrationReceiptRef}),expectedInstallationEtag:status.expectedInstallationEtag,idempotencyKey:key});
}
export function withdrawalBody(intent: WithdrawalIntent) {
  return {schemaVersion:"aos.ecommerce.first-dispatch-withdrawal/v1",registrationReceiptRef:intent.registrationReceiptRef,expectedInstallationEtag:intent.expectedInstallationEtag,idempotencyKey:intent.idempotencyKey};
}
export function parseWithdrawalReceipt(value: unknown, intent: WithdrawalIntent): WithdrawalReceipt {
  if(!value || typeof value!=="object" || Array.isArray(value)) throw new Error("Invalid withdrawal receipt");
  const r=value as Record<string, unknown>, ref=r.registrationReceiptRef as Record<string, unknown> | null;
  if(r.schemaVersion!=="aos.ecommerce.first-dispatch-withdrawal-receipt/v1" || r.installationId!==intent.installationId || r.idempotencyKey!==intent.idempotencyKey || r.executable!==false || r.releasedOperationCount!==9 ||
    typeof r.receiptId!=="string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(r.receiptId) ||
    typeof r.contentHash!=="string" || !/^sha256:[0-9a-f]{64}$/.test(r.contentHash) || !ref ||
    Object.entries(intent.registrationReceiptRef).some(([k,v])=>ref[k]!==v)) throw new Error("Withdrawal receipt mismatch");
  return {receiptId:r.receiptId,contentHash:r.contentHash};
}
