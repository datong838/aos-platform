import { useCallback, useEffect, useState } from "react";
import { aipProductionContracts, type EvidenceBundleListResponse, type TaskBriefListResponse } from "../../api/aipProductionContracts";
import { PageChrome } from "../../components/PageChrome";

export function ProductionContractsPage(){
  const[briefs,setBriefs]=useState<TaskBriefListResponse|null>(null),[bundles,setBundles]=useState<EvidenceBundleListResponse|null>(null),[error,setError]=useState(""),[busy,setBusy]=useState("");
  const load=useCallback(async()=>{try{const[briefData,bundleData]=await Promise.all([aipProductionContracts.listBriefs(),aipProductionContracts.listBundles()]);setBriefs(briefData);setBundles(bundleData);setError("");}catch(e){setBriefs(null);setBundles(null);setError(String((e as Error).message||e));}},[]);
  useEffect(()=>{void load();},[load]);
  async function freeze(briefId:string,version:number){setBusy(briefId);try{await aipProductionContracts.freezeBrief(briefId,version,`w2a-ui-freeze-${crypto.randomUUID()}`);await load();}catch(e){setError(String((e as Error).message||e));}finally{setBusy("");}}
  const loading=!briefs||!bundles;
  return <PageChrome title="生产契约" lede="Task Brief 与 Evidence Bundle 的 L0 权威视图；冻结不等于启动运行">
    {error&&<div role="alert" className="notice bad">生产契约读取失败：{error}</div>}
    {loading&&!error?<div role="status" className="card">正在读取 PostgreSQL Production Contract authority…</div>:null}
    {!loading?<>
      <div style={{display:"flex",gap:12,alignItems:"center",marginBottom:16,flexWrap:"wrap"}}><strong>{briefs.count} 份 Brief</strong><span>{bundles.count} 份 Evidence Bundle</span><button className="btn" onClick={()=>void load()}>刷新权威状态</button><button className="btn primary" disabled title="必须从已有真实 Task 创建；W2-A 不提供本地样例或隐式 Task">创建 Brief（需真实 Task）</button></div>
      <section style={{display:"grid",gridTemplateColumns:"minmax(0,1fr) minmax(0,1fr)",gap:16}}>
        <div className="card" style={{padding:18}}><h2 style={{marginTop:0}}>Task Brief</h2>{briefs.count===0?<div className="notice">当前组织尚无 Brief。请先从真实 Task 进入创建流程；本页不生成 Mock Task。</div>:briefs.items.map(item=><article key={item.briefId} style={{padding:"14px 0",borderTop:"1px solid var(--aos-border)"}}><div style={{display:"flex",justifyContent:"space-between",gap:12}}><strong>{item.briefType}</strong><span>{item.lifecycle==="frozen"?"已冻结":"草稿"}</span></div><p><code>{item.briefId}@{item.revision}</code> · Task <code>{item.taskId}</code></p><small>version {item.version} · hash {item.contentHash.slice(0,12)}…</small>{item.lifecycle==="draft"?<button className="btn" disabled={busy===item.briefId} onClick={()=>void freeze(item.briefId,item.version)} style={{marginTop:10}}>{busy===item.briefId?"冻结中…":"冻结当前 revision"}</button>:null}</article>)}</div>
        <div className="card" style={{padding:18}}><h2 style={{marginTop:0}}>Evidence Bundle</h2>{bundles.count===0?<div className="notice">当前组织尚无 Bundle。Bundle 只能聚合已授权 Evidence exact ref，不能复制正文或用摘要冒充事实。</div>:bundles.items.map(item=><article key={`${item.bundleId}@${item.revision}`} style={{padding:"14px 0",borderTop:"1px solid var(--aos-border)"}}><div style={{display:"flex",justifyContent:"space-between"}}><strong>{item.bundleId}</strong><span>{item.freshness}</span></div><p>{item.itemRefs.length} 条 Evidence · 覆盖 {item.coverage}</p><small>Brief {item.briefRef.resourceId}@{item.briefRef.revision}</small></article>)}</div>
      </section><div className="notice" style={{marginTop:16}}>运行门保持阻断：W2-A 只建立 Brief/Evidence authority；Eval、Responsibility、Stage、AIP-7 Route/Provider/Binding 未齐前不创建 AgentRun。</div>
    </>:null}
  </PageChrome>;
}
