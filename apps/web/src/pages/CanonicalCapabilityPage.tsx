import { Link } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import { aipAgentControl, type AgentRuntimeReadinessResponse, type CapabilityCatalogResponse, type OperationalBindingDependencies } from "../api/aipAgentControl";
import { PageChrome } from "../components/PageChrome";
import {
  bindingStatusDisplayName,
  definitionReadinessDisplayName,
  dimensionDisplayName,
  formatBlockers,
  riskDisplayName,
} from "../lib/aipChineseLabels";

const dimensions: Array<[keyof OperationalBindingDependencies, string]> = [
  ["providerRef", "供应商"],
  ["modelRouteRef", "路由"],
  ["evalGateRef", "评测门"],
  ["licenseEvidenceRefs", "许可"],
  ["dataDependencyRefs", "数据依赖"],
  ["toolDependencyRefs", "工具依赖"],
  ["budgetPolicyRef", "预算策略"],
];
function present(value: OperationalBindingDependencies[keyof OperationalBindingDependencies]): boolean {
  return Array.isArray(value) ? value.length > 0 : Boolean(value);
}

export function CanonicalCapabilityPage() {
  const [catalog, setCatalog] = useState<CapabilityCatalogResponse | null>(null);
  const [runtime, setRuntime] = useState<AgentRuntimeReadinessResponse | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const [nextCatalog, nextRuntime] = await Promise.all([
        aipAgentControl.listCapabilities(),
        aipAgentControl.runtimeReadiness(),
      ]);
      setCatalog(nextCatalog);
      setRuntime(nextRuntime);
      setError("");
    } catch (e) {
      setCatalog(null);
      setRuntime(null);
      setError(String((e as Error).message || e));
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return <PageChrome title="智能体插件" lede="10 类共享专业能力定义与当前组织绑定的八维就绪度">
    <div style={{display:"flex",gap:12,marginBottom:16,alignItems:"center",flexWrap:"wrap"}}>
      <button className="btn" onClick={() => void load()}>刷新</button>
      <Link to="/aip/agent-registry">智能体目录 →</Link>
      <Link to="/aip/capability-import">能力导入 →</Link>
      {catalog && runtime && <><strong>{catalog.count} 个定义</strong><span>组织绑定 {runtime.bindingStats.capabilityBindingCount}</span><span>已激活 {runtime.bindingStats.activeCapabilityBindingCount}</span><span>目录可用 {catalog.availableCount}</span></>}
    </div>
    {error && <div role="alert" className="notice bad">专业能力权威读取失败：{error}</div>}
    {!catalog || !runtime ? <div role="status" className="card">正在读取专业能力目录与组织绑定…</div> : <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(340px,1fr))",gap:14}}>
      {catalog.items.map(item => {
        const bindings = runtime.capabilityBindings.filter(binding => binding.capability.assetId === item.capabilityId && binding.capability.revision === item.revision);
        const active = bindings.filter(binding => binding.status === "active");
        const binding = active[0] || bindings[0];
        const missing = binding ? dimensions.filter(([key]) => !present(binding.dependencies[key])).map(([,label]) => label) : dimensions.map(([,label]) => label);
        const snapshotReady = Boolean(binding?.dependencySnapshotHash && binding.readinessExpiresAt && Date.parse(binding.readinessExpiresAt) > Date.now());
        const unbound = bindings.length === 0;
        const statusLabel = unbound ? "未绑定" : active.length ? bindingStatusDisplayName("active") : "未就绪";
        const statusColor = unbound ? "var(--aos-amber-700)" : active.length ? "var(--aos-green-700)" : "var(--aos-amber-700)";
        const reasonText = unbound
          ? "当前组织尚未创建该专业能力的绑定；定义层未就绪不等于运维失败。请经智能体目录完成技能/专业能力绑定后再预检。"
          : (binding?.readinessReasons.length
            ? formatBlockers(binding.readinessReasons)
            : item.readinessReasons.length
              ? formatBlockers(item.readinessReasons)
              : `缺少 ${missing.join(" / ")}`);
        const precheckOk = Boolean(binding && missing.length === 0 && snapshotReady);
        return <article key={item.capabilityId} className="card" style={{padding:18}}>
          <div style={{display:"flex",justifyContent:"space-between",gap:10}}><h3 style={{margin:0}}>{item.displayName}</h3><strong style={{color:statusColor}}>{statusLabel}</strong></div>
          <p style={{color:"var(--aos-text-secondary)",margin:"6px 0"}}>风险 {riskDisplayName(item.riskLevel)} · 组织绑定 {bindings.length} · {definitionReadinessDisplayName(item.readiness)}</p>
          <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>{dimensions.map(([key,label]) => <span key={key} className="notice" style={{padding:"4px 7px",color:binding && present(binding.dependencies[key]) ? "var(--aos-green-700)" : "var(--aos-amber-700)"}}>{dimensionDisplayName(key) || label} {binding && present(binding.dependencies[key]) ? "✓" : "—"}</span>)}</div>
          <div style={{marginTop:10,padding:10,background:"var(--aos-amber-bg)"}}>{reasonText}</div>
          <div style={{display:"flex",gap:8,marginTop:12,flexWrap:"wrap",alignItems:"center"}}>
            {unbound ? <Link className="btn" to="/aip/agent-registry">去目录绑定</Link> : null}
            <button className="btn" disabled={!precheckOk} title={!binding ? "需先创建组织专业能力绑定" : missing.length ? `缺少 ${missing.join(" / ")}` : !snapshotReady ? "依赖快照过期，请刷新绑定就绪度" : "当前只读页尚未取得命令确认"}>预检{precheckOk ? "" : unbound ? "（未绑定）" : missing.length ? "（依赖未齐）" : "（快照不可用）"}</button>
            <button className="btn" disabled title={snapshotReady ? "写命令需在专用确认流执行" : "缺少新鲜依赖快照"}>激活{snapshotReady ? "（待确认）" : "（快照不可用）"}</button>
          </div>
        </article>;
      })}
    </div>}
  </PageChrome>;
}
