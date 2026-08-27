import { evaluateWorkshopOperatingReadiness, type OperatingEvidence } from "./workshopOperatingReadiness";

function value(value: number | null, suffix = ""): string {
  return value === null ? "未知（不以 0 代替）" : `${value}${suffix}`;
}

export function WorkshopOperatingReadinessCard({ evidence = {} }: { evidence?: OperatingEvidence }) {
  const result = evaluateWorkshopOperatingReadiness(evidence);
  const rootReady = Boolean(evidence.releaseRef && evidence.bundleRef && evidence.installationRef);
  const cells = { display: "grid", gap: 4, minWidth: 0, padding: 10, border: "1px solid var(--aos-border)", background: "var(--aos-surface)" } as const;
  return <section className={`workshop-operating-readiness is-${result.status}`} aria-label="运营就绪预检" data-testid="workshop-operating-readiness" style={{ display: "grid", gap: 12, padding: 16, border: "1px solid var(--aos-border)", borderLeft: "4px solid var(--aos-amber-600, #d97706)", background: "color-mix(in srgb, var(--aos-surface) 95%, #fffbeb)" }}>
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}><div style={{ display: "grid", gap: 4 }}><span style={{ color: "var(--aos-text-tertiary)", fontSize: 11, letterSpacing: ".08em" }}>运营状态 · 只读</span><h2 style={{ margin: 0 }}>服务目标、待核对事项、使用情况与处置手册</h2></div><strong style={{ padding: "5px 9px", border: "1px solid var(--aos-amber-600, #d97706)", color: "var(--aos-amber-700, #b45309)", fontSize: 11 }}>{result.status === "ready" ? "证据已闭合" : "等待运营证据"}</strong></header>
    <p>只有同 release 权威证据可复算；未知、partial、forbidden、policy block 与 timeout 不从分母消失，Ack 不等于恢复。</p>
    <div className="workshop-operating-layers" aria-label="运营贡献分层" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 8 }}>
      <div style={cells}><span>原子技能</span><strong>{rootReady ? "精确引用已读取" : "待核对"}</strong><small>只读读取服务指标、使用情况与回读凭证</small></div>
      <div style={cells}><span>逻辑编排</span><strong>{result.status === "ready" ? "已就绪" : "等待条件"}</strong><small>同一数据截止面的数量守恒与安全关闭</small></div>
      <div style={cells}><span>数字同事绑定</span><strong>待核对</strong><small>未从页面状态推断真实值班人</small></div>
      <div style={cells}><span>工作台贡献</span><strong>{result.blockerCodes.length}</strong><small>独立阻断项</small></div>
    </div>
    <div className="workshop-operating-metrics" aria-label="运营权威指标" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: 8 }}>
      <div style={cells}><span>待核对事项</span><strong>{value(result.unknownBacklogCount)}</strong></div>
      <div style={cells}><span>最长等待</span><strong>{value(result.oldestUnknownAgeMs === null ? null : Math.floor(result.oldestUnknownAgeMs / 60000), " 分钟")}</strong></div>
      <div style={cells}><span>五轴 closure</span><strong>{result.closedAxes} / 5</strong></div>
      <div style={cells}><span>使用情况</span><strong>{result.usageState === "measured" ? "权威分桶可读" : "未知（不以 0 代替）"}</strong></div>
      <div style={cells}><span>处置手册</span><strong>{result.runbookState === "drilled" ? "演练闭合" : result.runbookState === "defined" ? "仅已定义" : "未提供"}</strong></div>
    </div>
    {result.blockerCodes.length ? <div className="workshop-operating-blockers"><strong>当前缺失条件</strong><ul>{result.blockerCodes.slice(0, 8).map((code) => <li key={code}>{code}</li>)}</ul>{result.blockerCodes.length > 8 ? <small>另有 {result.blockerCodes.length - 8} 项；完整清单保留在判定结果中。</small> : null}</div> : <div className="workshop-operating-clear">同 release 工程证据合同已闭合；真实 operational/release 仍由独立发布门裁决。</div>}
    <footer>告警确认、静默、升级、解决与结果协调：全部禁用 · 无外部调用 · 无业务副作用 · 无发布</footer>
  </section>;
}
