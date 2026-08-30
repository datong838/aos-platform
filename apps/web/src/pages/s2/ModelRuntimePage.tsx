import { useCallback, useEffect, useMemo, useState } from "react";
import { aipModelRuntime, type ModelRuntimeCostOverview, type ModelRuntimeOverview, type RuntimeAssetSummary } from "../../api/aipModelRuntime";
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
  if (state === "blocked") return "阻断";
  return "空";
}

export function ModelRuntimePage() {
  const [data, setData] = useState<ModelRuntimeOverview | null>(null);
  const [cost, setCost] = useState<ModelRuntimeCostOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => { setLoading(true); try { const [overview, costOverview] = await Promise.all([aipModelRuntime.overview(), aipModelRuntime.costOverview()]); setData(overview); setCost(costOverview); setError(""); } catch (e) { setData(null); setCost(null); setError(String((e as Error).message || e)); } finally { setLoading(false); } }, []);
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
          { label: "待补齐条件", value: String(blockedResolutions.length) },
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
      {state === "empty" ? <div className="notice">当前组织没有精确的供应商、模型、路由或策略配置。页面不会从旧配置、静态目录或其他租户自动回填；请通过受控配置流程建立权威修订。</div> : null}
      {state === "partial" || state === "blocked" ? <AipReadinessActionCard
        status={state === "partial" ? "部分模型路由可用" : "需要补齐模型运行条件"}
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
      <section className="card" style={{ padding: 18, marginTop: 16 }}><h2 style={{ marginTop: 0 }}>路由运行准备</h2>{data.resolutions.length ? data.resolutions.map(item => <article key={item.route.assetId} style={{ padding: "12px 0", borderTop: "1px solid var(--aos-border)" }}><strong>{item.readiness === "ready" ? "路由运行条件已通过" : "路由运行条件待补齐"}</strong><p>{item.readiness === "ready" ? "已选择有效模型与供应商" : "处理负责人和下一步见页面上方“运行准备行动卡”。"}</p><details><summary>技术标识（审计用）</summary><code>{item.route.assetId}@{item.route.revision}</code>{item.selectedModel ? <> · 模型 <code>{item.selectedModel.assetId}</code></> : null}{item.selectedProvider ? <> · 供应商 <code>{item.selectedProvider.assetId}</code></> : null}{item.selectedPriceSnapshot ? <> · 价格快照 <code>{item.selectedPriceSnapshot.assetId}</code></> : null}{item.blockerCodes.length ? <><br /><code>{item.blockerCodes.join(" · ")}</code></> : null}</details></article>) : <div className="notice">当前没有精确路由；请先在模型路由页建立并保存权威修订。</div>}</section>
      {cost ? <section className="card" style={{ padding: 18, marginTop: 16 }} aria-label="成本与预算权威">
        <h2 style={{ marginTop: 0 }}>成本与预算权威</h2>
        <p>用量：{cost.usage.state === "unobserved" ? "尚未观测，不能按 0 成本解释" : `${cost.usage.receiptCount} 条用量凭证（实测 ${cost.usage.measuredCount} / 估算 ${cost.usage.estimatedCount} / 未知 ${cost.usage.unknownCount}）`} · 调整单 {cost.usage.adjustmentCount}</p>
        {Object.keys(cost.usage.costTotals).length ? <p>成本合计：{Object.entries(cost.usage.costTotals).map(([currency, amount]) => `${currency} ${amount}`).join(" · ")}</p> : <p>成本合计：尚无实际模型调用记录（不代表免费或零成本）</p>}
        <div style={grid}>{cost.modelPrices.map(item => <article className="notice" key={item.modelRef.assetId}><strong>{item.providerModelId}</strong><div>{item.status === "priced" ? "已定价" : item.status === "approved_zero" ? "审批零价" : item.status === "unit_mismatch" ? "计价单位不匹配" : "价格条件待补齐"}</div>{item.blockerCodes.length ? <small>{formatBlockers(item.blockerCodes)}</small> : null}</article>)}</div>
      </section> : null}
      <div className="notice" style={{ marginTop: 16 }}>本页从不显示密钥引用或凭据正文。供应商是否可运行、真实调用和成本对账，仍必须以精确健康检查、用量凭证与追加调整记录为准。</div>
    </> : null}
  </PageChrome>;
}
