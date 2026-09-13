import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach,beforeEach,expect,it,vi } from "vitest";
import { RegistrationPanel } from "./RegistrationPanel";
import { assetControlClient } from "../../../api/assetControl/client";
import { getTenant,setTenant } from "../../../api/tenant";
import type { RegistrationStatus } from "../../../api/assetControl/registrationStatus";
(globalThis as {IS_REACT_ACT_ENVIRONMENT?:boolean}).IS_REACT_ACT_ENVIRONMENT=true;
const id="11111111-1111-4111-8111-111111111111";
const status:RegistrationStatus={schemaVersion:"aos.ecommerce.first-dispatch-status/v1",installationId:id,state:"registered",registrationReceiptRef:{resourceType:"FirstDispatchRegistrationReceipt",resourceId:id,revision:1,contentHash:"sha256:"+"a".repeat(64)},withdrawalReceiptId:null,allowedActions:["withdraw"],executable:false,expectedInstallationEtag:5,withdrawalReason:"unused_origin"};
let host:HTMLDivElement,root:Root;
const original={...getTenant()};
beforeEach(()=>{host=document.createElement("div");document.body.appendChild(host);root=createRoot(host);vi.spyOn(assetControlClient,"getRegistrationStatus").mockResolvedValue(status);});
afterEach(()=>{act(()=>root.unmount());host.remove();vi.restoreAllMocks();setTenant(original);});
async function render(offline=false){await act(async()=>root.render(<RegistrationPanel installationId={id} offline={offline}/>));}
async function click(label:string){const b=Array.from(host.querySelectorAll("button")).find(x=>x.textContent===label);expect(b).toBeDefined();await act(async()=>b!.click());}
it("confirms exact withdrawal and refreshes history",async()=>{
  const send=vi.spyOn(assetControlClient,"withdrawRegistration").mockResolvedValue({receiptId:id,contentHash:"sha256:"+"b".repeat(64)});
  await render();await click("撤回未启用登记");await click("确认撤回登记");
  expect(send).toHaveBeenCalledTimes(1);expect(send.mock.calls[0][0].registrationReceiptRef).toEqual(status.registrationReceiptRef);
  expect(host.textContent).toContain("撤回已确认");
});
it("never resends an unknown result and reads the same intent",async()=>{
  const send=vi.spyOn(assetControlClient,"withdrawRegistration").mockRejectedValue(new Error("network"));
  const read=vi.spyOn(assetControlClient,"readRegistrationWithdrawal").mockResolvedValue({receiptId:id,contentHash:"sha256:"+"b".repeat(64)});
  await render();await click("撤回未启用登记");await click("确认撤回登记");
  expect(host.textContent).toContain("不会重复提交");expect(host.textContent).not.toContain("确认撤回登记");
  await click("回读撤回结果");expect(send).toHaveBeenCalledTimes(1);expect(read.mock.calls[0][0]).toBe(send.mock.calls[0][0]);
});
it("disables mutation offline",async()=>{
  await render(true);const button=Array.from(host.querySelectorAll("button")).find(b=>b.textContent==="撤回未启用登记")!;
  expect(button.disabled).toBe(true);
});
it("does not show service failure as an unregistered installation",async()=>{
  vi.mocked(assetControlClient.getRegistrationStatus).mockRejectedValue(new Error("unavailable"));
  await render();expect(host.querySelector('[role="alert"]')).not.toBeNull();expect(host.textContent).not.toContain("尚未登记");
});
it("clears old tenant data and ignores its late response",async()=>{
  let finish!:(s:RegistrationStatus)=>void;
  vi.mocked(assetControlClient.getRegistrationStatus).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;})).mockRejectedValue(new Error("denied"));
  await render();await act(async()=>setTenant({orgId:"isolated-test-org"}));
  await act(async()=>finish(status));
  expect(host.textContent).not.toContain("撤回未启用登记");expect(host.querySelector('[role="alert"]')).not.toBeNull();
});
