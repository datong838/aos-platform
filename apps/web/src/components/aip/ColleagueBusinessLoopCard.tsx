import { Link } from "react-router-dom";

import { buildColleagueBusinessLoop } from "./colleagueBusinessLoops";

export function ColleagueBusinessLoopCard({ roleKey, logicIds, runtimeReadiness }: {
  roleKey: string;
  logicIds: readonly string[];
  runtimeReadiness: "blocked" | "runnable";
}) {
  const loop = buildColleagueBusinessLoop(roleKey, logicIds, runtimeReadiness);
  const stages = [
    ["业务输入", loop.businessInput],
    ["已版本化业务逻辑", loop.logicLabels.length ? `${loop.logicLabels.length} 项已由权威目录返回` : "业务逻辑需核验"],
    ["数字同事产出", loop.businessOutput],
    ["工作台贡献", loop.contributionLabel],
  ] as const;
  return <section aria-label={`${loop.roleName}业务闭环`} data-testid={`colleague-loop-${loop.roleKey}`} style={{ marginTop: 12, padding: 12, border: "1px solid var(--aos-border)", borderRadius: 8, background: "var(--aos-surface-subtle, #f8fafc)" }}>
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "baseline" }}>
      <strong>{loop.roleName} · 业务闭环</strong>
      <span style={{ fontSize: 12, color: runtimeReadiness === "runnable" ? "var(--aos-green-700)" : "var(--aos-amber-700)" }}>{runtimeReadiness === "runnable" ? "运行条件已核验" : "运行条件需核验"}</span>
    </div>
    <ol style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: 8, margin: "10px 0", padding: 0, listStyle: "none" }}>
      {stages.map(([label, value], index) => <li key={label} style={{ minWidth: 0, padding: 8, borderLeft: "3px solid var(--aos-blue-500, #3b82f6)", background: "var(--aos-surface)" }}>
        <small style={{ display: "block", color: "var(--aos-text-secondary)" }}>{index + 1}. {label}</small>
        <span style={{ display: "block", marginTop: 4, fontSize: 13 }}>{value}</span>
      </li>)}
    </ol>
    {loop.logicLabels.length ? <details style={{ fontSize: 12 }}><summary>业务逻辑技术标识（审计用）</summary><code>{loop.logicLabels.join("、")}</code></details> : null}
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
      <Link className="btn" to={loop.workshopHref} data-testid="colleague-enter-workshop">进入业务工作台</Link>
      <Link className="btn" to={loop.contributionHref} data-testid="colleague-read-contribution">回读工作台贡献</Link>
    </div>
  </section>;
}
