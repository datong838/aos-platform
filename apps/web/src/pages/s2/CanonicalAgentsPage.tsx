import { Link, useSearchParams } from "react-router-dom";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  aipAgentControl,
  type AgentInstanceListResponse,
  type AgentRuntimeReadinessResponse,
  type AgentRunListResponse,
} from "../../api/aipAgentControl";
import { aipMarketplaceImport, type MarketplaceAgentReadiness } from "../../api/aipMarketplaceImport";
import { PageChrome } from "../../components/PageChrome";
import { capabilityDisplayName, formatBlockers, instanceStatusDisplayName, responsibilityDisplayName, statusDisplayName } from "../../lib/aipChineseLabels";

type DetailTab = "overview" | "tools" | "try" | "publish";

export function CanonicalAgentsPage() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<AgentInstanceListResponse | null>(null);
  const [runtime, setRuntime] = useState<AgentRuntimeReadinessResponse | null>(null);
  const [repairs, setRepairs] = useState<Map<string, MarketplaceAgentReadiness>>(new Map());
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<DetailTab>("overview");
  const [recentRuns, setRecentRuns] = useState<AgentRunListResponse | null>(null);
  const [runError, setRunError] = useState("");

  const load = useCallback(async () => {
    try {
      const [instances, readiness, marketplace] = await Promise.all([
        aipAgentControl.listInstances(),
        aipAgentControl.runtimeReadiness(),
        aipMarketplaceImport.listMarketplace().catch(() => null),
      ]);
      setData(instances);
      setRuntime(readiness);
      setRepairs(new Map((marketplace?.items || []).flatMap((item) => item.agents).map((item) => [item.templateId, item])));
      setError("");
      setSelectedId((prev) => {
        const requested = searchParams.get("instanceId");
        if (requested && instances.items.some((item) => item.instanceId === requested)) return requested;
        if (prev && instances.items.some((item) => item.instanceId === prev)) return prev;
        return instances.items[0]?.instanceId ?? null;
      });
    } catch (e) {
      setData(null);
      setRuntime(null);
      setRepairs(new Map());
      setError(String((e as Error).message || e));
    }
  }, [searchParams]);

  useEffect(() => {
    void load();
  }, [load]);

  const catalogByTemplate = useMemo(() => {
    const map = new Map<string, (NonNullable<AgentRuntimeReadinessResponse>["catalog"]["items"])[number]>();
    for (const item of runtime?.catalog.items || []) {
      map.set(item.template.templateId, item);
    }
    return map;
  }, [runtime]);

  const filtered = useMemo(() => {
    const items = data?.items || [];
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) => {
      const name = (item.overlay.displayName || item.instanceId).toLowerCase();
      return name.includes(q) || item.template.assetId.toLowerCase().includes(q);
    });
  }, [data, query]);

  const selected = filtered.find((item) => item.instanceId === selectedId) || filtered[0] || null;
  const catalogItem = selected ? catalogByTemplate.get(selected.template.assetId) : undefined;
  const repair = selected ? repairs.get(selected.template.assetId) : undefined;
  const runnable = catalogItem?.runtimeReadiness === "runnable";

  useEffect(() => {
    if (!selected?.instanceId) { setRecentRuns(null); setRunError(""); return; }
    let active = true;
    setRecentRuns(null);
    aipAgentControl.listAgentRuns(selected.instanceId, 5).then((value) => {
      if (active) { setRecentRuns(value); setRunError(""); }
    }).catch((value) => {
      if (active) { setRecentRuns(null); setRunError(String((value as Error).message || value)); }
    });
    return () => { active = false; };
  }, [selected?.instanceId]);

  return (
    <PageChrome title="智能体列表" lede="管理已安装数字同事的职责、能力、工具与真实运行记录">
      <div style={{ display: "flex", gap: 12, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
        <button className="btn" type="button" onClick={() => void load()}>刷新</button>
        <Link className="btn" to="/aip/agent-registry">智能体目录</Link>
        <Link className="btn" to="/aip/agent-marketplace">市场发现</Link>
        <Link className="btn" to="/aip/tools">工具面板</Link>
        {runtime ? (
          <>
            <span className="notice" style={{ padding: "6px 10px" }}>实例 {data?.count ?? 0}</span>
            <span className="notice" style={{ padding: "6px 10px" }} data-testid="agents-dispatchable-ratio">
              可承接任务 {runtime.catalog.stats.runnableCount}/{runtime.catalog.stats.installedCount}
            </span>
          </>
        ) : null}
      </div>
      {error && <div role="alert" className="notice bad">实例读取失败：{error}</div>}
      {!data ? (
        <div className="card" role="status">正在读取组织实例…</div>
      ) : data.count === 0 ? (
        <div className="card">
          <h3>尚未安装智能体</h3>
          <p>请先在「智能体目录」安装电商六数字同事。本页不展示市场演示样例。</p>
          <Link to="/aip/agent-registry">前往安装 →</Link>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(260px,320px) minmax(0,1fr)", gap: 14, minHeight: 520 }}>
          <aside className="card" style={{ padding: 0, overflow: "hidden", display: "flex", flexDirection: "column" }} aria-label="智能体列表">
            <div style={{ padding: 12, borderBottom: "1px solid var(--aos-border, #e5e7eb)" }}>
              <input
                aria-label="筛选智能体"
                className="input"
                style={{ width: "100%", padding: "8px 10px" }}
                placeholder="筛选名称…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <div style={{ overflow: "auto", flex: 1 }}>
              {filtered.length === 0 ? (
                <p style={{ padding: 14, color: "var(--aos-text-secondary)" }}>无匹配实例</p>
              ) : (
                filtered.map((item) => {
                  const gate = catalogByTemplate.get(item.template.assetId);
                  const isSel = (selected?.instanceId || selectedId) === item.instanceId;
                  const isRun = gate?.runtimeReadiness === "runnable";
                  return (
                    <button
                      type="button"
                      key={item.instanceId}
                      onClick={() => { setSelectedId(item.instanceId); setTab("overview"); }}
                      style={{
                        display: "block",
                        width: "100%",
                        textAlign: "left",
                        padding: "12px 14px",
                        border: "none",
                        borderBottom: "1px solid var(--aos-border, #f3f4f6)",
                        borderLeft: isSel ? "3px solid var(--aos-indigo-600, #4f46e5)" : "3px solid transparent",
                        background: isSel ? "var(--aos-indigo-50, #eef2ff)" : "transparent",
                        cursor: "pointer",
                      }}
                    >
                      <div style={{ fontWeight: 600 }}>{item.overlay.displayName || item.instanceId}</div>
                      <div style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4 }}>
                        {gate ? responsibilityDisplayName(gate.template.manifest.responsibility) : "职责未投影"}
                      </div>
                      <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
                        <span className="notice" style={{ padding: "2px 6px", fontSize: 11 }}>{instanceStatusDisplayName(item.status)}</span>
                        <span className="notice" style={{ padding: "2px 6px", fontSize: 11, color: isRun ? "var(--aos-green-700)" : "var(--aos-amber-700)" }}>
                          {isRun ? "可承接任务" : "需核验运行准备"}
                        </span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </aside>

          <section className="card" style={{ padding: 18 }} aria-label="智能体配置壳">
            {!selected ? (
              <p>请选择左侧实例</p>
            ) : (
              <>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "start" }}>
                  <div>
                    <h2 style={{ margin: 0 }}>{selected.overlay.displayName || selected.instanceId}</h2>
                    <p style={{ margin: "6px 0 0", color: "var(--aos-text-secondary)", fontSize: 13 }}>
                      工作区 {selected.tenant.projectId} · 版本 {selected.version}
                      {catalogItem ? ` · ${responsibilityDisplayName(catalogItem.template.manifest.responsibility)}` : ""}
                    </p>
                  </div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <strong style={{ color: selected.status === "active" ? "var(--aos-green-700)" : "var(--aos-amber-700)" }}>
                      {instanceStatusDisplayName(selected.status)}
                    </strong>
                    <strong style={{ color: runnable ? "var(--aos-green-700)" : "var(--aos-amber-700)" }}>
                      {runnable ? "可承接任务" : "需核验运行准备"}
                    </strong>
                  </div>
                </div>

                <nav aria-label="配置分区" style={{ display: "flex", gap: 16, marginTop: 16, borderBottom: "1px solid var(--aos-border, #e5e7eb)" }}>
                  {([
                    ["overview", "概览"],
                    ["tools", "工具箱"],
                    ["try", "试运行"],
                    ["publish", "发布"],
                  ] as const).map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      className="btn"
                      aria-pressed={tab === id}
                      onClick={() => setTab(id)}
                      style={{
                        border: "none",
                        borderRadius: 0,
                        background: "transparent",
                        borderBottom: tab === id ? "2px solid var(--aos-indigo-600, #4f46e5)" : "2px solid transparent",
                        color: tab === id ? "var(--aos-indigo-600, #4f46e5)" : "inherit",
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </nav>

                <div style={{ marginTop: 16 }}>
                  {tab === "overview" && (
                    <div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(210px,1fr))", gap: 10 }}>
                        <article className="notice"><strong>主要职责</strong><p>{catalogItem ? responsibilityDisplayName(catalogItem.template.manifest.responsibility) : "请从目录核验职责定义"}</p></article>
                        <article className="notice"><strong>当前版本</strong><p>实例 v{selected.version} · 模板 r{selected.template.revision}</p><small>{new Date(selected.updatedAt).toLocaleString("zh-CN", { hour12: false })}</small></article>
                        <article className="notice"><strong>授权范围</strong><p>{selected.overlay.allowedCapabilityIds.length ? selected.overlay.allowedCapabilityIds.map(capabilityDisplayName).join("、") : "遵循模板所需能力与组织绑定"}</p></article>
                        <article className="notice"><strong>专业能力</strong><p>{catalogItem?.requiredCapabilityIds.length ? catalogItem.requiredCapabilityIds.map(capabilityDisplayName).join("、") : "由职责模板决定"}</p></article>
                      </div>
                      <p style={{ color: runnable ? "var(--aos-green-700)" : "var(--aos-amber-700)", marginTop: 14 }}>
                        {!catalogItem
                          ? "运行准备尚未对账；请打开智能体目录刷新"
                          : runnable
                            ? "当前运行条件已通过；需绑定真实任务后才会产生运行记录。"
                            : catalogItem.blockers.length
                              ? `需要处理：${formatBlockers(catalogItem.blockers)}`
                              : "需要核验完整能力、技能绑定与依赖快照。"}
                      </p>
                      <section style={{ marginTop: 16 }} aria-label="最近运行">
                        <h3>最近运行</h3>
                        {runError ? <div className="notice bad">运行记录读取失败：{runError}</div> : !recentRuns ? <p>正在读取真实运行记录…</p> : recentRuns.count === 0 ? <div className="notice">当前数字同事尚无运行记录；绑定真实任务并通过安全预检后，记录会在这里出现。</div> : recentRuns.items.map((run) => <article key={run.agentRunId} style={{ borderTop: "1px solid var(--aos-border)", padding: "10px 0" }}><strong>{statusDisplayName(run.status)}</strong><span> · 任务 {run.taskId}</span><small style={{ display: "block" }}>{new Date(run.updatedAt).toLocaleString("zh-CN", { hour12: false })}</small><details><summary>审计引用</summary><code>{run.agentRunId}</code> · <code>{run.taskRunId}</code></details></article>)}
                      </section>
                      <div style={{ display: "flex", gap: 10, marginTop: 12, flexWrap: "wrap" }}>
                        <Link className="btn" to={repair?.repairHref || `/aip/agent-registry?instanceId=${encodeURIComponent(selected.instanceId)}`}>{repair?.repairLabel || "核验运行准备"}</Link>
                        <Link className="btn" to="/aip/studio">智能体配置</Link>
                      </div>
                    </div>
                  )}
                  {tab === "tools" && (
                    <div>
                      <p>工具配置以实例 Overlay 为准，完整三栏见工具面板。本页不伪造「N 个工具已开启」。</p>
                      <Link className="btn primary" to={`/aip/tools?instanceId=${encodeURIComponent(selected.instanceId)}`} style={{ marginTop: 12, display: "inline-flex" }}>打开完整工具面板</Link>
                    </div>
                  )}
                  {tab === "try" && (
                    <div>
                      <p>{runnable ? "目录运行条件已通过。试跑须绑定真实任务与智能体运行上下文，本页不发起外呼。" : "已安装不代表运行条件已经通过；请先完成目录重评，再进入工具面板绑定真实上下文。"}</p>
                      <Link className="btn" to={runnable ? `/aip/tools?instanceId=${encodeURIComponent(selected.instanceId)}&intent=trial` : `/aip/agent-registry?instanceId=${encodeURIComponent(selected.instanceId)}`} title={runnable ? "到工具面板绑定真实上下文后试跑" : "到智能体目录核验依赖并刷新运行准备"}>
                        {runnable ? "前往工具面板试跑" : "核验运行准备"}
                      </Link>
                    </div>
                  )}
                  {tab === "publish" && (
                    <div>
                      <p>版本启停、回退与重新安装必须在目录中核对精确版本并人工确认；本列表不会绕过审批。</p>
                      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
                        <Link className="btn" to={`/aip/agent-registry?instanceId=${encodeURIComponent(selected.instanceId)}&intent=lifecycle`}>启停与版本管理</Link>
                        <Link className="btn" to="/aip/agent-marketplace">查找可用版本</Link>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </PageChrome>
  );
}
