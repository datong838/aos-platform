import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { aipMarketplaceImport, type MarketplaceCatalog } from "../../api/aipMarketplaceImport";
import { PageChrome } from "../../components/PageChrome";
import { AipReadinessActionCard } from "../../components/aip/AipReadinessActionCard";
import { businessDisplayName, formatBlockers } from "../../lib/aipChineseLabels";

export function AgentMarketplacePage() {
  const [catalog, setCatalog] = useState<MarketplaceCatalog | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | "installed" | "available">("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setCatalog(await aipMarketplaceImport.listMarketplace()); setError(""); }
    catch (value) { setCatalog(null); setError(String((value as Error).message || value)); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const blockerCodes = catalog ? Array.from(new Set(catalog.items.flatMap((item) => item.agents.flatMap((agent) => agent.blockers)))) : [];
  const visiblePackages = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (catalog?.items || []).map((item) => ({
      ...item,
      agents: item.agents.filter((agent) => {
        const matchesQuery = !q || `${agent.displayName} ${agent.templateId}`.toLowerCase().includes(q);
        const matchesStatus = status === "all" || (status === "installed" ? agent.installed : !agent.installed);
        return matchesQuery && matchesStatus;
      }),
    })).filter((item) => item.agents.length > 0 || (!q && status === "all"));
  }, [catalog, query, status]);

  return (
    <PageChrome title="智能体市场" lede="发现、比较并安全引入可复用数字同事方案">
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
        <button className="btn" type="button" onClick={() => void load()}>刷新目录</button>
        <Link className="btn" to="/aip/agent-registry">智能体目录</Link>
        <Link className="btn" to="/aip/agents">智能体列表</Link>
        <Link className="btn" to="/aip/agent-import">外部智能体预检</Link>
      </div>
      <section className="card" aria-label="市场筛选" style={{ padding: 14, marginBottom: 14, display: "flex", gap: 10, flexWrap: "wrap" }}>
        <input className="input" aria-label="搜索数字同事" placeholder="搜索名称或职责…" value={query} onChange={(event) => setQuery(event.target.value)} style={{ minWidth: 260, padding: "8px 10px" }} />
        <select className="input" aria-label="筛选安装状态" value={status} onChange={(event) => setStatus(event.target.value as typeof status)} style={{ padding: "8px 10px" }}>
          <option value="all">全部方案</option><option value="installed">已安装</option><option value="available">可申请引入</option>
        </select>
      </section>
      <div className="notice" role="note" style={{ padding: 12, marginBottom: 16 }}>
        市场只投影已版本化资产包，不把发现等同安装。安装必须经过审批、Overlay 和精确绑定；本页没有直接写入按钮。
      </div>
      {error ? <div className="notice bad" role="alert">目录读取失败：{error}。当前运行基线尚未提供目录时，请由平台集成人员完成权威版本接入；本页不会用演示资产替代。</div> : null}
      {!catalog && !error ? <div className="card" role="status">正在读取组织市场目录…</div> : catalog?.count === 0 ? (
        <div className="card"><h3>暂无可发现资产包</h3><p>目录返回为空；没有用演示包填充。</p></div>
      ) : catalog ? <>{blockerCodes.length ? <AipReadinessActionCard
        status="方案包已发现，运行准备需核验"
        owner="AIP 智能体运行平台 / 模型供应商"
        ownerHref="/aip/agent-registry"
        impact="当前方案包可以查看和审计；通过审批和运行准备核验后才能承接业务任务。"
        missingConditions={[formatBlockers(blockerCodes)]}
        reasons={[formatBlockers(blockerCodes)]}
        actionLabel="进入智能体目录刷新运行准备"
        actionHref="/aip/agent-registry"
        technicalCodes={blockerCodes}
      /> : null}{visiblePackages.length === 0 ? <div className="card"><h3>没有匹配的数字同事</h3><p>请调整名称或安装状态筛选。</p></div> : visiblePackages.map((item) => (
        <section className="card" key={`${item.packageId}@${item.version}`} style={{ padding: 18, marginBottom: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
            <div>
              <h2 style={{ margin: 0 }}>{businessDisplayName(item.displayName, "智能体方案包")}</h2>
              <p style={{ margin: "6px 0", color: "var(--aos-text-secondary)" }}>发布方：{item.publisher} · 使用许可：{item.license}</p>
              <details><summary>方案包技术标识（审计用）</summary><code>{item.packageId}@{item.version}</code><br /><code title={item.contentHash}>内容摘要 {item.contentHash.slice(0, 16)}…</code></details>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignContent: "start" }}>
              <span className="notice" style={{ padding: "6px 10px" }}>智能体 {item.agentCount}</span>
              <span className="notice" style={{ padding: "6px 10px" }}>技能 {item.skillCount}</span>
              <span className="notice" style={{ padding: "6px 10px" }}>能力 {item.capabilityCount}</span>
              <span className="notice" style={{ padding: "6px 10px" }}>可承接任务 {item.runnableCount}/{item.installedCount}</span>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(230px,1fr))", gap: 10, marginTop: 16 }}>
            {item.agents.map((agent) => (
              <article key={agent.templateId} style={{ border: "1px solid var(--aos-border)", borderRadius: 6, padding: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <strong>{businessDisplayName(agent.displayName, "数字同事")}</strong><span>{agent.runtimeReadiness === "runnable" ? "可承接任务" : agent.installed ? "已安装·需核验" : "可申请引入"}</span>
                </div>
                <p style={{ minHeight: 38, color: "var(--aos-text-secondary)", fontSize: 13 }}>{agent.blockers.length ? "运行准备需要核验；请按处理指引继续。" : "运行准备已通过"}</p>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button className="btn" type="button" onClick={() => setExpanded((value) => value === agent.templateId ? null : agent.templateId)}>{expanded === agent.templateId ? "收起详情" : "查看详情"}</button>
                  <Link className="btn primary" to={item.installAuthorized ? `/aip/agent-registry?templateId=${encodeURIComponent(agent.templateId)}&intent=install` : `/aip/agent-import?templateId=${encodeURIComponent(agent.templateId)}&packageId=${encodeURIComponent(item.packageId)}&sourceId=${encodeURIComponent(item.sourceRef.resourceId)}&displayName=${encodeURIComponent(agent.displayName)}&licenseId=${encodeURIComponent(item.license)}`}>{agent.installed ? "管理实例" : item.installAuthorized ? "确认引入" : "提交引入预检"}</Link>
                </div>
                {expanded === agent.templateId ? <div className="notice" style={{ marginTop: 10 }}><strong>引入说明</strong><p>来源：{item.publisher} · 版本 {item.version} · 许可 {item.license}</p><p>权限与依赖：{agent.blockers.length ? formatBlockers(agent.blockers) : "已通过当前组织核验"}</p><p>用户评价：当前权威方案包未提供公开评价；请以来源、许可、安全扫描和审批记录为准。</p><details><summary>技术标识（审计用）</summary><code>{agent.templateId}</code></details></div> : null}
              </article>
            ))}
          </div>
          <p style={{ marginBottom: 0, marginTop: 14, color: "var(--aos-text-secondary)" }}>
            引入权限：{item.installAuthorized ? "当前组织可进入确认流程" : "需要完成来源预检、审批与精确绑定"}
          </p>
        </section>
      ))}</> : null}
    </PageChrome>
  );
}
