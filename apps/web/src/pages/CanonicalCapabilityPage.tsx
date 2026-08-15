import { useCallback, useEffect, useState } from "react";
import { aipAgentControl, type AgentRuntimeReadinessResponse, type CapabilityCatalogResponse, type OperationalBindingDependencies } from "../api/aipAgentControl";
import { PageChrome } from "../components/PageChrome";

const dimensions: Array<[keyof OperationalBindingDependencies, string]> = [
  ["providerRef", "Provider"], ["modelRouteRef", "Route"], ["evalGateRef", "Eval"], ["licenseEvidenceRefs", "License"],
  ["dataDependencyRefs", "Data"], ["toolDependencyRefs", "Tool"], ["budgetPolicyRef", "Budget"],
];
function present(value: OperationalBindingDependencies[keyof OperationalBindingDependencies]): boolean { return Array.isArray(value) ? value.length > 0 : Boolean(value); }

export function CanonicalCapabilityPage() {
  const [catalog, setCatalog] = useState<CapabilityCatalogResponse | null>(null);
  const [runtime, setRuntime] = useState<AgentRuntimeReadinessResponse | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try { const [nextCatalog, nextRuntime] = await Promise.all([aipAgentControl.listCapabilities(), aipAgentControl.runtimeReadiness()]); setCatalog(nextCatalog); setRuntime(nextRuntime); setError(""); }
    catch (e) { setCatalog(null); setRuntime(null); setError(String((e as Error).message || e)); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  return <PageChrome title="智能体插件" lede="10 类共享专业 Capability 定义与当前组织 Binding 八维就绪度">
    <div style={{display:"flex",gap:12,marginBottom:16,alignItems:"center",flexWrap:"wrap"}}>
      <button className="btn" onClick={() => void load()}>刷新</button>
      {catalog && runtime && <><strong>{catalog.count} 个定义</strong><span>组织绑定 {runtime.bindingStats.capabilityBindingCount}</span><span>active {runtime.bindingStats.activeCapabilityBindingCount}</span><span>目录可用 {catalog.availableCount}</span></>}
    </div>
    {error && <div role="alert" className="notice bad">Capability 权威读取失败：{error}</div>}
    {!catalog || !runtime ? <div role="status" className="card">正在读取 Capability Registry 与组织 Binding…</div> : <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(340px,1fr))",gap:14}}>
      {catalog.items.map(item => {
        const bindings = runtime.capabilityBindings.filter(binding => binding.capability.assetId === item.capabilityId && binding.capability.revision === item.revision);
        const active = bindings.filter(binding => binding.status === "active");
        const binding = active[0] || bindings[0];
        const missing = binding ? dimensions.filter(([key]) => !present(binding.dependencies[key])).map(([,label]) => label) : dimensions.map(([,label]) => label);
        const snapshotReady = Boolean(binding?.dependencySnapshotHash && binding.readinessExpiresAt && Date.parse(binding.readinessExpiresAt) > Date.now());
        return <article key={item.capabilityId} className="card" style={{padding:18}}>
          <div style={{display:"flex",justifyContent:"space-between",gap:10}}><h3 style={{margin:0}}>{item.displayName}</h3><strong style={{color:active.length ? "var(--aos-green-700)" : "var(--aos-amber-700)"}}>{active.length ? "active" : "blocked"}</strong></div>
          <p><code>{item.capabilityId}@{item.revision}</code> · 风险 {item.riskLevel} · 组织绑定 {bindings.length}</p>
          <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>{dimensions.map(([key,label]) => <span key={key} className="notice" style={{padding:"4px 7px",color:binding && present(binding.dependencies[key]) ? "var(--aos-green-700)" : "var(--aos-amber-700)"}}>{label} {binding && present(binding.dependencies[key]) ? "✓" : "—"}</span>)}</div>
          <div style={{marginTop:10,padding:10,background:"var(--aos-amber-bg)"}}>{binding?.readinessReasons.length ? binding.readinessReasons.join("；") : item.readinessReasons.join("；") || `缺少 ${missing.join(" / ")}`}</div>
          <div style={{display:"flex",gap:8,marginTop:12,flexWrap:"wrap"}}>
            <button className="btn" disabled={!binding || missing.length > 0} title={!binding ? "需先创建组织 CapabilityBinding" : missing.length ? `缺少 ${missing.join(" / ")}` : "当前只读页尚未取得命令确认"}>预检{!binding || missing.length ? "（依赖未齐）" : ""}</button>
            <button className="btn" disabled title={snapshotReady ? "写命令需在专用确认流执行" : "缺少新鲜 dependency snapshot"}>激活{snapshotReady ? "（待确认）" : "（快照不可用）"}</button>
          </div>
        </article>;
      })}
    </div>}
  </PageChrome>;
}
