import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { aipMarketplaceImport, type MarketplaceCatalog } from "../../api/aipMarketplaceImport";
import { PageChrome } from "../../components/PageChrome";
import { AipReadinessActionCard } from "../../components/aip/AipReadinessActionCard";
import { businessDisplayName, formatBlockers } from "../../lib/aipChineseLabels";

export function AgentMarketplacePage() {
  const [catalog, setCatalog] = useState<MarketplaceCatalog | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try { setCatalog(await aipMarketplaceImport.listMarketplace()); setError(""); }
    catch (value) { setCatalog(null); setError(String((value as Error).message || value)); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const blockerCodes = catalog ? Array.from(new Set(catalog.items.flatMap((item) => item.agents.flatMap((agent) => agent.blockers)))) : [];

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
      {error ? <div className="notice bad" role="alert">目录读取失败：{error}。当前运行基线尚未提供目录时，请由平台集成人员完成权威版本接入；本页不会用演示资产替代。</div> : null}
      {!catalog && !error ? <div className="card" role="status">正在读取组织市场目录…</div> : catalog?.count === 0 ? (
        <div className="card"><h3>暂无可发现资产包</h3><p>目录返回为空；没有用演示包填充。</p></div>
      ) : catalog ? <>{blockerCodes.length ? <AipReadinessActionCard
        status="方案包已发现，正在补齐运行条件"
        owner="AIP 智能体运行平台 / 模型供应商"
        ownerHref="/aip/agent-registry"
        impact="当前方案包可以查看和审计，但不会直接承接新的业务任务。"
        missingConditions={[formatBlockers(blockerCodes)]}
        reasons={[formatBlockers(blockerCodes)]}
        actionLabel="进入智能体目录刷新运行准备"
        actionHref="/aip/agent-registry"
        technicalCodes={blockerCodes}
      /> : null}{catalog.items.map((item) => (
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
              <span className="notice" style={{ padding: "6px 10px" }}>可派发 {item.runnableCount}/{item.installedCount}</span>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(230px,1fr))", gap: 10, marginTop: 16 }}>
            {item.agents.map((agent) => (
              <article key={agent.templateId} style={{ border: "1px solid var(--aos-border)", borderRadius: 6, padding: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <strong>{businessDisplayName(agent.displayName, "未命名智能体")}</strong><span>{agent.runtimeReadiness === "runnable" ? "可派发" : agent.installed ? "已安装·受阻" : "未安装"}</span>
                </div>
                <p style={{ minHeight: 38, color: "var(--aos-text-secondary)", fontSize: 13 }}>{agent.blockers.length ? "仍需补齐运行条件；请按页面上方处理指引继续。" : "运行准备已完成"}</p>
              </article>
            ))}
          </div>
          <p style={{ marginBottom: 0, marginTop: 14, color: "var(--aos-text-secondary)" }}>
            安装授权：{item.installAuthorized ? "已授权" : "未授权（需进入智能体目录完成审批与绑定）"}
          </p>
        </section>
      ))}</> : null}
    </PageChrome>
  );
}
