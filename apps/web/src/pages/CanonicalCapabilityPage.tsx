import { Link } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import { aipAgentControl, type AgentRuntimeReadinessResponse, type CapabilityCatalogResponse, type OperationalBindingDependencies } from "../api/aipAgentControl";
import { PageChrome } from "../components/PageChrome";
import { AipOperationalProjectionStrip } from "../components/aip/AipOperationalProjectionStrip";
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

/** W-B1: org-binding badge must never say 未绑定 when a binding row exists. */
export function orgBindingStatusLabel(bindingsLength: number, activeCount: number): string {
  if (bindingsLength === 0) return "未绑定";
  if (activeCount > 0) return bindingStatusDisplayName("active");
  return "待激活";
}

export function CanonicalCapabilityPage() {
  const [catalog, setCatalog] = useState<CapabilityCatalogResponse | null>(null);
  const [runtime, setRuntime] = useState<AgentRuntimeReadinessResponse | null>(null);
  const [error, setError] = useState("");
  const [expandedCapabilityId, setExpandedCapabilityId] = useState<string | null>(() => new URLSearchParams(window.location.search).get("capabilityId"));
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

  return <PageChrome title="智能体插件" lede="10 类共享专业能力：组织绑定与定义八维分栏阅读">
    <AipOperationalProjectionStrip />
    {catalog && runtime ? (
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 14 }}>
        {[
          ["定义", catalog.count],
          ["目录可用", catalog.availableCount],
          ["组织绑定", runtime.bindingStats.capabilityBindingCount],
          ["已激活", runtime.bindingStats.activeCapabilityBindingCount],
          ["技能绑定", runtime.bindingStats.skillBindingCount],
        ].map(([name, count]) => (
          <div key={String(name)} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{name}</div>
            <div style={{ fontSize: 22, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{count}</div>
          </div>
        ))}
      </div>
    ) : null}
    <div style={{display:"flex",gap:12,marginBottom:16,alignItems:"center",flexWrap:"wrap"}}>
      <button className="btn" onClick={() => void load()}>刷新</button>
      <Link to="/aip/agent-registry">智能体目录 →</Link>
      <Link to="/aip/capability-import">能力导入 →</Link>
      <span className="notice" style={{ padding: "6px 10px" }}>密表卡片 · 组织绑定 ≠ 定义八维</span>
    </div>
    <div className="notice" style={{marginBottom:14,padding:10}} role="note">
      两层状态请分开看：<strong>组织绑定</strong>表示本租户是否已创建绑定记录；<strong>定义就绪</strong>表示供应商、路由、评测、许可、数据、工具与预算条件是否齐备。条件待补齐不等于「未绑定」。
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
        const orgLabel = orgBindingStatusLabel(bindings.length, active.length);
        const orgColor = unbound ? "var(--aos-amber-700)" : active.length ? "var(--aos-green-700)" : "var(--aos-amber-700)";
        const defLabel = definitionReadinessDisplayName(item.readiness);
        const orgReason = unbound
          ? "当前组织尚未创建该专业能力的绑定。请经智能体目录完成绑定后再预检。"
          : (binding?.readinessReasons?.length
            ? formatBlockers(binding.readinessReasons)
            : (missing.length ? `依赖投影缺：${missing.join(" / ")}` : "组织绑定侧暂无额外阻断说明。"));
        const defReason = item.readinessReasons?.length
          ? formatBlockers(item.readinessReasons)
          : (item.readiness === "available" ? "定义层投影可用。" : "定义层暂无额外说明。");
        const precheckOk = Boolean(binding && missing.length === 0 && snapshotReady);
        const applicableRoles = runtime.catalog.items
          .filter(agent => agent.requiredCapabilityIds.includes(item.capabilityId) || agent.skills.some(skill => skill.requiredCapabilities.includes(item.capabilityId)))
          .map(agent => agent.template.displayName);
        const inputName = item.inputSchemaRef?.assetId || "由业务任务按契约提供";
        const outputName = item.outputSchemaRef?.assetId || "按能力契约形成业务产物";
        const dependencyCount = (item.requiredDataRefs?.length || 0) + (item.requiredToolRefs?.length || 0) + (item.requiredCapabilityRefs?.length || 0);
        const expanded = expandedCapabilityId === item.capabilityId;
        const query = `capabilityId=${encodeURIComponent(item.capabilityId)}&revision=${item.revision}`;
        return <article key={item.capabilityId} className="card" style={{padding:18}}>
          <div style={{display:"flex",justifyContent:"space-between",gap:10,alignItems:"start",flexWrap:"wrap"}}>
            <h3 style={{margin:0}}>{item.displayName}</h3>
            <div style={{display:"flex",gap:8,flexWrap:"wrap",justifyContent:"flex-end"}}>
              <strong data-testid="org-binding-badge" style={{color:orgColor}}>组织绑定：{orgLabel}</strong>
              <strong data-testid="definition-ready-badge" style={{color:item.readiness === "available" ? "var(--aos-green-700)" : "var(--aos-amber-700)"}}>定义就绪：{defLabel}</strong>
            </div>
          </div>
          <p style={{color:"var(--aos-text-secondary)",margin:"6px 0"}}>用于业务流程中的“{item.displayName}”步骤；输入与产物均遵守当前发布版本的结构契约。</p>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(150px,1fr))",gap:8,margin:"10px 0"}}>
            <div className="notice" style={{padding:9}}><strong>输入</strong><div>{inputName}</div></div>
            <div className="notice" style={{padding:9}}><strong>产物</strong><div>{outputName}</div></div>
            <div className="notice" style={{padding:9}}><strong>风险</strong><div>{riskDisplayName(item.riskLevel)}</div></div>
            <div className="notice" style={{padding:9}}><strong>适用同事</strong><div>{applicableRoles.length ? applicableRoles.join("、") : "由业务逻辑按需编排"}</div></div>
          </div>
          <p style={{color:"var(--aos-text-secondary)",margin:"6px 0"}}>当前版本 v{item.revision} · 组织绑定 {bindings.length} 条 · 定义依赖 {dependencyCount} 项</p>
          <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>{dimensions.map(([key,label]) => <span key={key} className="notice" style={{padding:"4px 7px",color:binding && present(binding.dependencies[key]) ? "var(--aos-green-700)" : "var(--aos-amber-700)"}}>{dimensionDisplayName(key) || label} {binding && present(binding.dependencies[key]) ? "✓" : "—"}</span>)}</div>
          <div style={{marginTop:10,display:"grid",gap:8}}>
            <div style={{padding:10,background:"var(--aos-amber-bg)"}}><strong>组织绑定侧</strong>：{orgReason}</div>
            <div style={{padding:10,background:"var(--aos-surface-2, #f4f4f5)"}}><strong>定义层</strong>：{defReason}</div>
          </div>
          <div style={{display:"flex",gap:8,marginTop:12,flexWrap:"wrap",alignItems:"center"}}>
            {unbound ? <Link className="btn" to={`/aip/agent-registry?${query}`}>去目录绑定</Link> : null}
            {precheckOk
              ? <button className="btn" aria-expanded={expanded} onClick={() => setExpandedCapabilityId(expanded ? null : item.capabilityId)} title="核对当前专业能力依赖快照">{expanded ? "收起运行条件" : "核对运行条件"}</button>
              : <Link className="btn" to={`/aip/agent-registry?${query}`} title={!binding ? "需先创建组织专业能力绑定" : missing.length ? `缺少 ${missing.join(" / ")}` : "依赖快照过期，请刷新绑定状态"}>补齐预检条件</Link>}
            <Link className="btn" to={`/aip/agent-registry?${query}&intent=activate`} title={snapshotReady ? "进入专用确认流" : "先补齐新鲜依赖快照，再进入确认流"}>进入激活确认</Link>
          </div>
          {expanded ? <section aria-label={`${item.displayName}运行条件`} style={{marginTop:12,padding:12,border:"1px solid var(--aos-border)",display:"grid",gap:8}}>
            <strong>当前版本与运行依赖</strong>
            <div>能力标识：{item.capabilityId} · v{item.revision}</div>
            <div>组织绑定：{binding?.bindingId || "尚未创建"} · {binding ? bindingStatusDisplayName(binding.status) : "待绑定"}</div>
            <div>依赖快照：{snapshotReady ? "有效" : "待刷新"} · {binding?.readinessExpiresAt ? `有效期至 ${new Date(binding.readinessExpiresAt).toLocaleString("zh-CN")}` : "暂无截止时间"}</div>
            <div>定义依赖：数据 {item.requiredDataRefs?.length || 0} · 工具 {item.requiredToolRefs?.length || 0} · 前置能力 {item.requiredCapabilityRefs?.length || 0} · 评测包 {item.evalPackRef ? "已绑定" : "待核对"}</div>
            <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
              <Link to={`/aip/agents?${query}`}>查看使用该能力的数字同事 →</Link>
              <Link to={`/aip/logic?${query}`}>查看业务逻辑 →</Link>
              <Link to={`/aip/tools?${query}`}>查看工具依赖 →</Link>
              <Link to={`/workshop/cockpit?${query}`}>查看工作台贡献 →</Link>
            </div>
          </section> : null}
        </article>;
      })}
    </div>}
  </PageChrome>;
}
