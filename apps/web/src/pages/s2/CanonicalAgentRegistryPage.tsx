import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { aipAgentControl, type AgentRuntimeReadinessResponse } from "../../api/aipAgentControl";
import { PageChrome } from "../../components/PageChrome";
import { AipOperationalProjectionStrip } from "../../components/aip/AipOperationalProjectionStrip";
import {
  agentReadinessLadderSummary,
  bindingStatusDisplayName,
  deriveAgentReadinessLadder,
  formatBlockers,
  logicDisplayName,
  responsibilityDisplayName,
} from "../../lib/aipChineseLabels";

function statusLabel(status: string | undefined) {
  return ({ provisioning: "待配置", active: "已启用", suspended: "已暂停", deleted: "已删除" } as Record<string, string>)[status || ""] || "未安装";
}

function freshAt(expiresAt: string | null, now = Date.now()): boolean {
  return expiresAt !== null && Date.parse(expiresAt) > now;
}

function ReadinessLadderStrip({ ladder }: { ladder: ReturnType<typeof deriveAgentReadinessLadder> }) {
  return (
    <div data-testid="agent-readiness-ladder" aria-label="分栏就绪阶梯" style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10, fontSize: 12 }}>
      {ladder.stages.map((stage) => (
        <span
          key={stage.id}
          data-stage={stage.id}
          data-done={stage.done ? "1" : "0"}
          style={{
            padding: "2px 8px",
            borderRadius: 4,
            border: "1px solid var(--aos-border)",
            background: stage.done ? (stage.id === "runnable" ? "var(--aos-green-bg, #ecfdf3)" : "var(--aos-surface)") : "transparent",
            color: stage.done ? (stage.id === "runnable" ? "var(--aos-green-700)" : "var(--aos-text-secondary)") : "var(--aos-text-secondary)",
            opacity: stage.done ? 1 : 0.55,
          }}
        >
          {stage.label}
        </span>
      ))}
    </div>
  );
}

export function runtimeSnapshotStale(evaluatedAt: string, now = Date.now()): boolean {
  return now - Date.parse(evaluatedAt) > 15 * 60 * 1000;
}

export function precheckDisabledTitle(blockers: string[]): string {
  if (!blockers.length) return "缺少完整能力/技能绑定与依赖快照";
  if (blockers.every((code) => /_stale$|_stale:/.test(code) || code.endsWith("_stale"))) {
    return "就绪快照已过期：请点击本页「刷新」重评绑定。";
  }
  return formatBlockers(blockers);
}

export function CanonicalAgentRegistryPage() {
  const [data, setData] = useState<AgentRuntimeReadinessResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [precheckedTemplateId, setPrecheckedTemplateId] = useState<string | null>(null);
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
  async function refresh() {
    setRefreshing(true);
    try {
      setData(await aipAgentControl.refreshReadiness(`a6f-refresh-${crypto.randomUUID()}`));
      setError("");
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setRefreshing(false);
    }
  }
  const stale = useMemo(() => data ? runtimeSnapshotStale(data.evaluatedAt) : false, [data]);
  return <PageChrome title="智能体目录" lede="绑定真相台 · 安装、技能与专业能力就绪（非市场发现壳）">
    <AipOperationalProjectionStrip />
    {error && <div role="alert" className="notice bad">运行就绪度读取失败：{error}</div>}
    {!data ? <div role="status" className="card">正在读取组织智能体目录与绑定…</div> : <>
      <section className="card" style={{padding:18,marginBottom:16}}>
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(120px,1fr))",gap:10,marginBottom:14}}>
          <div className="notice" style={{padding:10}}><div style={{fontSize:12,color:"var(--aos-text-secondary)"}}>角色定义</div><strong>{data.catalog.stats.definitionCount}</strong></div>
          <div className="notice" style={{padding:10}}><div style={{fontSize:12,color:"var(--aos-text-secondary)"}}>已安装</div><strong>{data.catalog.stats.installedCount}</strong></div>
          <div className="notice" style={{padding:10}} data-testid="catalog-dispatchable-count"><div style={{fontSize:12,color:"var(--aos-text-secondary)"}}>可派发</div><strong style={{color:data.catalog.stats.runnableCount === data.catalog.stats.definitionCount ? "var(--aos-green-700)" : "var(--aos-amber-700)"}}>{data.catalog.stats.runnableCount}</strong></div>
          <div className="notice" style={{padding:10}}><div style={{fontSize:12,color:"var(--aos-text-secondary)"}}>技能绑定记录</div><strong>{data.bindingStats.activeSkillBindingCount}/{data.bindingStats.skillBindingCount}</strong><small style={{display:"block",color:"var(--aos-text-secondary)"}}>活跃 / 全部</small></div>
          <div className="notice" style={{padding:10}}><div style={{fontSize:12,color:"var(--aos-text-secondary)"}}>能力绑定记录</div><strong>{data.bindingStats.activeCapabilityBindingCount}/{data.bindingStats.capabilityBindingCount}</strong><small style={{display:"block",color:"var(--aos-text-secondary)"}}>活跃 / 全部</small></div>
          <div className="notice" style={{padding:10}}><div style={{fontSize:12,color:"var(--aos-text-secondary)"}}>技能定义</div><strong>{data.catalog.stats.skillDefinitionCount}</strong></div>
          <div className="notice" style={{padding:10}}><div style={{fontSize:12,color:"var(--aos-text-secondary)"}}>专业能力类</div><strong>{data.catalog.stats.capabilityDefinitionCount}</strong></div>
        </div>
        <div style={{display:"flex",gap:10,alignItems:"center",flexWrap:"wrap"}}>
          <button className="btn primary" disabled={busy || refreshing || data.catalog.stats.installedCount === data.catalog.stats.definitionCount} onClick={() => void install()}>{busy ? "安装中…" : data.catalog.stats.installedCount === data.catalog.stats.definitionCount ? "六数字同事已安装（≠可派发）" : "安装电商六数字同事"}</button>
          <button className="btn" disabled={refreshing || busy} onClick={() => void refresh()} title="刷新并重评绑定就绪">{refreshing ? "重评中…" : "刷新"}</button>
          <Link className="btn" to="/aip/agent-marketplace">市场发现（只读）</Link>
        </div>
        <div className="notice" role="note" data-testid="install-not-dispatchable" style={{marginTop:10,fontSize:13}}>
          已安装 ≠ 可派发。可派发须完整通过 published → installed → binding → evaluated → operational → runnable。
        </div>
        <div style={{marginTop:10,fontSize:13,color:stale ? "var(--aos-amber-700)" : "var(--aos-text-secondary)"}}>
          快照 {new Date(data.evaluatedAt).toLocaleString()} · {stale ? "已过期，请点「刷新」重评绑定" : "15 分钟有效期内"}
        </div>
        <nav aria-label="相关页面" style={{marginTop:12,fontSize:13,display:"flex",gap:12,flexWrap:"wrap"}}>
          <Link to="/aip/agent-marketplace">市场发现</Link>
          <Link to="/aip/evals">评测</Link>
          <Link to="/aip/maturity">成熟度</Link>
          <Link to="/aip/capabilities">智能体插件</Link>
          <Link to="/aip/model-runtime">运行就绪</Link>
          <Link to="/aip/logic">逻辑画布</Link>
        </nav>
      </section>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(360px,1fr))",gap:14}}>
        {data.catalog.items.map(item => {
          const instanceId = item.instance?.instanceId;
          const canonicalSkillIds = new Set(item.skills.map((skill) => skill.skillId));
          const bindings = data.skillBindings.filter(binding => binding.instanceId === instanceId && canonicalSkillIds.has(binding.skill.assetId));
          const activeSkillIds = new Set(item.skills.filter((skill) => bindings.some((binding) => (
            binding.skill.assetId === skill.skillId
            && binding.skill.revision === skill.revision
            && binding.status === "active"
          ))).map((skill) => skill.skillId));
          const requiredCapabilityIds = [...new Set(item.requiredCapabilityIds)];
          const activeCapabilityIds = new Set(requiredCapabilityIds.filter((capId) => data.capabilityBindings.some((binding) => (
            binding.capability.assetId === capId && binding.status === "active"
          ))));
          const opsReady = requiredCapabilityIds.length > 0
            && requiredCapabilityIds.every((capId) => data.capabilityBindings.some((binding) => (
              binding.capability.assetId === capId
              && binding.status === "active"
              && binding.operationalReadiness === "available"
              && freshAt(binding.readinessExpiresAt)
            )));
          const ladder = deriveAgentReadinessLadder({
            templatePublished: item.template.lifecycle === "published",
            installed: Boolean(item.instance),
            hasActiveSkillBinding: activeSkillIds.size === item.skills.length && item.skills.length > 0,
            skillsPublished: item.skills.length > 0 && item.skills.every((skill) => skill.lifecycle === "published"),
            capabilityOperational: opsReady,
            runtimeReadiness: item.runtimeReadiness,
          });
          const blockedTitle = precheckDisabledTitle(item.blockers);
          const precheckOpen = precheckedTemplateId === item.template.templateId;
          const matchedSkillBindings = item.skills.flatMap((skill) => bindings.filter((binding) => (
            binding.skill.assetId === skill.skillId && binding.skill.revision === skill.revision
          )));
          const readinessExpiries = [
            ...matchedSkillBindings.map((binding) => binding.readinessExpiresAt),
            ...requiredCapabilityIds.flatMap((capId) => data.capabilityBindings
              .filter((binding) => binding.capability.assetId === capId && binding.status === "active")
              .map((binding) => binding.readinessExpiresAt)),
          ].filter((value): value is string => Boolean(value));
          const earliestExpiry = readinessExpiries.length
            ? readinessExpiries.reduce((earliest, value) => Date.parse(value) < Date.parse(earliest) ? value : earliest)
            : null;
          return <article key={item.template.templateId} className="card" style={{padding:18}}>
            <div style={{display:"flex",justifyContent:"space-between",gap:10,alignItems:"start"}}>
              <div>
                <h3 style={{margin:0}}>{item.template.displayName}</h3>
                <small style={{color:"var(--aos-text-secondary)"}}>{responsibilityDisplayName(item.template.manifest.responsibility)}</small>
              </div>
              <strong style={{color:item.instance?.status === "active" ? "var(--aos-green-700)" : "var(--aos-amber-700)"}}>{statusLabel(item.instance?.status)}</strong>
            </div>
            <ReadinessLadderStrip ladder={ladder} />
            <div style={{marginTop:8,fontSize:12,color:"var(--aos-text-secondary)"}} data-testid="agent-readiness-summary">{agentReadinessLadderSummary(ladder)}</div>
            <div style={{display:"grid",gridTemplateColumns:"repeat(2,minmax(0,1fr))",gap:8,fontSize:13,marginTop:10}}>
              <div className="notice">技能 {activeSkillIds.size}/{item.skills.length} 已绑定</div>
              <div className="notice">专业能力 {activeCapabilityIds.size}/{requiredCapabilityIds.length} 已绑定</div>
            </div>
            <details style={{marginTop:12}}><summary>查看 {item.skills.length} 个技能状态</summary>
              <ul>{item.skills.map(skill => {
                const binding = bindings.find(value => value.skill.assetId === skill.skillId && value.skill.revision === skill.revision);
                return <li key={skill.skillId}>
                  <strong>{logicDisplayName(skill.canonicalLogicId)}</strong>
                  {" · "}
                  {skill.lifecycle === "published" ? "已发布" : "未发布"}
                  {" · "}
                  {binding ? `绑定${bindingStatusDisplayName(binding.status)}` : "未绑定"}
                </li>;
              })}</ul>
            </details>
            <div style={{marginTop:10,padding:10,background:ladder.dispatchable ? "var(--aos-green-bg, #ecfdf3)" : "var(--aos-amber-bg)",color:ladder.dispatchable ? "var(--aos-green-700)" : "var(--aos-amber-700)"}}>
              {ladder.dispatchable ? "可派发（runnable）" : (item.blockers.length ? formatBlockers(item.blockers) : "缺少完整能力/技能绑定与依赖快照")}
            </div>
            <button
              className="btn"
              disabled={!ladder.dispatchable}
              aria-expanded={precheckOpen}
              aria-controls={`agent-precheck-${item.template.templateId}`}
              title={ladder.dispatchable ? "查看本次目录就绪摘要；不触发外部调用" : blockedTitle}
              style={{marginTop:12}}
              onClick={() => setPrecheckedTemplateId(precheckOpen ? null : item.template.templateId)}
            >
              {precheckOpen ? "收起预检" : ladder.dispatchable ? "预检（可派发）" : "预检（不可派发）"}
            </button>
            {precheckOpen && <div
              id={`agent-precheck-${item.template.templateId}`}
              role="status"
              data-testid={`agent-precheck-${item.template.roleKey}`}
              className="notice"
              style={{marginTop:10,fontSize:12,lineHeight:1.7}}
            >
              <strong>只读预检通过</strong><br />
              模板 {item.template.templateId}@{item.template.revision}<br />
              实例 {item.instance?.instanceId || "未安装"}<br />
              canonical 技能 {activeSkillIds.size}/{item.skills.length} · 唯一专业能力 {activeCapabilityIds.size}/{requiredCapabilityIds.length}<br />
              权威截止 {new Date(data.evaluatedAt).toLocaleString()} · 最早到期 {earliestExpiry ? new Date(earliestExpiry).toLocaleString() : "未提供"}<br />
              本操作未触发 Provider、AgentRun 或生产 Action。
            </div>}
          </article>;
        })}
      </div>
    </>}
  </PageChrome>;
}
