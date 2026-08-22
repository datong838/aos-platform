import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { aipMarketplaceImport, type MarketplaceCatalog } from "../../api/aipMarketplaceImport";
import { PageChrome } from "../../components/PageChrome";
import { formatBlockers } from "../../lib/aipChineseLabels";

export function AgentMarketplacePage() {
  const [catalog, setCatalog] = useState<MarketplaceCatalog | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try { setCatalog(await aipMarketplaceImport.listMarketplace()); setError(""); }
    catch (value) { setCatalog(null); setError(String((value as Error).message || value)); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <PageChrome title="智能体市场" lede="真实版本包只读发现 · 安装、审批与绑定保持权威分离">
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
        <button className="btn" type="button" onClick={() => void load()}>刷新目录</button>
        <Link className="btn" to="/aip/agent-registry">智能体目录</Link>
        <Link className="btn" to="/aip/agents">智能体列表</Link>
        <Link className="btn" to="/aip/agent-import">外部智能体预检</Link>
      </div>
      <div className="notice" role="note" style={{ padding: 12, marginBottom: 16 }}>
        市场只投影已版本化资产包，不把发现等同安装。安装必须经过审批、Overlay 和精确绑定；本页没有直接写入按钮。
      </div>
      {error ? <div className="notice bad" role="alert">目录读取失败：{error}</div> : null}
      {!catalog ? <div className="card" role="status">正在读取组织市场目录…</div> : catalog.count === 0 ? (
        <div className="card"><h3>暂无可发现资产包</h3><p>目录返回为空；没有用演示包填充。</p></div>
      ) : catalog.items.map((item) => (
        <section className="card" key={`${item.packageId}@${item.version}`} style={{ padding: 18, marginBottom: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
            <div>
              <h2 style={{ margin: 0 }}>{item.displayName}</h2>
              <p style={{ margin: "6px 0", color: "var(--aos-text-secondary)" }}>{item.packageId}@{item.version} · {item.publisher} · {item.license}</p>
              <code title={item.contentHash}>内容哈希 {item.contentHash.slice(0, 16)}…</code>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignContent: "start" }}>
              <span className="notice" style={{ padding: "6px 10px" }}>智能体 {item.agentCount}</span>
              <span className="notice" style={{ padding: "6px 10px" }}>技能 {item.skillCount}</span>
              <span className="notice" style={{ padding: "6px 10px" }}>能力 {item.capabilityCount}</span>
              <span className="notice" style={{ padding: "6px 10px" }}>可派发 {item.runnableCount}/{item.installedCount}</span>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(230px,1fr))", gap: 10, marginTop: 16 }}>
            {item.agents.map((agent) => (
              <article key={agent.templateId} style={{ border: "1px solid var(--aos-border)", borderRadius: 6, padding: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <strong>{agent.displayName}</strong><span>{agent.runtimeReadiness === "runnable" ? "可派发" : agent.installed ? "已安装·受阻" : "未安装"}</span>
                </div>
                <p style={{ minHeight: 38, color: "var(--aos-text-secondary)", fontSize: 13 }}>{agent.blockers.length ? formatBlockers(agent.blockers) : "运行门已满足"}</p>
                <Link to={agent.repairHref}>{agent.repairLabel} →</Link>
              </article>
            ))}
          </div>
          <p style={{ marginBottom: 0, marginTop: 14, color: "var(--aos-text-secondary)" }}>
            安装授权：{item.installAuthorized ? "已授权" : "未授权（需进入智能体目录完成审批与绑定）"}
          </p>
        </section>
      ))}
    </PageChrome>
  );
}
