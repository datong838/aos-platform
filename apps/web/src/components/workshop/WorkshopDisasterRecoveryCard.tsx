import { evaluateWorkshopDisasterRecovery, type DrEvidence } from "./workshopDisasterRecoveryReadiness";

export function WorkshopDisasterRecoveryCard({ evidence = {} }: { evidence?: DrEvidence }) {
  const result = evaluateWorkshopDisasterRecovery(evidence);
  const cell = { display: "grid", gap: 4, minWidth: 0, padding: 10, border: "1px solid var(--aos-border)", background: "var(--aos-surface)" } as const;
  const objective = result.objectivesState === "measured_within_approved" ? "批准且实测达标" : result.objectivesState === "missed" ? "实测未达标" : "未知（不以 0 代替）";
  return <section className={`workshop-dr-readiness is-${result.status}`} aria-label="灾难恢复预检" data-testid="workshop-dr-readiness" style={{ display: "grid", gap: 12, padding: 16, border: "1px solid var(--aos-border)", borderLeft: "4px solid var(--aos-red-600, #dc2626)", background: "color-mix(in srgb, var(--aos-surface) 96%, #fef2f2)" }}>
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}><div style={{ display: "grid", gap: 4 }}><span style={{ color: "var(--aos-text-tertiary)", fontSize: 11, letterSpacing: ".08em" }}>灾备状态 · 只读</span><h2 style={{ margin: 0 }}>备份恢复、数据视图重建、租户隔离与灾难恢复</h2></div><strong>{result.status === "ready" ? "证据已闭合" : "等待灾备证据"}</strong></header>
    <p>只复算同 release EvidencePack；authority 恢复、disposable projection、RLS 与外部事实分别守恒，数据库回档不撤销外部效果。</p>
    <div aria-label="灾备贡献分层" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 8 }}>
      <div style={cell}><span>原子技能</span><strong>{result.backupState === "verified" ? "清单已精确核对" : "待核对"}</strong><small>只读核对数据清单、备份清单与回读凭证</small></div>
      <div style={cell}><span>逻辑编排</span><strong>{result.status === "ready" ? "已就绪" : "等待条件"}</strong><small>恢复顺序、守恒与安全关闭</small></div>
      <div style={cell}><span>数字同事绑定</span><strong>待核对</strong><small>不从页面推断制作、复核与执行责任人</small></div>
      <div style={cell}><span>工作台贡献</span><strong>{result.blockerCodes.length}</strong><small>独立阻断项</small></div>
    </div>
    <div aria-label="灾备证据指标" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: 8 }}>
      <div style={cell}><span>Authority inventory</span><strong>{result.authorityDomainsVerified} / 8</strong></div>
      <div style={cell}><span>Backup manifest</span><strong>{result.backupState === "verified" ? "已验证" : "未知（不以 0 代替）"}</strong></div>
      <div style={cell}><span>RLS negatives</span><strong>{result.rlsChecksPassed} / 4</strong></div>
      <div style={cell}><span>Projection rebuild</span><strong>{result.projectionState === "rebuild_verified" ? "守恒闭合" : "未知（不以 0 代替）"}</strong></div>
      <div style={cell}><span>External reconcile</span><strong>{result.externalAxesClosed} / 5</strong></div>
      <div style={cell}><span>RPO / RTO</span><strong>{objective}</strong></div>
      <div style={cell}><span>DR drills</span><strong>{result.drillsPassed} / 10</strong></div>
    </div>
    {result.blockerCodes.length ? <div><strong>当前缺失条件</strong><ul>{result.blockerCodes.slice(0, 8).map((code) => <li key={code}>{code}</li>)}</ul>{result.blockerCodes.length > 8 ? <small>另有 {result.blockerCodes.length - 8} 项；完整清单保留在判定结果中。</small> : null}</div> : <p>同 release 工程证据合同已闭合；真实恢复、灾备 ready 与发布仍由独立门裁决。</p>}
    <footer>检查备份、恢复、重建数据视图、修改租户隔离、外部协调、故障切换与回切：全部禁用 · 无数据操作 · 无外部副作用 · 无发布</footer>
  </section>;
}
