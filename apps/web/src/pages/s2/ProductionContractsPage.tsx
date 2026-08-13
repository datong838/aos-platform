import { useCallback, useEffect, useState } from "react";
import {
  aipProductionContracts,
  type ContractBlocker,
  type EvalContractListResponse,
  type EvidenceBundleListResponse,
  type ResponsibilityPlanListResponse,
  type TaskBriefListResponse,
} from "../../api/aipProductionContracts";
import { PageChrome } from "../../components/PageChrome";

type AuthorityState = {
  briefs: TaskBriefListResponse;
  bundles: EvidenceBundleListResponse;
  evals: EvalContractListResponse;
  plans: ResponsibilityPlanListResponse;
};

const grid = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 16 } as const;
const itemStyle = { padding: "14px 0", borderTop: "1px solid var(--aos-border)" } as const;
const label: Record<string, string> = { ready: "就绪", blocked: "阻断", stale: "过期", unknown: "未知", draft: "草稿", frozen: "已冻结", complete: "完整", partial: "部分" };

function Blockers({ items }: { items: ContractBlocker[] }) {
  if (!items.length) return null;
  return <ul aria-label="阻断原因" style={{ margin: "8px 0 0", paddingLeft: 20 }}>{items.map(item => <li key={`${item.code}:${item.message}`}><code>{item.code}</code> · {item.message}</li>)}</ul>;
}

export function ProductionContractsPage() {
  const [state, setState] = useState<AuthorityState | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [briefs, bundles, evals, plans] = await Promise.all([
        aipProductionContracts.listBriefs(), aipProductionContracts.listBundles(),
        aipProductionContracts.listEvalContracts(), aipProductionContracts.listResponsibilityPlans(),
      ]);
      setState({ briefs, bundles, evals, plans });
      setError("");
    } catch (e) {
      setState(null);
      setError(String((e as Error).message || e));
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function run(id: string, action: () => Promise<unknown>) {
    setBusy(id);
    try { await action(); await load(); }
    catch (e) { setError(String((e as Error).message || e)); }
    finally { setBusy(""); }
  }
  const freezeBrief = (id: string, version: number) => run(`brief:${id}`, () => aipProductionContracts.freezeBrief(id, version, `w2-ui-brief-freeze-${crypto.randomUUID()}`));
  const freezeEval = (id: string, version: number) => run(`eval:${id}`, () => aipProductionContracts.freezeEvalContract(id, version, `w2-ui-eval-freeze-${crypto.randomUUID()}`));
  const freezePlan = (id: string, version: number) => run(`plan:${id}`, () => aipProductionContracts.freezeResponsibilityPlan(id, version, `w2-ui-plan-freeze-${crypto.randomUUID()}`));

  return <PageChrome title="生产契约" lede="Task Brief、Evidence Bundle、Eval Contract 与 Responsibility Plan 的租户权威视图；冻结不等于启动运行">
    {error && <div role="alert" className="notice bad">生产契约读取或操作失败：{error}</div>}
    {loading ? <div role="status" className="card">正在读取 PostgreSQL Production Contract authority…</div> : null}
    {!loading && state ? <>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16, flexWrap: "wrap" }}>
        <strong>{state.briefs.count} Brief</strong><span>{state.bundles.count} Evidence</span><span>{state.evals.count} Eval</span><span>{state.plans.count} Responsibility</span>
        <button className="btn" onClick={() => void load()}>刷新权威状态</button>
        <button className="btn primary" disabled title="必须从真实 Task 与权威依赖创建；本页不生成样例或隐式权威">创建契约（需真实依赖）</button>
      </div>
      <section style={grid}>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>Task Brief</h2>
          {state.briefs.count === 0 ? <div className="notice">当前组织尚无 Brief。请从真实 Task 进入创建流程；本页不生成 Mock Task。</div> : state.briefs.items.map(item => <article key={item.briefId} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{item.briefType}</strong><span>{label[item.lifecycle] ?? item.lifecycle}</span></div><p><code>{item.briefId}@{item.revision}</code> · Task <code>{item.taskId}</code></p><small>version {item.version} · hash {item.contentHash.slice(0, 12)}…</small>{item.lifecycle === "draft" ? <button className="btn" disabled={busy === `brief:${item.briefId}`} onClick={() => void freezeBrief(item.briefId, item.version)} style={{ marginTop: 10 }}>{busy === `brief:${item.briefId}` ? "冻结中…" : "冻结当前 revision"}</button> : null}</article>)}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>Evidence Bundle</h2>
          {state.bundles.count === 0 ? <div className="notice">当前组织尚无 Bundle。Bundle 只能聚合已授权 Evidence exact ref，不能复制正文或用摘要冒充事实。</div> : state.bundles.items.map(item => <article key={`${item.bundleId}@${item.revision}`} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between" }}><strong>{item.bundleId}</strong><span>{item.freshness}</span></div><p>{item.itemRefs.length} 条 Evidence · 覆盖 {label[item.coverage] ?? item.coverage}</p><small>Brief {item.briefRef.resourceId}@{item.briefRef.revision}</small></article>)}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>Eval Contract</h2>
          {state.evals.count === 0 ? <div className="notice">当前组织尚无 Eval Contract。必须绑定真实 EvalSuite、PublicationEvent 与 ReleaseGateDecision 后才能就绪。</div> : state.evals.items.map(item => { const canFreeze = item.lifecycle === "draft" && item.readiness === "ready" && item.blockers.length === 0; return <article key={item.contractId} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{item.contractId}@{item.revision}</strong><span>{label[item.readiness] ?? item.readiness}</span></div><p>EvalSuite <code>{item.suiteRef.resourceId}@{item.suiteRef.revision}</code></p><small>{label[item.lifecycle] ?? item.lifecycle} · version {item.version} · {Object.keys(item.severityThresholds).length} 个阈值</small><Blockers items={item.blockers} />{item.lifecycle === "draft" ? <button className="btn" disabled={!canFreeze || busy === `eval:${item.contractId}`} title={canFreeze ? "冻结当前就绪 revision" : "存在阻断或状态未就绪，禁止冻结"} onClick={() => void freezeEval(item.contractId, item.version)} style={{ marginTop: 10 }}>{busy === `eval:${item.contractId}` ? "冻结中…" : "冻结 Eval"}</button> : null}</article>; })}
        </div>
        <div className="card" style={{ padding: 18 }}><h2 style={{ marginTop: 0 }}>Responsibility Plan</h2>
          {state.plans.count === 0 ? <div className="notice bad">当前组织尚无 Responsibility Plan。ResponsibilityTemplateRevision 权威未接入前保持 fail-closed，不用本地清单伪造职责覆盖。</div> : state.plans.items.map(item => { const canFreeze = item.lifecycle === "draft" && item.readiness === "ready" && item.coverage === "complete" && item.blockers.length === 0; return <article key={item.planId} style={itemStyle}><div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{item.profile}</strong><span>{label[item.readiness] ?? item.readiness}</span></div><p>{item.slots.length} 个职责槽 · 覆盖 {label[item.coverage] ?? item.coverage}</p>{item.uncoveredSlots.length ? <p>未覆盖：{item.uncoveredSlots.join("、")}</p> : null}<small>Template {item.templateRef.resourceId}@{item.templateRef.revision} · version {item.version}</small><Blockers items={item.blockers} />{item.lifecycle === "draft" ? <button className="btn" disabled={!canFreeze || busy === `plan:${item.planId}`} title={canFreeze ? "冻结完整且就绪的职责计划" : "职责覆盖不完整、存在阻断或状态未就绪"} onClick={() => void freezePlan(item.planId, item.version)} style={{ marginTop: 10 }}>{busy === `plan:${item.planId}` ? "冻结中…" : "冻结职责计划"}</button> : null}</article>; })}
        </div>
      </section>
      <div className="notice" style={{ marginTop: 16 }}>运行门保持阻断：四类 Production Contract authority 齐备且冻结，仍不等于 AgentRun 可启动；Stage、AIP-7 Route / Provider / Binding 与后续运行门必须独立通过。</div>
    </> : null}
  </PageChrome>;
}
