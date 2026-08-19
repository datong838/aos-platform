import { Link } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";

/**
 * W-G1b · 市场发现页（只读壳）
 * 禁止把演示 Agent 写入 org-org/dev-project；权威安装仍走智能体目录绑定台。
 */
export function AgentMarketplacePage() {
  return (
    <PageChrome title="智能体市场" lede="发现向只读目录 · 不写入本组织权威租户">
      <div className="notice" role="note" style={{ padding: 12, marginBottom: 16 }}>
        本页只做发现与跳转。安装与绑定真相在「智能体目录」；演示样例<strong>不会</strong>写入当前组织工作区。
      </div>
      <section className="card" style={{ padding: 18 }}>
        <h3 style={{ marginTop: 0 }}>发现入口</h3>
        <ul style={{ margin: "8px 0 16px", paddingLeft: 18, color: "var(--aos-text-secondary)" }}>
          <li>电商六数字同事：请到绑定台查看安装与就绪。</li>
          <li>外部市场包：后续只读投影；本波不落库。</li>
        </ul>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <Link className="btn primary" to="/aip/agent-registry">打开智能体目录（绑定台）</Link>
          <Link className="btn" to="/aip/agents">智能体列表</Link>
          <Link className="btn" to="/aip/agent-import">智能体导入</Link>
        </div>
      </section>
    </PageChrome>
  );
}
