import { evaluateWorkshopOperatingReadiness, type OperatingEvidence } from "./workshopOperatingReadiness";

function value(value: number | null, suffix = ""): string {
  return value === null ? "未知（不以 0 代替）" : `${value}${suffix}`;
}

export function WorkshopOperatingReadinessCard({ evidence = {} }: { evidence?: OperatingEvidence }) {
  const result = evaluateWorkshopOperatingReadiness(evidence);
  const rootReady = Boolean(evidence.releaseRef && evidence.bundleRef && evidence.installationRef);
  const cells = { display: "grid", gap: 4, minWidth: 0, padding: 10, border: "1px solid var(--aos-border)", background: "var(--aos-surface)" } as const;
  return <section className={`workshop-operating-readiness is-${result.status}`} aria-label="W8-09 运营就绪预检" data-testid="workshop-operating-readiness" style={{ display: "grid", gap: 12, padding: 16, border: "1px solid var(--aos-border)", borderLeft: "4px solid var(--aos-amber-600, #d97706)", background: "color-mix(in srgb, var(--aos-surface) 95%, #fffbeb)" }}>
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}><div style={{ display: "grid", gap: 4 }}><span style={{ color: "var(--aos-text-tertiary)", fontSize: 11, letterSpacing: ".08em" }}>W8-09 · READ-ONLY</span><h2 style={{ margin: 0 }}>SLO、Unknown Backlog、Usage 与 Runbook</h2></div><strong style={{ padding: "5px 9px", border: "1px solid var(--aos-amber-600, #d97706)", color: "var(--aos-amber-700, #b45309)", fontSize: 11 }}>{result.status === "ready" ? "证据合同闭合" : "运营失败关闭"}</strong></header>
    <p>只有同 release 权威证据可复算；未知、partial、forbidden、policy block 与 timeout 不从分母消失，Ack 不等于恢复。</p>
    <div className="workshop-operating-layers" aria-label="运营贡献分层" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 8 }}>
      <div style={cells}><span>原子 Skill</span><strong>{rootReady ? "exact refs" : "unknown"}</strong><small>只读 SLI / Usage / Receipt 读取</small></div>
      <div style={cells}><span>Logic 编排</span><strong>{result.status}</strong><small>同 cutoff 守恒与失败关闭</small></div>
      <div style={cells}><span>数字同事绑定</span><strong>unknown</strong><small>未从页面状态推断真实值班人</small></div>
      <div style={cells}><span>工作台贡献</span><strong>{result.blockerCodes.length}</strong><small>独立阻断项</small></div>
    </div>
    <div className="workshop-operating-metrics" aria-label="运营权威指标" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: 8 }}>
      <div style={cells}><span>Unknown backlog</span><strong>{value(result.unknownBacklogCount)}</strong></div>
      <div style={cells}><span>Oldest age</span><strong>{value(result.oldestUnknownAgeMs === null ? null : Math.floor(result.oldestUnknownAgeMs / 60000), " min")}</strong></div>
      <div style={cells}><span>五轴 closure</span><strong>{result.closedAxes} / 5</strong></div>
      <div style={cells}><span>Usage</span><strong>{result.usageState === "measured" ? "权威分桶可读" : "未知（不以 0 代替）"}</strong></div>
      <div style={cells}><span>Runbook</span><strong>{result.runbookState === "drilled" ? "演练闭合" : result.runbookState === "defined" ? "仅已定义" : "未提供"}</strong></div>
    </div>
    {result.blockerCodes.length ? <div className="workshop-operating-blockers"><strong>当前缺失条件</strong><ul>{result.blockerCodes.slice(0, 8).map((code) => <li key={code}>{code}</li>)}</ul>{result.blockerCodes.length > 8 ? <small>另有 {result.blockerCodes.length - 8} 项；完整清单保留在判定结果中。</small> : null}</div> : <div className="workshop-operating-clear">同 release 工程证据合同已闭合；真实 operational/release 仍由独立发布门裁决。</div>}
    <footer>告警 / Ack / Silence / Escalate / Resolve / Reconcile：全部禁用 · 无 Provider 调用 · 无外部副作用 · 无发布</footer>
  </section>;
}
