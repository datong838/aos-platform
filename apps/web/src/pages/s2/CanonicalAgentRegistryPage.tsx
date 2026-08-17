import { useCallback, useEffect, useMemo, useState } from "react";
import { aipAgentControl, type AgentRuntimeReadinessResponse } from "../../api/aipAgentControl";
import { PageChrome } from "../../components/PageChrome";

function statusLabel(status: string | undefined) {
  return ({ provisioning: "待配置", active: "已启用", suspended: "已暂停", deleted: "已删除" } as Record<string, string>)[status || ""] || "未安装";
}

export function runtimeSnapshotStale(evaluatedAt: string, now = Date.now()): boolean {
  return now - Date.parse(evaluatedAt) > 15 * 60 * 1000;
}

export function CanonicalAgentRegistryPage() {
  const [data, setData] = useState<AgentRuntimeReadinessResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { setData(await aipAgentControl.runtimeReadiness()); setError(""); }
    catch (e) { setData(null); setError(String((e as Error).message || e)); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function install() {
    setBusy(true);
    try { await aipAgentControl.installEcommerce(`a6f-ui-${crypto.randomUUID()}`); await load(); }
    catch (e) { setError(String((e as Error).message || e)); }
    finally { setBusy(false); }
  }
  const stale = useMemo(() => data ? runtimeSnapshotStale(data.evaluatedAt) : false, [data]);
  return <PageChrome title="智能体目录" lede="六数字同事的模板、实例、Skill 与 Capability 运行绑定真相">
    {error && <div role="alert" className="notice bad">运行就绪度读取失败：{error}</div>}
    {!data ? <div role="status" className="card">正在读取 PostgreSQL Agent Registry 与 Binding…</div> : <>
      <section className="card" style={{padding:18,marginBottom:16}}>
        <div style={{display:"flex",gap:14,alignItems:"center",flexWrap:"wrap"}}>
          <strong>{data.catalog.stats.definitionCount} 个角色定义</strong>
          <span>{data.catalog.stats.installedCount} 个已安装</span>
          <span>{data.catalog.stats.skillDefinitionCount} 个技能定义</span>
          <span>{data.catalog.stats.capabilityDefinitionCount} 类专业能力</span>
          <span>Skill Binding {data.bindingStats.activeSkillBindingCount}/{data.bindingStats.skillBindingCount} active</span>
          <span>Capability Binding {data.bindingStats.activeCapabilityBindingCount}/{data.bindingStats.capabilityBindingCount} active</span>
          <strong style={{color:"var(--aos-amber-700)"}}>可运行 {data.catalog.stats.runnableCount}</strong>
          <button className="btn primary" disabled={busy || data.catalog.stats.installedCount === data.catalog.stats.definitionCount} onClick={() => void install()}>{busy ? "安装中…" : data.catalog.stats.installedCount === data.catalog.stats.definitionCount ? "六数字同事已安装" : "安装电商六数字同事"}</button>
          <button className="btn" onClick={() => void load()}>刷新</button>
        </div>
        <div style={{marginTop:10,fontSize:13,color:stale ? "var(--aos-amber-700)" : "var(--aos-text-secondary)"}}>
          快照 {new Date(data.evaluatedAt).toLocaleString()} · {stale ? "已过期，请刷新后再判断" : "15 分钟有效期内"}
        </div>
      </section>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(360px,1fr))",gap:14}}>
        {data.catalog.items.map(item => {
          const instanceId = item.instance?.instanceId;
          const bindings = data.skillBindings.filter(binding => binding.instanceId === instanceId);
          const activeBindings = bindings.filter(binding => binding.status === "active");
          const requiredBindingCount = data.capabilityBindings.filter(binding => item.requiredCapabilityIds.includes(binding.capability.assetId)).length;
          return <article key={item.template.templateId} className="card" style={{padding:18}}>
            <div style={{display:"flex",justifyContent:"space-between",gap:10,alignItems:"start"}}>
              <div><h3 style={{margin:0}}>{item.template.displayName}</h3><small><code>{item.template.templateId}@{item.template.revision}</code></small></div>
              <strong style={{color:item.instance?.status === "active" ? "var(--aos-green-700)" : "var(--aos-amber-700)"}}>{statusLabel(item.instance?.status)}</strong>
            </div>
            <p style={{color:"var(--aos-text-secondary)"}}>{item.template.manifest.responsibility}</p>
            <div style={{display:"grid",gridTemplateColumns:"repeat(2,minmax(0,1fr))",gap:8,fontSize:13}}>
              <div className="notice">Skill {activeBindings.length}/{item.skills.length} 已绑定</div>
              <div className="notice">Capability {requiredBindingCount}/{item.requiredCapabilityIds.length} 已绑定</div>
            </div>
            <details style={{marginTop:12}}><summary>查看 {item.skills.length} 个 Skill 状态</summary>
              <ul>{item.skills.map(skill => { const binding = bindings.find(value => value.skill.assetId === skill.skillId); return <li key={skill.skillId}><code>{skill.canonicalLogicId}</code> · {skill.lifecycle === "published" ? "已发布" : "仅已评测"} · {binding ? `绑定 ${binding.status}` : "未绑定"}</li>; })}</ul>
            </details>
            <div style={{marginTop:10,padding:10,background:"var(--aos-amber-bg)",color:"var(--aos-amber-700)"}}>
              {item.blockers.length ? item.blockers.join("；") : "缺少完整 Capability/Skill 绑定与依赖快照，运行失败关闭"}
            </div>
            <button className="btn" disabled title="需先完成 Skill 发布、Capability 绑定、八维依赖与新鲜快照" style={{marginTop:12}}>预检运行（依赖未齐）</button>
          </article>;
        })}
      </div>
    </>}
  </PageChrome>;
}
