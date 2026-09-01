import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { aipAgentControl, type AgentRuntimeReadinessResponse } from "../../api/aipAgentControl";
import { PageChrome } from "../../components/PageChrome";
import { AipOperationalProjectionStrip } from "../../components/aip/AipOperationalProjectionStrip";
import { AipReadinessActionCard } from "../../components/aip/AipReadinessActionCard";
import { ColleagueBusinessLoopCard } from "../../components/aip/ColleagueBusinessLoopCard";
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

const roleEntrances: Record<string, Array<{ label: string; href: string }>> = {
  data_advisor: [{ label: "进入经营参谋", href: "/workshop/analyst" }],
  content_officer: [{ label: "进入内容与活动", href: "/workshop/content-campaign" }, { label: "进入多媒体生产", href: "/workshop/media-studio" }],
  shopping_advisor: [{ label: "进入日常任务总控", href: "/workshop/cockpit" }],
  customer_service: [{ label: "进入客户关系", href: "/workshop/customer" }],
  private_domain_manager: [{ label: "进入客户关系", href: "/workshop/customer" }],
  campaign_planner: [{ label: "进入内容与活动", href: "/workshop/content-campaign" }, { label: "进入经营参谋", href: "/workshop/analyst" }],
};

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
  const [confirmingInstanceId, setConfirmingInstanceId] = useState<string | null>(null);
  const [actionInstanceId, setActionInstanceId] = useState<string | null>(null);
  const selectedCapabilityId = useMemo(() => new URLSearchParams(window.location.search).get("capabilityId"), []);
  const activationIntent = useMemo(() => new URLSearchParams(window.location.search).get("intent") === "activate", []);
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
  async function changeLifecycle(instanceId: string, version: number, mode: "activate" | "suspend", capabilityBindingIds: string[]) {
    setActionInstanceId(instanceId);
    try {
      if (mode === "activate") await aipAgentControl.activateAgent(instanceId, version, capabilityBindingIds, `agent-activate-${crypto.randomUUID()}`);
      else await aipAgentControl.suspendAgent(instanceId, version, "目录人工暂停；保留现有配置与审计记录", `agent-suspend-${crypto.randomUUID()}`);
      setConfirmingInstanceId(null);
      await load();
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setActionInstanceId(null);
    }
  }
  const stale = useMemo(() => data ? runtimeSnapshotStale(data.evaluatedAt) : false, [data]);
  const readinessSummary = useMemo(() => {
    if (!data) return null;
    const codes = Array.from(new Set(data.catalog.items.flatMap((item) => item.blockers)));
    const expiries = [...data.skillBindings, ...data.capabilityBindings]
      .map((binding) => binding.readinessExpiresAt)
      .filter((value): value is string => Boolean(value));
    const expiresAt = expiries.length ? expiries.reduce((earliest, value) => Date.parse(value) < Date.parse(earliest) ? value : earliest) : null;
    return { codes, expiresAt };
  }, [data]);
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
          <button className="btn primary" disabled={busy || refreshing || data.catalog.stats.installedCount === data.catalog.stats.definitionCount} title={busy ? "正在安装并回读确认" : refreshing ? "正在刷新并重评绑定" : data.catalog.stats.installedCount === data.catalog.stats.definitionCount ? "六数字同事角色定义已全部安装；请继续补齐绑定、评测和运行证据" : "安装电商六数字同事角色定义"} onClick={() => void install()}>{busy ? "安装中…" : data.catalog.stats.installedCount === data.catalog.stats.definitionCount ? "六数字同事已安装（≠可派发）" : "安装电商六数字同事"}</button>
          <button className="btn" disabled={refreshing || busy} onClick={() => void refresh()} title="刷新并重评绑定就绪">{refreshing ? "重评中…" : "刷新"}</button>
          <Link className="btn" to="/aip/agent-marketplace">市场发现（只读）</Link>
        </div>
        <div className="notice" role="note" data-testid="install-not-dispatchable" style={{marginTop:10,fontSize:13}}>
          已安装 ≠ 可派发。可派发须依次完成角色发布、组织安装、技能与专业能力绑定、正式评测、运行证据核验和派发确认。
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
      {(stale || readinessSummary?.codes.length) ? <AipReadinessActionCard
        status={stale ? "需要重新核验运行准备" : "部分智能体需要补齐运行条件"}
        owner="AIP 智能体运行平台 / 模型供应商"
        ownerHref="/aip/model-runtime"
        impact="只有通过当前运行准备核验的智能体会出现在可选执行入口；目录和历史证据仍可查看。"
        missingConditions={[
          ...(stale ? ["15 分钟有效期内的运行准备快照"] : []),
          ...(readinessSummary?.codes.length ? [formatBlockers(readinessSummary.codes)] : []),
        ]}
        reasons={[
          ...(stale ? ["目录运行快照已超过 15 分钟，需要重新核验当前依赖"] : []),
          ...(readinessSummary?.codes.length ? [formatBlockers(readinessSummary.codes)] : []),
        ]}
        observedAt={data.evaluatedAt}
        expiresAt={readinessSummary?.expiresAt}
        actionLabel={refreshing ? "正在刷新…" : "刷新运行准备"}
        onAction={() => void refresh()}
        actionDisabled={refreshing || busy}
        actionDisabledReason={refreshing || busy ? "正在核验目录、绑定与模型运行状态，请等待当前请求完成。" : undefined}
        technicalCodes={readinessSummary?.codes}
      /> : null}
      {selectedCapabilityId ? <div className="notice" role="status" style={{marginBottom:14}}>
        当前从专业能力“{selectedCapabilityId}”进入；下方已标出使用该能力的数字同事。{activationIntent ? "只有依赖快照、健康状态与版本校验同时通过时，才会开放激活确认。" : ""}
      </div> : null}
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
          const exactCapabilityBindings = requiredCapabilityIds.map((capId) => data.capabilityBindings.find((binding) => (
            binding.capability.assetId === capId
            && binding.status === "active"
            && binding.health === "healthy"
            && binding.operationalReadiness === "available"
            && Boolean(binding.dependencySnapshotHash)
            && freshAt(binding.readinessExpiresAt)
          )));
          const activationReady = Boolean(item.instance?.status === "provisioning" && exactCapabilityBindings.length > 0 && exactCapabilityBindings.every(Boolean));
          const selectedForCapability = Boolean(selectedCapabilityId && requiredCapabilityIds.includes(selectedCapabilityId));
          const entrances = roleEntrances[item.template.roleKey] || [{ label: "进入日常任务总控", href: "/workshop/cockpit" }];
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
          return <article key={item.template.templateId} className="card" data-capability-match={selectedForCapability ? "1" : "0"} style={{padding:18,border:selectedForCapability ? "2px solid var(--aos-blue-600, #2563eb)" : undefined}}>
            <div style={{display:"flex",justifyContent:"space-between",gap:10,alignItems:"start"}}>
              <div>
                <h3 style={{margin:0}}>{item.template.displayName}</h3>
                <small style={{color:"var(--aos-text-secondary)"}}>{responsibilityDisplayName(item.template.manifest.responsibility)} · 模板 v{item.template.revision}</small>
              </div>
              <strong style={{color:item.instance?.status === "active" ? "var(--aos-green-700)" : "var(--aos-amber-700)"}}>{statusLabel(item.instance?.status)}</strong>
            </div>
            <ReadinessLadderStrip ladder={ladder} />
            <div style={{marginTop:8,fontSize:12,color:"var(--aos-text-secondary)"}} data-testid="agent-readiness-summary">{agentReadinessLadderSummary(ladder)}</div>
            <div style={{display:"grid",gridTemplateColumns:"repeat(2,minmax(0,1fr))",gap:8,fontSize:13,marginTop:10}}>
              <div className="notice">技能 {activeSkillIds.size}/{item.skills.length} 已绑定</div>
              <div className="notice">专业能力 {activeCapabilityIds.size}/{requiredCapabilityIds.length} 已绑定</div>
            </div>
            <div style={{display:"flex",gap:8,flexWrap:"wrap",marginTop:10,fontSize:13}}>
              {requiredCapabilityIds.map(capabilityId => <Link key={capabilityId} to={`/aip/capabilities?capabilityId=${encodeURIComponent(capabilityId)}`}>{capabilityId}</Link>)}
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
              {ladder.dispatchable ? "运行条件已通过" : "仍需补齐运行条件；请按页面上方“刷新运行准备”完成重评。"}
            </div>
            <ColleagueBusinessLoopCard roleKey={item.template.roleKey} logicIds={item.template.manifest.logicIds} runtimeReadiness={item.runtimeReadiness} />
            {ladder.dispatchable ? <button
              className="btn"
              aria-expanded={precheckOpen}
              aria-controls={`agent-precheck-${item.template.templateId}`}
              title={ladder.dispatchable ? "查看本次目录就绪摘要；不触发外部调用" : blockedTitle}
              style={{marginTop:12}}
              onClick={() => setPrecheckedTemplateId(precheckOpen ? null : item.template.templateId)}
            >
              {precheckOpen ? "收起预检" : "查看运行预检"}
            </button> : <Link className="btn" to="/aip/model-runtime" style={{marginTop:12}}>补齐运行条件</Link>}
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
              权威技能 {activeSkillIds.size}/{item.skills.length} · 唯一专业能力 {activeCapabilityIds.size}/{requiredCapabilityIds.length}<br />
              权威截止 {new Date(data.evaluatedAt).toLocaleString()} · 最早到期 {earliestExpiry ? new Date(earliestExpiry).toLocaleString() : "未提供"}<br />
              本操作未触发 Provider、AgentRun 或生产 Action。
            </div>}
            <div style={{display:"flex",gap:8,flexWrap:"wrap",marginTop:12}}>
              {entrances.map(entrance => <Link key={entrance.href} className="btn" to={entrance.href}>{entrance.label}</Link>)}
              <Link className="btn" to={`/aip/agents?instanceId=${encodeURIComponent(instanceId || item.template.templateId)}`}>查看绑定与最近运行</Link>
            </div>
            {item.instance ? <div style={{marginTop:10,paddingTop:10,borderTop:"1px solid var(--aos-border)"}}>
              {confirmingInstanceId !== item.instance.instanceId ? <button
                className="btn"
                disabled={actionInstanceId !== null || (item.instance.status === "provisioning" ? !activationReady : item.instance.status !== "active")}
                title={item.instance.status === "provisioning" && !activationReady ? "需先补齐全部专业能力的健康、运行就绪与新鲜依赖快照" : item.instance.status === "active" ? "暂停后保留配置、版本与审计记录" : "当前状态不支持此操作"}
                onClick={() => setConfirmingInstanceId(item.instance?.instanceId || null)}
              >{item.instance.status === "active" ? "暂停使用" : "激活此数字同事"}</button> : <div className="notice" role="group" aria-label={`${item.template.displayName}生命周期确认`}>
                <strong>{item.instance.status === "active" ? "确认暂停该数字同事？" : "确认按当前精确绑定激活？"}</strong>
                <p style={{margin:"6px 0"}}>实例 {item.instance.instanceId} · 当前版本 {item.instance.version}；操作成功后将立即回读权威状态。</p>
                <div style={{display:"flex",gap:8}}>
                  <button className="btn primary" disabled={actionInstanceId !== null} onClick={() => void changeLifecycle(item.instance!.instanceId, item.instance!.version, item.instance!.status === "active" ? "suspend" : "activate", exactCapabilityBindings.filter((binding): binding is NonNullable<typeof binding> => Boolean(binding)).map(binding => binding.bindingId))}>{actionInstanceId === item.instance.instanceId ? "提交中…" : "确认提交"}</button>
                  <button className="btn" disabled={actionInstanceId !== null} onClick={() => setConfirmingInstanceId(null)}>取消</button>
                </div>
              </div>}
            </div> : null}
          </article>;
        })}
      </div>
    </>}
  </PageChrome>;
}
