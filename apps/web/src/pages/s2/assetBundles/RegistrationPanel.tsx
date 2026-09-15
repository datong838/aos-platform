import { normalizeAssetControlError } from "../../../api/assetControl/errors";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { getTenant } from "../../../api/tenant";
import { assetControlClient } from "../../../api/assetControl/client";
import type { RegistrationStatus } from "../../../api/assetControl/registrationStatus";
import { createWithdrawalIntent, type WithdrawalIntent } from "../../../api/assetControl/registrationWithdrawal";
import { createIdempotentCommand, idempotencyKeyFor } from "../../../api/assetControl/idempotency";
const identity=()=>{const t=getTenant();return JSON.stringify([t.orgId,t.projectId,t.subject,t.roles]);};
const subscribe=(f:()=>void)=>{window.addEventListener("aos-tenant-updated",f);return()=>window.removeEventListener("aos-tenant-updated",f);};
export function RegistrationPanel({installationId,offline}:{installationId:string|null;offline:boolean}) {
  const scope=useSyncExternalStore(subscribe,identity,identity);
  return installationId ? <RegistrationDetails key={scope+installationId} installationId={installationId} scope={scope} offline={offline}/> : null;
}
const reasons={unused_origin:"登记尚未进入业务执行，可撤回后重新准备。",dependent_history:"已有业务切换或任务记录，不能按未启用登记撤回。",dispatch_changed:"登记状态已变化，需要核对当前运行记录。",successor_history:"已登记接续原安装的业务，历史记录保留；实际接管仍需评审与切换确认。",not_applicable:""};
function RegistrationDetails({installationId,scope,offline}:{installationId:string;scope:string;offline:boolean}) {
  const [data,setData]=useState<RegistrationStatus|null>(null);
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[confirm,setConfirm]=useState(false);
  const [error,setError]=useState<string|null>(null),[message,setMessage]=useState<string|null>(null);
  const [intent,setIntent]=useState<WithdrawalIntent|null>(null);
  const alive=useRef(true),sequence=useRef(0),inflight=useRef(false);
  const current=()=>alive.current && identity()===scope;
  async function load() {
    const ticket=++sequence.current;setLoading(true);setData(null);setConfirm(false);setError(null);
    try {const result=await assetControlClient.getRegistrationStatus(installationId);if(current()&&ticket===sequence.current)setData(result);}
    catch (cause) {if(current()&&ticket===sequence.current) {
      const failure=normalizeAssetControlError(cause);
      setError(failure.status===403 ? "当前身份无权读取此安装的登记状态。" :
        failure.status===503 ? "登记服务暂不可用，请在服务恢复后刷新。" :
        "暂时无法读取登记状态，请检查服务和当前访问权限后刷新。");
    }}
    finally {if(current()&&ticket===sequence.current)setLoading(false);}
  }
  useEffect(()=>{alive.current=true;void load();return()=>{alive.current=false;sequence.current++;};},[]);
  async function execute(readOnly:boolean) {
    if(!current()||offline||inflight.current||loading)return;
    if(!readOnly&&(!data?.allowedActions.includes("withdraw")||intent))return;
    const command=readOnly?intent:createWithdrawalIntent(data!,idempotencyKeyFor(createIdempotentCommand()));
    if(!command)return;
    inflight.current=true;setBusy(true);setConfirm(false);setIntent(command);setError(null);
    try {
      if(readOnly)await assetControlClient.readRegistrationWithdrawal(command);
      else await assetControlClient.withdrawRegistration(command);
      if(!current())return;
      setIntent(null);setMessage("撤回已确认，准备占位已释放，历史记录与业务数据保留。");await load();
    } catch {
      if(current()){setData(null);setError("尚未确认撤回完成。请回读原请求结果；系统不会重复提交。");}
    } finally {inflight.current=false;if(current())setBusy(false);}
  }
  return <section aria-label="电商业务登记" style={{border:"1px solid var(--aos-border)",padding:12,borderRadius:3}}>
    <h3>电商业务登记</h3>
    {loading&&<p role="status">正在读取登记状态…</p>}
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    {data&&<p>{data.state==="unregistered"?"当前安装尚未登记业务。":data.state==="withdrawn"?"未启用登记已撤回，历史记录已保留。":data.state==="needs_attention"?"发现多份未撤回登记，需要核对安装记录。":reasons[data.withdrawalReason]}</p>}
    <button disabled={loading||busy||offline} onClick={()=>void load()}>刷新登记状态</button>
    {intent&&<button disabled={busy||loading||offline} onClick={()=>void execute(true)}>回读撤回结果</button>}
    {data?.allowedActions.includes("withdraw")&&!intent&&<button disabled={busy||loading||offline} onClick={()=>setConfirm(true)}>撤回未启用登记</button>}
    {confirm&&<div role="group" aria-label="确认撤回登记"><p>仅释放尚未使用的准备占位，保留历史记录与业务数据。</p><button disabled={busy||loading||offline} onClick={()=>void execute(false)}>确认撤回登记</button><button onClick={()=>setConfirm(false)}>取消</button></div>}
  </section>;
}
