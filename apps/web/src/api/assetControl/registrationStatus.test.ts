import { describe, expect, it } from "vitest";
import { parseRegistrationStatus } from "./registrationStatus";
const id = "11111111-1111-4111-8111-111111111111";
const fixture = () => ({schemaVersion:"aos.ecommerce.first-dispatch-status/v1",installationId:id,
  state:"registered",registrationReceiptRef:{resourceType:"FirstDispatchRegistrationReceipt",resourceId:id,revision:1,contentHash:"sha256:"+"a".repeat(64)},
  withdrawalReceiptId:null,allowedActions:["withdraw"],executable:false,expectedInstallationEtag:5,withdrawalReason:"unused_origin"});
describe("registration status boundary",()=>{
  it("accepts a server hint without granting business execution",()=>{
    expect(parseRegistrationStatus(fixture()).allowedActions).toEqual(["withdraw"]);
  });
  it.each(["extra","execution","unsafe-etag","hash","state","action","missing-ref","reason"])("rejects invalid %s",defect=>{
    const value: any=fixture();
    if(defect==="extra")value.force=true;
    if(defect==="execution")value.executable=true;
    if(defect==="unsafe-etag")value.expectedInstallationEtag=Number.MAX_SAFE_INTEGER+1;
    if(defect==="hash")value.registrationReceiptRef.contentHash="bad";
    if(defect==="state")value.state="withdrawn";
    if(defect==="action")value.allowedActions=["enable"];
    if(defect==="missing-ref")value.registrationReceiptRef=null;
    if(defect==="reason")value.withdrawalReason="dependent_history";
    expect(()=>parseRegistrationStatus(value)).toThrow();
  });
  it.each(["unregistered","withdrawn","needs_attention"])("accepts %s without actions",state=>{
    const value={...fixture(),state,registrationReceiptRef:null,allowedActions:[],expectedInstallationEtag:null,withdrawalReason:"not_applicable",withdrawalReceiptId:state==="withdrawn"?id:null};
    expect(parseRegistrationStatus(value).state).toBe(state);
  });
});
