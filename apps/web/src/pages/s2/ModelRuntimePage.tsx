import { useCallback, useEffect, useMemo, useState } from "react";
import { aipModelRuntime, type ModelRuntimeOverview, type RuntimeAssetSummary } from "../../api/aipModelRuntime";
import { PageChrome } from "../../components/PageChrome";
import { AipOperationalProjectionStrip } from "../../components/aip/AipOperationalProjectionStrip";
import { formatBlockers } from "../../lib/aipChineseLabels";

const grid = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 14 } as const;
const names: Record<string, string> = {
  providers: "供应商",
  models: "注册模型",
  routes: "路由",
  policies: "运行策略",
  priceSnapshots: "价格快照",
  evalGates: "评测门",
  capacityPools: "容量池",
  healthObservations: "Health",
};
const lifecycle: Record<string, string> = { draft: "草稿", validated: "已校验", active: "生效", suspended: "暂停", revoked: "撤销" };

function AssetList({ items, empty }: { items: RuntimeAssetSummary[]; empty: string }) {
  if (!items.length) return <div className="notice">{empty}</div>;
  return <div>{items.map(item => <article key={`${item.ref.assetId}@${item.ref.revision}`} style={{ padding: "10px 0", borderTop: "1px solid var(--aos-border)" }}><strong>{item.ref.assetId}</strong><div><code>r{item.ref.revision} · {item.ref.contentHash.slice(0, 12)}…</code></div><small>{lifecycle[item.lifecycle] ?? item.lifecycle} · {item.dependencyRefs.length} 个 exact 依赖</small></article>)}</div>;
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => { setLoading(true); try { setData(await aipModelRuntime.overview()); setError(""); } catch (e) { setData(null); setError(String((e as Error).message || e)); } finally { setLoading(false); } }, []);
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

  return <PageChrome title="模型运行就绪" lede="Exact 供应商、模型、路由、策略、评测、价格与容量权威快照；控制面就绪不等于外部供应商已可调用">
    <AipOperationalProjectionStrip />
    {error ? <div role="alert" className="notice bad">模型运行权威读取失败：{error}</div> : null}
    {loading ? <div role="status" className="card">正在读取当前组织的 exact 模型运行权威…</div> : null}
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
          { label: "未就绪", value: String(blockedResolutions.length) },
          { label: "容量池", value: String(data.capacityPools.length) },
          { label: "Health", value: String(data.healthObservations.length) },
          { label: "评测门", value: String(data.evalGates.length) },
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
      {state === "empty" ? <div className="notice">当前组织没有 AIP-7 exact 供应商 / 模型 / 路由 / 策略。页面不会从旧 KV、静态模型目录或其他租户自动回填；请通过受控配置流程建立权威 revision。</div> : null}
      {state === "partial" || state === "blocked" ? (
        <div className="notice" role="status" style={{ marginBottom: 16 }}>
          {state === "partial"
            ? "部分路由已就绪；未就绪项恢复供应商健康检查后刷新本页即升为「控制面：就绪」，不伪造全绿。"
            : "尚无就绪路由；请检查供应商健康 / 评测 / 价格与容量权威后刷新。"}
          {blockedResolutions.length ? (
            <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
              {blockedResolutions.map((item) => (
                <li key={item.route.assetId}>
                  <strong>{item.route.assetId}</strong>
                  {item.blockerCodes.length ? ` · ${formatBlockers(item.blockerCodes)}` : " · 就绪度未达标"}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <section style={grid} aria-label="模型运行权威分层">
        {(["providers", "models", "routes", "policies", "priceSnapshots"] as const).map(key => <div className="card" style={{ padding: 16 }} key={key}><h2 style={{ marginTop: 0 }}>{names[key]} · {data[key].length}</h2><AssetList items={data[key]} empty={`当前组织尚无 ${names[key]} exact revision。`} /></div>)}
        <div className="card" style={{ padding: 16 }}><h2 style={{ marginTop: 0 }}>评测门 · {data.evalGates.length}</h2>{data.evalGates.length ? data.evalGates.map(item => <p key={item.ref.assetId}><code>{item.ref.assetId}@{item.ref.revision}</code> · {item.status}</p>) : <div className="notice">尚无路由 / 模型引用的评测门。</div>}</div>
        <div className="card" style={{ padding: 16 }}><h2 style={{ marginTop: 0 }}>容量池 · {data.capacityPools.length}</h2>{data.capacityPools.length ? data.capacityPools.map(pool => <article key={pool.poolId}><strong>{pool.poolId}@{pool.revision}</strong><p>{pool.activeReservations}/{pool.maxConcurrency} 并发 · {pool.reservedTokenUnits}/{pool.maxTokenUnits} token 单位</p></article>) : <div className="notice">尚无 exact 容量池；AgentRun 运行门将失败关闭。</div>}</div>
        <div className="card" style={{ padding: 16 }}><h2 style={{ marginTop: 0 }}>Health · {data.healthObservations.length}</h2>{data.healthObservations.length ? data.healthObservations.map(item => <article key={item.observationId}><strong>{item.provider.assetId}@{item.provider.revision}</strong><p>{Date.parse(item.expiresAt) > Date.now() ? "新鲜" : "已过期"} · {item.status} · P50 {item.p50LatencyMs ?? "—"} ms</p></article>) : <div className="notice">尚无 Provider Health observation；相关路由必须失败关闭。</div>}</div>
      </section>
      <section className="card" style={{ padding: 18, marginTop: 16 }}><h2 style={{ marginTop: 0 }}>路由运行就绪</h2>{data.resolutions.length ? data.resolutions.map(item => <article key={item.route.assetId} style={{ padding: "12px 0", borderTop: "1px solid var(--aos-border)" }}><strong>{item.route.assetId}@{item.route.revision} · {item.readiness === "ready" ? "就绪" : "阻断"}</strong>{item.readiness === "ready" ? <p>模型 {item.selectedModel?.assetId} · 供应商 {item.selectedProvider?.assetId} · 价格 {item.selectedPriceSnapshot?.assetId}</p> : <ul>{item.blockerCodes.map(code => <li key={code}>{formatBlockers([code])}</li>)}</ul>}</article>) : <div className="notice">没有 exact 路由，因此没有可解析的运行就绪结果。</div>}</section>
      <div className="notice" style={{ marginTop: 16 }}>本页从不显示 secretRef 或凭据。供应商 operational、真实调用、Usage Receipt 与成本对账仍必须分别取得真实外部证据。</div>
    </> : null}
  </PageChrome>;
}
