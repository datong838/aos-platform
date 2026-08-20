import { Link } from "react-router-dom";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  aipAgentControl,
  type AgentInstanceListResponse,
  type AgentRuntimeReadinessResponse,
} from "../../api/aipAgentControl";
import { PageChrome } from "../../components/PageChrome";
import { formatBlockers, instanceStatusDisplayName, responsibilityDisplayName } from "../../lib/aipChineseLabels";

type DetailTab = "overview" | "tools" | "try" | "publish";

export function CanonicalAgentsPage() {
  const [data, setData] = useState<AgentInstanceListResponse | null>(null);
  const [runtime, setRuntime] = useState<AgentRuntimeReadinessResponse | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<DetailTab>("overview");

  const load = useCallback(async () => {
    try {
      const [instances, readiness] = await Promise.all([
        aipAgentControl.listInstances(),
        aipAgentControl.runtimeReadiness(),
      ]);
      setData(instances);
      setRuntime(readiness);
      setError("");
      setSelectedId((prev) => {
        if (prev && instances.items.some((item) => item.instanceId === prev)) return prev;
        return instances.items[0]?.instanceId ?? null;
      });
    } catch (e) {
      setData(null);
      setRuntime(null);
      setError(String((e as Error).message || e));
    }
  }, []);

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
  const runnable = catalogItem?.runtimeReadiness === "runnable";

  return (
    <PageChrome title="智能体列表" lede="已安装数字同事 · 左列表右配置壳（对齐蓝图密度，权威不写演示样例）">
      <div style={{ display: "flex", gap: 12, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
        <button className="btn" type="button" onClick={() => void load()}>刷新</button>
        <Link className="btn" to="/aip/agent-registry">智能体目录</Link>
        <Link className="btn" to="/aip/agent-marketplace">市场发现</Link>
        <Link className="btn" to="/aip/tools">工具面板</Link>
        {runtime ? (
          <>
            <span className="notice" style={{ padding: "6px 10px" }}>实例 {data?.count ?? 0}</span>
            <span className="notice" style={{ padding: "6px 10px" }} data-testid="agents-dispatchable-ratio">
              可派发 {runtime.catalog.stats.runnableCount}/{runtime.catalog.stats.installedCount}（已安装≠可派发）
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
                          {isRun ? "可派发" : "不可派发"}
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
                      {runnable ? "目录可派发" : "目录不可派发"}
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
                      <p style={{ color: runnable ? "var(--aos-green-700)" : "var(--aos-amber-700)" }}>
                        {!catalogItem
                          ? "运行就绪尚未对账；请打开智能体目录刷新"
                          : runnable
                            ? "可派发（目录 runnable；本页不直接外呼）"
                            : catalogItem.blockers.length
                              ? `已安装≠可派发：${formatBlockers(catalogItem.blockers)}`
                              : "已安装≠可派发：缺少完整能力/技能绑定与依赖快照"}
                      </p>
                      <div style={{ display: "flex", gap: 10, marginTop: 12, flexWrap: "wrap" }}>
                        <Link className="btn" to="/aip/agent-registry">去目录重评就绪</Link>
                        <Link className="btn" to="/aip/studio">Studio</Link>
                      </div>
                    </div>
                  )}
                  {tab === "tools" && (
                    <div>
                      <p>工具配置以实例 Overlay 为准，完整三栏见工具面板。本页不伪造「N 个工具已开启」。</p>
                      <Link className="btn primary" to="/aip/tools" style={{ marginTop: 12, display: "inline-flex" }}>打开完整工具面板</Link>
                    </div>
                  )}
                  {tab === "try" && (
                    <div>
                      <p>{runnable ? "目录可派发。试跑须绑定真实 Task/AgentRun 上下文（见工具面板试跑轨），本页不发起外呼。" : "目录不可派发（已安装≠可派发），试运行禁用。"}</p>
                      <button className="btn" type="button" disabled={!runnable} title={runnable ? "请到工具面板绑定真实上下文后试跑" : "依赖未齐，不可派发"}>
                        {runnable ? "前往工具面板试跑" : "试运行（不可派发）"}
                      </button>
                      {runnable ? <div style={{ marginTop: 10 }}><Link to="/aip/tools">打开工具面板 →</Link></div> : null}
                    </div>
                  )}
                  {tab === "publish" && (
                    <div>
                      <p>实例发布/导入不在本列表伪造成功。技能发布见独立发布台；安装与绑定见目录。</p>
                      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
                        <Link className="btn" to="/aip/agent-registry">智能体目录</Link>
                        <Link className="btn" to="/aip/agent-import">智能体导入</Link>
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
