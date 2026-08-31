import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  aipModelRuntime,
  type ModelRuntimeOverview,
  type ProviderInstanceRevision,
  type ProviderPluginRevision,
} from "../../api/aipModelRuntime";
import { S2Chrome } from "./shared";

export type ProviderDetailClient = {
  overview(): Promise<ModelRuntimeOverview>;
  provider(providerId: string): Promise<ProviderInstanceRevision>;
  providerPlugin(pluginId: string, revision: number): Promise<ProviderPluginRevision>;
};

const grid = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit,minmax(250px,1fr))",
  gap: 14,
} as const;

function exactLabel(ref: { assetId: string; revision: number; contentHash: string }) {
  return `${ref.assetId}@${ref.revision} · ${ref.contentHash.slice(0, 12)}…`;
}

function providerTitle(providerId: string) {
  if (providerId.startsWith("agnes-text")) return "Agnes 文本";
  if (providerId.startsWith("agnes-image")) return "Agnes 图像";
  if (providerId.startsWith("agnes-video")) return "Agnes 视频";
  return providerId;
}

function resolvesProvider(summary: ModelRuntimeOverview["providers"][number], requestedId: string) {
  return summary.ref.assetId === requestedId
    || summary.dependencyRefs.some((ref) =>
      ref.assetType === "ProviderPluginRevision" && ref.assetId === requestedId
    );
}

export function threeProbeSummary(observation: ModelRuntimeOverview["healthObservations"][number] | null, fresh: boolean) {
  const authorizedWriter = Boolean(observation && [
    "health-agnes-text-qyh-r2-",
    "health-agnes-image-qyh-r2-",
    "health-agnes-video-qyh-r2-",
  ].some((prefix) => observation.observationId.startsWith(prefix)));
  const complete = Boolean(authorizedWriter && fresh && observation?.status === "healthy" && observation.availabilityPct === 100);
  return { complete, label: complete ? "3/3 受控探针聚合通过" : authorizedWriter ? (fresh ? "3/3 聚合结果未满足" : "3/3 聚合证据已过期") : "没有可核验的 3/3 聚合证据" };
}

export function ProviderDetailPage({ client = aipModelRuntime }: { client?: ProviderDetailClient }) {
  const { providerId = "" } = useParams<{ providerId: string }>();
  const [provider, setProvider] = useState<ProviderInstanceRevision | null>(null);
  const [plugin, setPlugin] = useState<ProviderPluginRevision | null>(null);
  const [overview, setOverview] = useState<ModelRuntimeOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [unpublished, setUnpublished] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setUnpublished(false);
    client.overview()
      .then(async (snapshot) => {
        const providerSummary = snapshot.providers.find((item) => resolvesProvider(item, providerId));
        if (!providerSummary) {
          if (cancelled) return;
          setOverview(snapshot);
          setUnpublished(true);
          return;
        }
        const current = await client.provider(providerSummary.ref.assetId);
        if (
          current.providerInstanceId !== providerSummary.ref.assetId
          || current.revision !== providerSummary.ref.revision
          || current.contentHash !== providerSummary.ref.contentHash
        ) throw new Error("overview 与 Provider exact revision 不一致");
        const pluginAuthority = await client.providerPlugin(current.pluginRef.assetId, current.pluginRef.revision);
        if (cancelled) return;
        setProvider(current);
        setPlugin(pluginAuthority);
        setOverview(snapshot);
      })
      .catch((reason) => {
        if (!cancelled) setError(String((reason as Error).message || reason));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [client, providerId]);

  const health = useMemo(() => overview?.healthObservations.find((item) =>
    provider
      && item.provider.assetId === provider.providerInstanceId
      && item.provider.revision === provider.revision
      && item.provider.contentHash === provider.contentHash
  ) ?? null, [overview, provider]);
  const healthFresh = Boolean(health && Date.parse(health.expiresAt) > Date.now());
  const probes = threeProbeSummary(health, healthFresh);
  const models = useMemo(() => overview?.models.filter((item) => item.dependencyRefs.some((ref) =>
    provider
      && ref.assetType === "ProviderInstanceRevision"
      && ref.assetId === provider.providerInstanceId
      && ref.revision === provider.revision
      && ref.contentHash === provider.contentHash
  )) ?? [], [overview, provider]);
  const modelKeys = useMemo(() => new Set(models.map((item) => `${item.ref.assetId}@${item.ref.revision}:${item.ref.contentHash}`)), [models]);
  const pools = useMemo(() => overview?.capacityPools.filter((item) =>
    modelKeys.has(`${item.modelRef.assetId}@${item.modelRef.revision}:${item.modelRef.contentHash}`)
  ) ?? [], [modelKeys, overview]);
  const resolutions = useMemo(() => overview?.resolutions.filter((item) =>
    item.selectedProvider?.assetId === provider?.providerInstanceId
    || pools.some((pool) => pool.routeRef.assetId === item.route.assetId)
  ) ?? [], [overview, pools, provider]);

  return (
    <S2Chrome
      title={`${providerTitle(providerId)}运行权威`}
      lede="只读查看 exact Provider、插件审批、Health、模型与容量关系；本页不读取或回显 Secret payload"
    >
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 16 }}>
        <Link to="/aip/model-providers" className="btn btn-nav">← 返回模型供应商</Link>
        <Link to="/aip/model-runtime" className="btn btn-nav">模型运行就绪 →</Link>
        <Link to="/aip/model-router" className="btn btn-nav">模型路由 →</Link>
        <Link to="/aip/evals" className="btn btn-nav">Evals 门控 →</Link>
        <Link to="/aip/capacity" className="btn btn-nav">容量与用量 →</Link>
        <Link to="/aip/agents" className="btn btn-nav">受影响数字同事 →</Link>
      </div>

      {loading ? <div role="status" className="card">正在读取当前组织的 exact Provider 权威…</div> : null}
      {error ? <div role="alert" className="notice bad">Provider 权威读取失败：{error}</div> : null}
      {!loading && !error && unpublished && overview ? (
        <div role="status" className="notice">
          组织 {overview.tenant.orgId} · 工作区 {overview.tenant.projectId} 尚未发布与 {providerId} 插件绑定的 ProviderInstanceRevision；
          当前仅是插件已安装状态，不具备路由、Health 或 AgentRun 启动资格。
        </div>
      ) : null}
      {!loading && !error && provider && plugin && overview ? (
        <>
          <div className="notice" style={{ marginBottom: 16 }}>
            组织 {overview.tenant.orgId} · 工作区 {overview.tenant.projectId} ·
            Health {healthFresh ? "新鲜" : health ? "已过期" : "未知"} ·
            控制面状态不等于真实外部调用已成功
          </div>

          <section style={grid} aria-label="Provider 权威摘要">
            <article className="card" style={{ padding: 16 }}>
              <h2 style={{ marginTop: 0 }}>Provider exact revision</h2>
              <p><strong>{provider.providerInstanceId}</strong></p>
              <p><code>r{provider.revision} · {provider.contentHash}</code></p>
              <p>生命周期：{provider.lifecycle}</p>
              <p>创建者：{provider.createdBy}</p>
            </article>
            <article className="card" style={{ padding: 16 }}>
              <h2 style={{ marginTop: 0 }}>Endpoint 与凭据绑定</h2>
              <p>{provider.endpointProfile.baseUrl}</p>
              <p>{provider.endpointProfile.region} · timeout {provider.endpointProfile.timeoutMs} ms</p>
              <p><strong>{provider.secretBackend} · version {provider.secretVersion}</strong></p>
              <p className="muted">仅显示 Secret backend 与版本；opaque ref 和 payload 均不下发到页面。</p>
            </article>
            <article className="card" style={{ padding: 16 }}>
              <h2 style={{ marginTop: 0 }}>Health {healthFresh ? "新鲜" : health ? "已过期" : "未知"}</h2>
              {health ? <>
                <p><strong>{health.status}</strong> · 可用率 {health.availabilityPct ?? "—"}%</p>
                <p>P50 {health.p50LatencyMs ?? "—"} ms</p>
                <p>观察 {new Date(health.observedAt).toLocaleString()}</p>
                <p>失效 {new Date(health.expiresAt).toLocaleString()}</p>
                <p><strong>{probes.label}</strong></p>
              </> : <div className="notice">当前 exact Provider 尚无 Health observation，运行门必须失败关闭。</div>}
            </article>
            <article className="card" style={{ padding: 16 }}>
              <h2 style={{ marginTop: 0 }}>插件审批权威</h2>
              <p><strong>{plugin.providerPluginId}@{plugin.revision}</strong> · {plugin.approvalStatus}</p>
              <p>Owner：{plugin.owner} · 批准者：{plugin.approvedBy}</p>
              <p>允许：{plugin.approvedCapabilities.join("、")}</p>
              <p>禁止：{plugin.deniedCapabilities.join("、") || "—"}</p>
            </article>
          </section>

          <section className="card" style={{ padding: 18, marginTop: 16 }} aria-label="3/3 探针诊断">
            <h2 style={{ marginTop: 0 }}>3/3 Health 探针诊断</h2>
            <p>模型与模态：{plugin.defaultModels.join("、")} · {plugin.modalities.join("、")}；仅认可同一 exact Provider 和当前截止面。</p>
            <div className={`notice ${probes.complete ? "good" : "bad"}`}>
              <strong>{probes.label}</strong><br />
              {probes.complete ? "受控 R2 writer 只在三次单次尝试全部成功后写入本条聚合 observation。" : "当前 observation 不能证明三次受控探针全部成功。"}
            </div>
            <p className="muted">当前权威只保存聚合结果，不保存三条逐探针明细；页面不虚构单条延迟或响应，也不展示提示词、响应正文、Header 或 Secret。</p>
          </section>

          <section className="card" style={{ padding: 18, marginTop: 16 }}>
            <h2 style={{ marginTop: 0 }}>关联 exact 模型 · {models.length}</h2>
            {models.length ? models.map((item) => <p key={item.ref.assetId}><strong>{exactLabel(item.ref)}</strong> · {item.lifecycle}</p>) : <div className="notice">当前 Provider 尚无 exact 注册模型。</div>}
          </section>
          <section style={{ ...grid, marginTop: 16 }}>
            <article className="card" style={{ padding: 18 }}>
              <h2 style={{ marginTop: 0 }}>容量池 · {pools.length}</h2>
              {pools.length ? pools.map((pool) => <p key={pool.poolId}><strong>{pool.poolId}@{pool.revision}</strong> · {pool.activeReservations}/{pool.maxConcurrency} 并发</p>) : <div className="notice">无 exact 容量池，相关 AgentRun 不得启动。</div>}
            </article>
            <article className="card" style={{ padding: 18 }}>
              <h2 style={{ marginTop: 0 }}>路由解析 · {resolutions.length}</h2>
              {resolutions.length ? resolutions.map((item) => <p key={item.route.assetId}><strong>{item.route.assetId}</strong> · {item.readiness} {item.blockerCodes.length ? `· ${item.blockerCodes.join("、")}` : ""}</p>) : <div className="notice">当前 Provider 没有可核验的路由解析结果。</div>}
            </article>
          </section>
        </>
      ) : null}
    </S2Chrome>
  );
}
