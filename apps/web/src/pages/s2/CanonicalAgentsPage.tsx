import { useCallback, useEffect, useState } from "react";
import { aipAgentControl, type AgentInstanceListResponse } from "../../api/aipAgentControl";
import { PageChrome } from "../../components/PageChrome";

export function CanonicalAgentsPage() {
  const [data,setData]=useState<AgentInstanceListResponse|null>(null); const [error,setError]=useState("");
  const load=useCallback(async()=>{try{setData(await aipAgentControl.listInstances());setError("");}catch(e){setError(String((e as Error).message||e));}},[]);
  useEffect(()=>{void load();},[load]);
  return <PageChrome title="智能体列表" lede="当前组织与工作区的 AgentInstance；运行前置门未满足时诚实失败关闭">
    {error&&<div role="alert" className="notice bad">实例读取失败：{error}</div>}
    {!data?<div className="card">正在读取组织实例…</div>:data.count===0?<div className="card"><h3>尚未安装智能体</h3><p>请先在“智能体目录”安装电商六数字同事。本页不显示本地样例。</p></div>:<div style={{display:"grid",gap:12}}>{data.items.map(item=><article className="card" key={item.instanceId} style={{padding:18,display:"grid",gridTemplateColumns:"1fr auto",gap:12}}><div><h3 style={{margin:0}}>{item.overlay.displayName||item.instanceId}</h3><p><code>{item.instanceId}</code> · 模板 <code>{item.template.assetId}@{item.template.revision}</code></p><small>组织 {item.tenant.orgId} · 工作区 {item.tenant.projectId} · revision {item.version}</small></div><div><strong>{item.status==="provisioning"?"待配置":item.status}</strong><p style={{color:"var(--aos-amber-700)"}}>无 Skill/Capability Binding，不能试运行</p></div></article>)}</div>}
  </PageChrome>;
}
