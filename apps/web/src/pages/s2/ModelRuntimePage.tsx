import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { aipModelRuntime, type ModelRuntimeChainOverview, type ModelRuntimeCostOverview, type ModelRuntimeOverview, type RuntimeAssetSummary, type RuntimeChainNode, type RuntimeTraceRef } from "../../api/aipModelRuntime";
import { PageChrome } from "../../components/PageChrome";
import { AipOperationalProjectionStrip } from "../../components/aip/AipOperationalProjectionStrip";
import { AipReadinessActionCard } from "../../components/aip/AipReadinessActionCard";
import { formatBlockers, statusDisplayName } from "../../lib/aipChineseLabels";

const grid = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 14 } as const;
const names: Record<string, string> = {
  providers: "供应商",
  models: "注册模型",
  routes: "路由",
  policies: "运行策略",
  priceSnapshots: "价格快照",
  evalGates: "评测门",
  capacityPools: "容量池",
  healthObservations: "供应商健康状态",
};
const lifecycle: Record<string, string> = { draft: "草稿", validated: "已校验", active: "生效", suspended: "暂停", revoked: "撤销" };
const chainStageLabels: Record<RuntimeChainNode["stage"], string> = {
  provider: "供应商",
  secret_ref: "凭据引用",
  policy: "运行策略",
  eval: "评测门",
  health: "健康状态",
  capacity: "容量池",
};
const traceLabels: Record<RuntimeTraceRef["resourceType"], string> = { task: "任务", agent: "数字同事", logic: "业务逻辑", model: "模型" };

function AssetList({ items, empty, label }: { items: RuntimeAssetSummary[]; empty: string; label: string }) {
  if (!items.length) return <div className="notice">{empty}</div>;
  return <div>{items.map((item, index) => <article key={`${item.ref.assetId}@${item.ref.revision}`} style={{ padding: "10px 0", borderTop: "1px solid var(--aos-border)" }}><strong>{label}配置 {index + 1}</strong><small>{lifecycle[item.lifecycle] ?? item.lifecycle} · {item.dependencyRefs.length} 个精确依赖</small><details><summary>技术标识（审计用）</summary><code>{item.ref.assetId}@{item.ref.revision}</code> · 摘要 <code>{item.ref.contentHash.slice(0, 12)}…</code></details></article>)}</div>;
}

export function modelRuntimeControlStatus(data: ModelRuntimeOverview): "empty" | "blocked" | "partial" | "ready" {
  if (!data.providers.length && !data.models.length && !data.routes.length && !data.policies.length) return "empty";
  if (!data.resolutions.length) return "blocked";
  const readyCount = data.resolutions.filter((item) => item.readiness === "ready").length;
  if (readyCount === data.resolutions.length) return "ready";
  if (readyCount > 0) return "partial";
  return "blocked";
}

export function modelRuntimeControlLabel(state: "empty" | "blocked" | "partial" | "ready"): string {
  if (state === "ready") return "就绪";
  if (state === "partial") return "部分就绪";
  if (state === "blocked") return "需复核";
  return "暂无配置";
}

export function controlledTrialLabel(allowed: boolean): string {
  return allowed ? "进入受控试聊" : "当前链路不可试聊";
}

export function ModelRuntimePage() {
  const [data, setData] = useState<ModelRuntimeOverview | null>(null);
  const [chain, setChain] = useState<ModelRuntimeChainOverview | null>(null);
  const [cost, setCost] = useState<ModelRuntimeCostOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => { setLoading(true); try { const [overview, chainOverview, costOverview] = await Promise.all([aipModelRuntime.overview(), aipModelRuntime.chainOverview(), aipModelRuntime.costOverview()]); setData(overview); setChain(chainOverview); setCost(costOverview); setError(""); } catch (e) { setData(null); setChain(null); setCost(null); setError(String((e as Error).message || e)); } finally { setLoading(false); } }, []);
  useEffect(() => { void load(); }, [load]);
  const state = useMemo(() => data ? modelRuntimeControlStatus(data) : "empty", [data]);
  const blockedResolutions = useMemo(
    () => (data?.resolutions || []).filter((item) => item.readiness !== "ready"),
    [data],
  );
  const readyResolutionCount = useMemo(
    () => (data?.resolutions || []).filter((item) => item.readiness === "ready").length,
    [data],
  );
  const blockerCodes = useMemo(() => Array.from(new Set(blockedResolutions.flatMap((item) => item.blockerCodes))), [blockedResolutions]);
  const earliestHealthExpiry = useMemo(() => {
    const expiries = (data?.healthObservations || []).map((item) => item.expiresAt).filter(Boolean);
    return expiries.length ? expiries.reduce((earliest, value) => Date.parse(value) < Date.parse(earliest) ? value : earliest) : null;
  }, [data]);

  return <PageChrome title="模型运行就绪" lede="汇总供应商、模型、路由、策略、评测、价格与容量的精确权威快照；控制面就绪不等于外部供应商已可调用">
    <AipOperationalProjectionStrip />
    {error ? <div role="alert" className="notice bad">模型运行权威读取失败：{error}</div> : null}
    {loading ? <div role="status" className="card">正在读取当前组织的精确模型运行权威…</div> : null}
    {!loading && data ? <>
      <div
        data-testid="model-runtime-ops-stats"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 14 }}
      >
        {[
          { label: "控制面", value: modelRuntimeControlLabel(state) },
          { label: "供应商", value: String(data.providers.length) },
          { label: "模型", value: String(data.models.length) },
          { label: "路由", value: String(data.routes.length) },
          { label: "路由就绪", value: data.resolutions.length ? `${readyResolutionCount}/${data.resolutions.length}` : "0/0" },
          { label: "需复核路由", value: String(blockedResolutions.length) },
          { label: "容量池", value: String(data.capacityPools.length) },
          { label: "健康记录", value: String(data.healthObservations.length) },
          { label: "评测门", value: String(data.evalGates.length) },
          { label: "已定价", value: cost ? `${cost.modelPrices.filter((item) => item.status === "priced" || item.status === "approved_zero").length}/${cost.modelPrices.length}` : "—" },
          { label: "预算生效", value: cost ? `${cost.budgets.filter((item) => item.status === "active").length}/${cost.budgets.length}` : "—" },
          { label: "用量证据", value: cost?.usage.state === "unobserved" ? "未观测" : cost?.usage.state === "measured" ? "实测" : cost?.usage.state === "partial" ? "部分" : "未知" },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 20, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{s.value}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 16 }}>
        <strong>控制面：{modelRuntimeControlLabel(state)}</strong>
        <span>组织 {data.tenant.orgId} · 工作区 {data.tenant.projectId}</span>
        {data.resolutions.length ? <span>路由就绪 {readyResolutionCount}/{data.resolutions.length}</span> : null}
        <button className="btn" onClick={() => void load()}>刷新权威快照</button>
      </div>
      {chain ? <section className="card" style={{ padding: 18, marginBottom: 16 }} aria-label="模型运行六节点链路">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
          <div><h2 style={{ margin: 0 }}>运行链与受控试聊门</h2><p style={{ marginBottom: 0 }}>同一截止面核验供应商、凭据引用、策略、评测、健康与容量；任一节点不通过都不会发起模型调用。</p></div>
          <small>截止 {new Date(chain.generatedAt).toLocaleString("zh-CN")}</small>
        </div>
        {chain.chains.length ? chain.chains.map((item) => <article key={`${item.route.assetId}@${item.route.revision}:${item.candidateModel?.assetId ?? "none"}@${item.candidateModel?.revision ?? 0}`} style={{ marginTop: 18, paddingTop: 18, borderTop: "1px solid var(--aos-border)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            <div><strong>{item.taskTypes.join("、") || "当前路由承接的经营任务"}</strong><small>候选模型 {item.candidateModel?.assetId ?? "尚无精确候选"} · 路由修订 {item.route.revision}</small></div>
            {item.controlledTrialAllowed ? <Link className="btn primary" to="/aip/model-router">{controlledTrialLabel(true)}</Link> : <button className="btn" type="button" disabled title="六节点需在同一截止面全部通过">{controlledTrialLabel(false)}</button>}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6,minmax(150px,1fr))", gap: 8, overflowX: "auto", padding: "12px 0 2px" }}>
            {item.nodes.map((node, index) => <div key={node.stage} className={`notice ${node.status === "ready" ? "good" : "warn"}`} style={{ minWidth: 150, padding: 12 }}>
              <small>{index + 1}. {chainStageLabels[node.stage]}</small>
              <strong style={{ display: "block", margin: "5px 0" }}>{node.status === "ready" ? "已验证" : "需复核"}</strong>
              <div>{node.title}</div>
              <small>截止 {node.observedAt ? new Date(node.observedAt).toLocaleString("zh-CN") : "无有效观测"}</small>
              <details><summary>影响与复核方法</summary><p>{node.impact}</p><p>{node.recheckAction}</p>{node.blockerCode ? <code>{node.blockerCode}</code> : null}<br /><Link to={node.ownerEntry}>打开责任入口 →</Link></details>
            </div>)}
          </div>
        </article>) : <div className="notice" style={{ marginTop: 14 }}>当前租户没有可核验的模型路由，因此不会显示虚构运行链，也不会开放受控试聊。</div>}
      </section> : null}
      {chain ? <section className="card" style={{ padding: 18, marginBottom: 16 }} aria-label="任务模型双向追溯">
        <h2 style={{ marginTop: 0 }}>任务与模型双向追溯</h2>
        <p>只关联共享同一条用量凭证的任务、模型、数字同事与业务逻辑；缺少显式归因时原样显示缺口。</p>
        <div style={grid}>
          <div><h3>任务 → 模型</h3>{chain.taskTraces.length ? chain.taskTraces.map((item, index) => <article className="notice" key={`${item.task.resourceId}@${item.task.revision}`}><strong>业务任务 {index + 1}</strong><small>{item.receiptCount} 条用量凭证</small>{(["models", "agents", "logics"] as const).map((key) => <div key={key}>{item[key].map((ref) => `${traceLabels[ref.resourceType]}：${ref.resourceId}`).join(" · ") || `${key === "models" ? "模型" : key === "agents" ? "数字同事" : "业务逻辑"}：无显式归因`}</div>)}{item.missingDimensions.length ? <small>缺失维度：{item.missingDimensions.map((value) => value === "model" ? "模型" : value === "agent" ? "数字同事" : "业务逻辑").join("、")}</small> : null}<details><summary>任务技术标识（审计用）</summary><code>{item.task.resourceId}@{item.task.revision}</code></details></article>) : <div className="notice">当前没有带任务绑定的用量凭证，不能推断任务使用了哪个模型。</div>}</div>
          <div><h3>模型 → 影响对象</h3>{chain.modelImpacts.length ? chain.modelImpacts.map((item) => <article className="notice" key={`${item.model.resourceId}@${item.model.revision}`}><strong>{item.model.resourceId}</strong><small>{item.receiptCount} 条显式模型归因凭证</small>{(["tasks", "agents", "logics"] as const).map((key) => <div key={key}>{item[key].map((ref) => `${traceLabels[ref.resourceType]}：${ref.resourceId}`).join(" · ") || "无同凭证关联对象"}</div>)}</article>) : <div className="notice">当前没有显式模型归因凭证，不能反推影响任务或数字同事。</div>}</div>
        </div>
      </section> : null}
      {state === "empty" ? <div className="notice">当前组织没有精确的供应商、模型、路由或策略配置。页面不会从旧配置、静态目录或其他租户自动回填；请通过受控配置流程建立权威修订。</div> : null}
      {state === "partial" || state === "blocked" ? <AipReadinessActionCard
        status={state === "partial" ? "部分模型路由可用" : "模型运行条件需复核"}
        owner="模型供应商运行负责人 / AIP 模型平台"
        ownerHref="/aip/model-providers"
        impact={state === "partial" ? "只有已完成核验的路由可以承接新任务；其他路由不会被系统选用。" : "新的智能体运行不会进入模型调用，已有运行证据仍可只读审计。"}
        missingConditions={blockerCodes.length ? [formatBlockers(blockerCodes)] : ["有效的路由、模型供应商健康状态与评测门"]}
        reasons={blockerCodes.length ? [formatBlockers(blockerCodes)] : ["路由运行准备未达到要求"]}
        observedAt={data.generatedAt}
        expiresAt={earliestHealthExpiry}
        actionLabel="刷新模型运行状态"
        onAction={() => void load()}
        actionDisabled={loading}
        actionDisabledReason={loading ? "正在读取最新模型运行状态，本次请求返回后可再次核验。" : undefined}
        technicalCodes={blockerCodes}
      /> : null}
      <section style={grid} aria-label="模型运行权威分层">
        {(["providers", "models", "routes", "policies", "priceSnapshots"] as const).map(key => <div className="card" style={{ padding: 16 }} key={key}><h2 style={{ marginTop: 0 }}>{names[key]} · {data[key].length}</h2><AssetList items={data[key]} label={names[key]} empty={`当前组织尚无 ${names[key]}精确修订。`} /></div>)}
        <div className="card" style={{ padding: 16 }}><h2 style={{ marginTop: 0 }}>评测门 · {data.evalGates.length}</h2>{data.evalGates.length ? data.evalGates.map((item, index) => <article key={item.ref.assetId}><strong>评测门 {index + 1} · {statusDisplayName(item.status)}</strong><details><summary>技术标识（审计用）</summary><code>{item.ref.assetId}@{item.ref.revision}</code></details></article>) : <div className="notice">尚无路由 / 模型引用的评测门。</div>}</div>
        <div className="card" style={{ padding: 16 }}><h2 style={{ marginTop: 0 }}>容量池 · {data.capacityPools.length}</h2>{data.capacityPools.length ? data.capacityPools.map(pool => <article key={pool.poolId}><strong>并发容量 {pool.activeReservations}/{pool.maxConcurrency}</strong><p>已预留用量 {pool.reservedTokenUnits}/{pool.maxTokenUnits}</p><details><summary>技术标识（审计用）</summary><code>{pool.poolId}@{pool.revision}</code></details></article>) : <div className="notice">尚无精确容量池；智能体运行门将保持关闭。</div>}</div>
        <div className="card" style={{ padding: 16 }}><h2 style={{ marginTop: 0 }}>供应商健康状态 · {data.healthObservations.length}</h2>{data.healthObservations.length ? data.healthObservations.map(item => <article key={item.observationId}><strong>健康检查：{Date.parse(item.expiresAt) > Date.now() ? "有效" : "已过期"}</strong><p>{statusDisplayName(item.status)} · 中位响应时间 {item.p50LatencyMs ?? "—"} 毫秒</p><details><summary>供应商技术标识（审计用）</summary><code>{item.provider.assetId}@{item.provider.revision}</code></details></article>) : <div className="notice">尚无供应商健康检查记录；相关路由必须保持关闭。</div>}</div>
      </section>
      <section className="card" style={{ padding: 18, marginTop: 16 }}><h2 style={{ marginTop: 0 }}>路由运行准备</h2>{data.resolutions.length ? data.resolutions.map(item => <article key={item.route.assetId} style={{ padding: "12px 0", borderTop: "1px solid var(--aos-border)" }}><strong>{item.readiness === "ready" ? "路由运行条件已通过" : "路由运行条件需复核"}</strong><p>{item.readiness === "ready" ? "已选择有效模型与供应商" : "处理负责人和下一步见页面上方“运行准备行动卡”。"}</p><details><summary>技术标识（审计用）</summary><code>{item.route.assetId}@{item.route.revision}</code>{item.selectedModel ? <> · 模型 <code>{item.selectedModel.assetId}</code></> : null}{item.selectedProvider ? <> · 供应商 <code>{item.selectedProvider.assetId}</code></> : null}{item.selectedPriceSnapshot ? <> · 价格快照 <code>{item.selectedPriceSnapshot.assetId}</code></> : null}{item.blockerCodes.length ? <><br /><code>{item.blockerCodes.join(" · ")}</code></> : null}</details></article>) : <div className="notice">当前没有精确路由；请先在模型路由页建立并保存权威修订。</div>}</section>
      {cost ? <section className="card" style={{ padding: 18, marginTop: 16 }} aria-label="成本与预算权威">
        <h2 style={{ marginTop: 0 }}>成本与预算权威</h2>
        <p>用量：{cost.usage.state === "unobserved" ? "尚未观测，不能按 0 成本解释" : `${cost.usage.receiptCount} 条用量凭证（实测 ${cost.usage.measuredCount} / 估算 ${cost.usage.estimatedCount} / 未知 ${cost.usage.unknownCount}）`} · 调整单 {cost.usage.adjustmentCount}</p>
        {Object.keys(cost.usage.costTotals).length ? <p>成本合计：{Object.entries(cost.usage.costTotals).map(([currency, amount]) => `${currency} ${amount}`).join(" · ")}</p> : <p>成本合计：尚无实际模型调用记录（不代表免费或零成本）</p>}
        <div style={grid}>{cost.modelPrices.map(item => <article className="notice" key={item.modelRef.assetId}><strong>{item.providerModelId}</strong><div>{item.status === "priced" ? "已定价" : item.status === "approved_zero" ? "审批零价" : item.status === "unit_mismatch" ? "计价单位不匹配" : "价格条件需复核"}</div>{item.blockerCodes.length ? <small>{formatBlockers(item.blockerCodes)}</small> : null}</article>)}</div>
      </section> : null}
      <div className="notice" style={{ marginTop: 16 }}>本页从不显示密钥引用或凭据正文。供应商是否可运行、真实调用和成本对账，仍必须以精确健康检查、用量凭证与追加调整记录为准。</div>
    </> : null}
  </PageChrome>;
}
