import { OPERATIONAL_CAPABILITIES, evaluateWorkshopOperationalReleaseDecision, type OperationalReleaseEvidence } from "./workshopOperationalReleaseDecision";

export function WorkshopOperationalReleaseDecisionCard({ evidence = {} }: { evidence?: OperationalReleaseEvidence }) {
  const result = evaluateWorkshopOperationalReleaseDecision(evidence);
  const cell = { display: "grid", gap: 4, minWidth: 0, padding: 10, border: "1px solid var(--aos-border)", background: "var(--aos-surface)" } as const;
  return <section className={`workshop-operational-release-decision is-${result.decision}`} aria-label="W8-12 运营就绪与发布决定" data-testid="workshop-operational-release-decision" style={{ display: "grid", gap: 12, padding: 16, border: "1px solid var(--aos-border)", borderLeft: "4px solid var(--aos-red-600, #dc2626)", background: "color-mix(in srgb, var(--aos-surface) 96%, #fff7ed)" }}>
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}><div style={{ display: "grid", gap: 4 }}><span style={{ color: "var(--aos-text-tertiary)", fontSize: 11, letterSpacing: ".08em" }}>W8-12 · READ-ONLY · NO FLAG · NO RELEASE</span><h2 style={{ margin: 0 }}>逐 Capability 运营就绪与发布决定</h2></div><strong>{result.decision === "go" ? "GO（仅合同判定）" : "NO_GO · 失败关闭"}</strong></header>
    <p>连续开发授权不是发布批准；每项能力、候选版本、maker-checker、rollout、rollback 与 Decision Receipt 必须独立闭合。</p>
    <div aria-label="运营决定贡献分层" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 8 }}>
      <div style={cell}><span>原子 Skill</span><strong>{result.candidateState === "exact" ? "exact candidate" : "unknown"}</strong><small>合同、租户、安全与运营原子证据</small></div>
      <div style={cell}><span>Logic 编排</span><strong>{result.capabilitiesReady} / 8</strong><small>逐 capability 独立裁决</small></div>
      <div style={cell}><span>数字同事绑定</span><strong>{result.capabilitiesBlocked} blocked</strong><small>高风险阻断不被汇总掩盖</small></div>
      <div style={cell}><span>工作台贡献</span><strong>{result.blockerCodes.length}</strong><small>NO_GO 独立阻断项</small></div>
    </div>
    <div aria-label="逐 capability 运营就绪" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 8 }}>{OPERATIONAL_CAPABILITIES.map((capability) => {
      const item = evidence.capabilities?.find((entry) => entry.capabilityId === capability.id);
      return <div style={cell} key={capability.id}><span>{capability.label}</span><strong>{item?.status ?? "blocked"}</strong><small>{capability.risk} · {item?.nextAllowedAction || "等待 exact EvidencePack"}</small></div>;
    })}</div>
    <div aria-label="发布决定权威状态" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 8 }}>
      <div style={cell}><span>Candidate</span><strong>{result.candidateState === "exact" ? "exact" : "未知"}</strong></div>
      <div style={cell}><span>W8-11</span><strong>{result.cumulativeState}</strong></div>
      <div style={cell}><span>Approval</span><strong>{result.approvalState === "valid" ? "valid" : "缺失/失效"}</strong></div>
      <div style={cell}><span>Rollout / Rollback</span><strong>{result.rolloutState === "complete" ? "complete" : "缺失"}</strong></div>
      <div style={cell}><span>Decision Receipt</span><strong>{result.receiptState === "exact" ? "exact" : "缺失"}</strong></div>
    </div>
    {result.blockerCodes.length ? <div><strong>当前 NO_GO 条件</strong><ul>{result.blockerCodes.slice(0, 8).map((code) => <li key={code}>{code}</li>)}</ul>{result.blockerCodes.length > 8 ? <small>另有 {result.blockerCodes.length - 8} 项；完整清单保留在判定结果中。</small> : null}</div> : <p>合同输入允许 GO；真实阶段开始前仍需回读 canonical authority。</p>}
    <footer>Approve Candidate / Open Feature Flag / Start Rollout / Stop / Rollback / Fail-forward / Release：全部禁用 · 无真实租户变更 · 无外部副作用 · 无发布</footer>
  </section>;
}
