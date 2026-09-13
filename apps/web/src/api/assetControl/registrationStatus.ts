export interface RegistrationReceiptRef {
  resourceType: "FirstDispatchRegistrationReceipt";
  resourceId: string;
  revision: 1;
  contentHash: string;
}
export interface RegistrationStatus {
  schemaVersion: "aos.ecommerce.first-dispatch-status/v1";
  installationId: string;
  state: "unregistered" | "registered" | "withdrawn" | "needs_attention";
  registrationReceiptRef: RegistrationReceiptRef | null;
  withdrawalReceiptId: string | null;
  allowedActions: ("withdraw")[];
  executable: false;
  expectedInstallationEtag: number | null;
  withdrawalReason: "not_applicable" | "unused_origin" | "dependent_history" | "dispatch_changed";
}
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function object(value: unknown, fields: string[]): Record<string, unknown> {
  if (!value || typeof value!=="object" || Array.isArray(value)) throw new Error("Invalid registration status");
  const item=value as Record<string, unknown>;
  if(Object.keys(item).length!==fields.length || fields.some(key=>!Object.hasOwn(item,key))) throw new Error("Invalid registration fields");
  return item;
}
function uuid(value: unknown): asserts value is string {
  if(typeof value!=="string" || !UUID.test(value)) throw new Error("Invalid registration identity");
}
export function parseRegistrationStatus(value: unknown): RegistrationStatus {
  const item=object(value,["schemaVersion","installationId","state","registrationReceiptRef","withdrawalReceiptId","allowedActions","executable","expectedInstallationEtag","withdrawalReason"]);
  uuid(item.installationId);
  if(item.schemaVersion!=="aos.ecommerce.first-dispatch-status/v1" || item.executable!==false ||
    !["unregistered","registered","withdrawn","needs_attention"].includes(String(item.state)) ||
    !Array.isArray(item.allowedActions)) throw new Error("Invalid registration state");
  let ref: RegistrationReceiptRef | null=null;
  if(item.state==="registered") {
    const raw=object(item.registrationReceiptRef,["resourceType","resourceId","revision","contentHash"]);
    uuid(raw.resourceId);
    if(raw.resourceType!=="FirstDispatchRegistrationReceipt" || raw.revision!==1 ||
      typeof raw.contentHash!=="string" || !/^sha256:[0-9a-f]{64}$/.test(raw.contentHash) ||
      !Number.isSafeInteger(item.expectedInstallationEtag) || Number(item.expectedInstallationEtag)<1 ||
      item.withdrawalReceiptId!==null || !["unused_origin","dependent_history","dispatch_changed"].includes(String(item.withdrawalReason))) throw new Error("Invalid registration reference");
    ref={resourceType:"FirstDispatchRegistrationReceipt",resourceId:raw.resourceId,revision:1,contentHash:raw.contentHash};
    const expected=item.withdrawalReason==="unused_origin" ? ["withdraw"] : [];
    if(JSON.stringify(item.allowedActions)!==JSON.stringify(expected)) throw new Error("Invalid withdrawal hint");
  } else {
    if(item.registrationReceiptRef!==null || item.expectedInstallationEtag!==null || item.withdrawalReason!=="not_applicable" || item.allowedActions.length!==0) throw new Error("Unexpected registration action");
    if(item.state==="withdrawn") uuid(item.withdrawalReceiptId);
    else if(item.withdrawalReceiptId!==null) throw new Error("Unexpected withdrawal history");
  }
  return {...item,registrationReceiptRef:ref,allowedActions:[...item.allowedActions]} as RegistrationStatus;
}
