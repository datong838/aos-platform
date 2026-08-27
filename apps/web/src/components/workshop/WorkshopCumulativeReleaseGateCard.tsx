import { CUMULATIVE_GATE_COLUMNS, evaluateWorkshopCumulativeReleaseGate, type CumulativeReleaseEvidence } from "./workshopCumulativeReleaseGate";

const LABELS: Record<(typeof CUMULATIVE_GATE_COLUMNS)[number], string> = {
  contract_schema: "Contract / Schema", unit_parser: "Unit / Parser", store_rls_cas_append_only: "Store / RLS / CAS", service_integration: "Service / Integration",
  openapi: "OpenAPI", alembic: "Alembic", bundle_resolver_installation_eval: "Bundle / Eval", web_typecheck_build: "Web / Build",
  browser_a11y: "Browser / A11y", security_supply_chain: "Security / Supply-chain", fault_restart_race_reconcile: "Fault / Reconcile",
  operational_slo_runbook_dr: "SLO / Runbook / DR", diff_generated_honesty: "Diff / Honesty", receipts_exact_readback: "Receipt Readback",
};

export function WorkshopCumulativeReleaseGateCard({ evidence = {} }: { evidence?: CumulativeReleaseEvidence }) {
  const result = evaluateWorkshopCumulativeReleaseGate(evidence);
  const cell = { display: "grid", gap: 4, minWidth: 0, padding: 10, border: "1px solid var(--aos-border)", background: "var(--aos-surface)" } as const;
  return <section className={`workshop-cumulative-release-gate is-${result.status}`} aria-label="累计发布安全检查" data-testid="workshop-cumulative-release-gate" style={{ display: "grid", gap: 12, padding: 16, border: "1px solid var(--aos-border)", borderLeft: "4px solid var(--aos-red-600, #dc2626)", background: "color-mix(in srgb, var(--aos-surface) 96%, #fff7ed)" }}>
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}><div style={{ display: "grid", gap: 4 }}><span style={{ color: "var(--aos-text-tertiary)", fontSize: 11, letterSpacing: ".08em" }}>发布安全检查 · 只读</span><h2 style={{ margin: 0 }}>接口、数据变更、安装包、安全与差异检查</h2></div><strong>{result.status === "ready" ? "证据已闭合" : "等待发布证据"}</strong></header>
    <p>只复算同 Git/build、AOS revision、Bundle/Installation 与 tenant cutoff 的 EvidencePack；历史通过数不跨提交相加。</p>
    <div aria-label="累计门贡献分层" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 8 }}>
      <div style={cell}><span>原子技能</span><strong>{result.identityState === "exact" ? "精确证据" : "待核对"}</strong><small>测试、数据结构、评价与安全原子证据</small></div>
      <div style={cell}><span>逻辑编排</span><strong>{result.gatesPassed} / 14</strong><small>同版十四栏安全聚合</small></div>
      <div style={cell}><span>数字同事绑定</span><strong>{result.modulesVerified} / 8</strong><small>八 Module exact refs；不推断 runnable</small></div>
      <div style={cell}><span>工作台贡献</span><strong>{result.blockerCodes.length}</strong><small>独立阻断项</small></div>
    </div>
    <div aria-label="累计门十四栏" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 8 }}>{CUMULATIVE_GATE_COLUMNS.map((column) => <div style={cell} key={column}><span>{LABELS[column]}</span><strong>{evidence.gates?.find((gate) => gate.column === column)?.status ?? "unknown"}</strong></div>)}</div>
    <div aria-label="累计门权威状态" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 8 }}>
      <div style={cell}><span>Release identity</span><strong>{result.identityState === "exact" ? "exact" : "未知（不以历史值代替）"}</strong></div>
      <div style={cell}><span>Tenant negatives</span><strong>{result.tenantState === "isolated" ? "同 cutoff 闭合" : "未知（不以 0 代替）"}</strong></div>
      <div style={cell}><span>Receipt readback</span><strong>{result.receiptState === "exact" ? "exact" : "未知（不以 0 代替）"}</strong></div>
    </div>
    {result.blockerCodes.length ? <div><strong>当前缺失条件</strong><ul>{result.blockerCodes.slice(0, 8).map((code) => <li key={code}>{code}</li>)}</ul>{result.blockerCodes.length > 8 ? <small>另有 {result.blockerCodes.length - 8} 项；完整清单保留在判定结果中。</small> : null}</div> : <p>同版工程证据已闭合；运营就绪与发布仍由独立发布决定裁决。</p>}
    <footer>运行测试、生成接口契约、应用数据变更、安装模块、修复安全问题、修改生成物与发布：全部禁用 · 无数据变更 · 无外部副作用 · 无发布</footer>
  </section>;
}
