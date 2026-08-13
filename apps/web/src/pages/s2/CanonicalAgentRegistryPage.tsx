import { useCallback, useEffect, useState } from "react";
import { aipAgentControl, type AgentCatalogResponse } from "../../api/aipAgentControl";
import { PageChrome } from "../../components/PageChrome";

export function CanonicalAgentRegistryPage() {
  const [data, setData] = useState<AgentCatalogResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { setData(await aipAgentControl.listCatalog()); setError(""); } catch (e) { setData(null); setError(String((e as Error).message || e)); } }, []);
  useEffect(() => { void load(); }, [load]);
  async function install() { setBusy(true); try { await aipAgentControl.installEcommerce(`a6f-ui-${crypto.randomUUID()}`); await load(); } catch (e) { setError(String((e as Error).message || e)); } finally { setBusy(false); } }
  return <PageChrome title="智能体目录" lede="电商 SolutionPack 定义、组织实例与运行就绪度分层展示">
    {error && <div role="alert" className="notice bad">目录读取失败：{error}</div>}
    {!data ? <div role="status" className="card">正在读取 PostgreSQL Agent Registry…</div> : <>
      <div style={{display:"flex",gap:12,alignItems:"center",marginBottom:16,flexWrap:"wrap"}}>
        <strong>{data.stats.definitionCount} 个角色定义</strong><span>{data.stats.installedCount} 个已安装</span><span>{data.stats.skillDefinitionCount} 个技能定义</span><span>{data.stats.capabilityDefinitionCount} 类专业能力</span><span style={{color:"var(--aos-amber-700)"}}>可运行 {data.stats.runnableCount}</span>
        <button className="btn primary" disabled={busy || data.stats.installedCount === 6} onClick={() => void install()}>{busy ? "安装中…" : data.stats.installedCount === 6 ? "六数字同事已安装" : "安装电商六数字同事"}</button>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(300px,1fr))",gap:14}}>
        {data.items.map(item => <article key={item.template.templateId} className="card" style={{padding:18}}>
          <div style={{display:"flex",justifyContent:"space-between",gap:10}}><h3 style={{margin:0}}>{item.template.displayName}</h3><span>{item.instance ? "已安装 · 待配置" : "未安装"}</span></div>
          <p style={{color:"var(--aos-text-secondary)"}}>{item.template.manifest.responsibility} · {item.skills.length} 个 Logic</p>
          <div style={{fontSize:13}}>模板：<code>{item.template.templateId}@{item.template.revision}</code></div>
          <div style={{fontSize:13,marginTop:8}}>所需能力：{item.requiredCapabilityIds.join("、") || "无"}</div>
          <div style={{marginTop:10,padding:10,background:"var(--aos-amber-bg)",color:"var(--aos-amber-700)"}}>运行已阻断：技能尚未发布、能力未绑定、模型路由未就绪。</div>
        </article>)}
      </div>
    </>}
  </PageChrome>;
}
