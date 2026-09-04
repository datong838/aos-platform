import { useEffect, useRef, useState } from "react";

import {
  EcommerceWorkshopClientError,
  ecommerceWorkshopClient,
  type ContentCampaignItem,
  type ContentCampaignSlice,
  type ContentCampaignSliceId,
  type ContentCampaignViewResponse,
  type ContentCampaignWorkflowCommand,
  type ContentCampaignWorkflowCommandResponse,
} from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { ContributionLineage } from "./production";
import { deriveWorkshopViewState, pickPreferredWorkshopView } from "./workshopViewState";

type Client = Pick<typeof ecommerceWorkshopClient, "getContentCampaignView" | "executeContentCampaignWorkflow" | "previewContentCampaignApproval">;
type Phase = AsyncState;

const LABELS: Record<ContentCampaignSliceId, string> = {
  plan: "活动计划",
  calendar: "内容日历",
  content: "主内容与变体",
};
const TAB_LABELS: Record<ContentCampaignSliceId, string> = {
  plan: "活动策划",
  calendar: "内容日历",
  content: "日常模板",
};
const DESCRIPTIONS: Record<ContentCampaignSliceId, string> = {
  plan: "活动目标与节奏",
  calendar: "日期、渠道与负责人",
  content: "主内容与渠道版本",
};
const CONTRIBUTIONS: Record<ContentCampaignSliceId, string> = {
  plan: "以正式活动计划作为内容与活动规划依据",
  calendar: "呈现活动排期意图，不代表已经发布",
  content: "按主内容与渠道版本展示内容关系",
};
const ASSISTANT_HINTS = ["读取正式活动计划", "核对内容日历", "关联主内容与渠道版本"];
const stateFor = (phase: Phase): AsyncState => phase;
const formatTime = (value: string) => new Date(value).toLocaleString("zh-CN", { hour12: false });
const short = (value: string) => value.length > 34 ? `${value.slice(0, 15)}…${value.slice(-12)}` : value;

function ItemCard({ item }: { item: ContentCampaignItem }) {
  const variant = "intentRef" in item;
  return (
    <article className={`content-campaign-item${variant ? " is-variant" : ""}`}>
      <header><strong>正式活动数据</strong><span>第 {item.revision} 版</span></header>
      <p>该业务记录已通过当前租户的数据边界校验。</p>
      <details>
        <summary>查看数据审计信息</summary>
        <dl>
          <div><dt>数据类型</dt><dd>{item.resourceType}</dd></div>
          <div><dt>数据编号</dt><dd title={item.resourceId}>{item.resourceId}</dd></div>
          <div><dt>内容校验</dt><dd title={item.contentHash}>{short(item.contentHash)}</dd></div>
          <div><dt>读取凭证</dt><dd title={item.receiptId}>{short(item.receiptId)}</dd></div>
          {variant ? <>
            <div><dt>归因路径</dt><dd>{item.relationType} · {item.relationId}</dd></div>
            <div><dt>主内容与渠道版本</dt><dd>{short(item.masterArtifactRef.artifactId)} → {short(item.variantArtifactRef.artifactId)}</dd></div>
          </> : null}
        </dl>
      </details>
    </article>
  );
}

export function ContentCampaignPage({ client = ecommerceWorkshopClient }: { client?: Client }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [response, setResponse] = useState<ContentCampaignViewResponse | null>(null);
  const [selected, setSelected] = useState<ContentCampaignSliceId>("plan");
  const [safeAction, setSafeAction] = useState("");
  const [intent, setIntent] = useState("");
  const [workflow, setWorkflow] = useState<ContentCampaignWorkflowCommandResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const request = useRef(0);

  const load = () => {
    const id = ++request.current;
    setPhase("loading");
    setResponse(null);
    void client.getContentCampaignView().then((next) => {
      if (id !== request.current) return;
      setResponse(next);
      setSelected(pickPreferredWorkshopView(next.slices, (item) => item.items.length > 0)?.sliceId ?? "plan");
      setPhase(deriveWorkshopViewState(next.slices, next.page.count));
    }, (error: unknown) => {
      if (id === request.current) {
        setPhase(error instanceof EcommerceWorkshopClientError && (error.status === 401 || error.status === 403) ? "forbidden" : "failed");
      }
    });
  };

  useEffect(() => {
    load();
    return () => { request.current += 1; };
  }, [client]);

  const slice: ContentCampaignSlice | undefined = response?.slices.find((item) => item.sliceId === selected);
  const ready = response?.slices.filter((item) => item.status === "ready").length ?? 0;
  const eligible = response?.slices.reduce((sum, item) => sum + item.countLedger.eligible, 0) ?? 0;
  const unmatched = response?.slices.reduce((sum, item) => sum + item.countLedger.unmatched + item.countLedger.conflicted, 0) ?? 0;
  const runWorkflow = async (command: ContentCampaignWorkflowCommand) => {
    if (intent.trim().length < 4) { setSafeAction("请先填写至少四个字的活动目标，再继续生成或保存。"); return; }
    if (command !== "generate" && !workflow) { setSafeAction("请先生成活动方案草稿，再保存或重新生成。"); return; }
    setBusy(true);
    try {
      const next = await client.executeContentCampaignWorkflow({
        command, objective: intent.trim(), channels: ["微信小店"],
        ...(workflow ? { draftRef: { resourceType: "TaskBriefRevision", resourceId: workflow.draft.resourceId, revision: workflow.draft.revision, contentHash: workflow.draft.contentHash }, expectedVersion: workflow.draft.version } : {}),
      }, `content-campaign-${command}-${Date.now()}`);
      setWorkflow(next);
      setSafeAction(`${next.message} 当前第 ${next.draft.version} 版，业务回执 ${next.receipt.receiptId}。`);
    } catch (error) {
      setSafeAction(error instanceof Error ? `操作未完成：${error.message}` : "操作未完成，请重新读取后再试。");
    } finally { setBusy(false); }
  };
  const previewApproval = async () => {
    if (!workflow) { setSafeAction("请先生成并保存活动方案草稿，再执行审批前检查。"); return; }
    setBusy(true);
    try {
      const preview = await client.previewContentCampaignApproval({ resourceType: "TaskBriefRevision", resourceId: workflow.draft.resourceId, revision: workflow.draft.revision, contentHash: workflow.draft.contentHash });
      setSafeAction(preview.approvalAllowed ? `审批前检查通过：${preview.nextActions.join("；")}` : `审批前检查已完成：${preview.nextActions.join("；")}`);
    } catch (error) { setSafeAction(error instanceof Error ? `审批前检查未完成：${error.message}` : "审批前检查未完成。"); }
    finally { setBusy(false); }
  };

  const content = response && slice ? (
    <div className="content-campaign-read-model">
      <div className="content-campaign-board">
        <aside className="content-campaign-nav content-campaign-list-lane" aria-label="活动列表">
          <header><h2>活动列表</h2><button type="button" onClick={() => setSafeAction("筛选已切换为当前数据范围；未改变业务记录。")}>筛选</button></header>
          <div className="content-campaign-list-group"><strong>当前数据范围</strong><span>{ready} 个视图可读取</span></div>
          {workflow ? <button type="button" className="content-campaign-draft is-selected" onClick={() => setIntent(workflow.draft.objective)}><strong>{workflow.task.title}</strong><small>内部活动草稿 · 第 {workflow.draft.version} 版</small><span>回执可追溯</span></button> : null}
          {response.slices.map((item) => (
            <button
              type="button"
              key={item.sliceId}
              className={`content-campaign-slice is-${item.status}${item.sliceId === slice.sliceId ? " is-selected" : ""}`}
              aria-pressed={item.sliceId === slice.sliceId}
              onClick={() => setSelected(item.sliceId)}
            >
              <strong>{LABELS[item.sliceId]}</strong>
              <small>{DESCRIPTIONS[item.sliceId]}</small>
              <span>{item.status === "ready" ? "可读取" : "需要补充正式数据"} · {item.countLedger.attached}/{item.countLedger.eligible}</span>
            </button>
          ))}
          <div className="content-campaign-list-help">
            <strong>没有活动记录？</strong>
            <p>填写中央活动目标即可生成内部草稿；对外发布仍需独立审批。</p>
          </div>
        </aside>

        <section className="content-campaign-detail content-campaign-planning-lane" aria-label="内容与活动详情">
          <section className="content-campaign-visual-intent">
            <div><strong>AI 策划助手</strong><span>仅消费当前正式业务数据</span></div>
            <div>
              <textarea aria-label="活动意图" value={intent} onChange={(event) => setIntent(event.target.value)} placeholder="描述活动目标、周期与约束，系统会先执行安全预检…" />
              <button type="button" disabled={busy} onClick={() => void runWorkflow(workflow ? "regenerate" : "generate")}>{busy ? "处理中…" : "生成方案"}</button>
            </div>
            <div className="content-campaign-hints" aria-label="策划建议">
              <span>基于当前数据：</span>
              {ASSISTANT_HINTS.map((hint) => <button type="button" key={hint} onClick={() => setIntent(hint)}>{hint}</button>)}
            </div>
          </section>

          <div className="content-campaign-center-scroll">
            <section className={`content-campaign-assistant-summary is-${slice.status}`} aria-label="AI 策划结论">
              <div>
                <strong>{slice.status === "ready" ? "当前正式数据可供审阅" : "尚未形成可审阅方案"}</strong>
                <span>{slice.status === "ready" ? "只读呈现正式业务事实，不代表已批准或发布。" : "正式数据来源未闭合，助手不生成活动、预算、经营指标或风险建议。"}</span>
              </div>
              <em>{slice.status === "ready" ? "只读" : "等待数据"}</em>
            </section>

            <section className="content-campaign-overview" aria-label="活动概览">
              <header>
                <div><span>当前业务视图</span><h2>活动概览</h2></div>
                <strong className={`content-campaign-status is-${slice.status}`}>{slice.status === "ready" ? "正式数据可读" : "等待正式数据"}</strong>
              </header>
              <p className="content-campaign-overview-title"><strong>{LABELS[slice.sliceId]}</strong><span>{slice.status === "ready" ? "正式业务数据已挂接" : "等待正式业务数据"}</span></p>
              <section className="content-campaign-ledger" aria-label="当前业务数量">
                <div><span>可评估</span><strong>{slice.countLedger.eligible}</strong></div>
                <div><span>已挂接</span><strong>{slice.countLedger.attached}</strong></div>
                <div><span>未匹配</span><strong>{slice.countLedger.unmatched}</strong></div>
                <div><span>冲突</span><strong>{slice.countLedger.conflicted}</strong></div>
              </section>
              <section className="content-campaign-items" aria-label={`${LABELS[slice.sliceId]}正式数据`}>
                {slice.items.length ? slice.items.map((item) => <ItemCard item={item} key={`${item.resourceType}:${item.resourceId}:${item.revision}`} />) : (
                  <p><strong>当前没有可展示的{LABELS[slice.sliceId]}</strong><span>页面不会用演示活动填充；请补充正式业务数据后重新读取。</span></p>
                )}
              </section>
            </section>
          </div>

          <footer className="content-campaign-actionbar" aria-label="活动审批操作">
            <div><strong>{workflow ? `内部草稿第 ${workflow.draft.version} 版` : "可创建内部草稿"}</strong><span>草稿操作形成版本与业务回执；对外发布仍需独立审批。</span></div>
            <div>
              <button type="button" disabled={busy} onClick={() => void runWorkflow(workflow ? "save" : "generate")}>保存为草稿</button>
              <button type="button" disabled={busy} onClick={() => void runWorkflow(workflow ? "regenerate" : "generate")}>重新生成</button>
              <button type="button" disabled={busy} onClick={() => void previewApproval()}>批准并发布</button>
            </div>
          </footer>
        </section>

        <aside className="content-campaign-evidence content-campaign-collaboration-lane" aria-label="AI 协作与风险">
          <header><div><h2>AI 策划助手</h2><span>基于正式数据实时核对</span></div><strong>{slice.status === "ready" ? "可审阅" : "等待数据"}</strong></header>
          <section className="content-campaign-collaboration-summary">
            <strong>{slice.status === "ready" ? `${LABELS[slice.sliceId]}已读取` : "当前没有可生成的活动方案"}</strong>
            <p>{slice.status === "ready" ? "已完成数量与来源核对；需要人工审阅后才能进入后续内部流程。" : "正式来源尚未闭合，AI 不会补造商品、预算、档期或效果数字。"}</p>
          </section>

          <section className="content-campaign-risk-list" aria-label="风险决策">
            <header><h3>风险决策</h3><span>需要人工确认</span></header>
            <article>
              <strong>当前无可验证风险决策</strong>
              <p>折扣、库存与发布风险需要 canonical 风险版本；本页目前仅保留可工作的预检入口。</p>
              <button type="button" onClick={() => setSafeAction("风险决策预检：尚无可验证风险版本，未采纳建议或修改方案。")}>检查风险条件</button>
            </article>
          </section>

          <section className="content-campaign-evidence-summary">
            <header><h3>证据链 · 边界</h3><span>{slice.blockers.length} 项待补条件</span></header>
            {slice.blockers.length ? <ul>{slice.blockers.map((blocker) => (
              <li key={blocker.code}>
                <strong>补充同一数据截止面的正式业务数据</strong><span>当前执行失败关闭</span>
                <details><summary>查看数据审计信息</summary><p>{blocker.requiredAction}</p><p>{blocker.dependency}</p><code>{blocker.code}</code></details>
              </li>
            ))}</ul> : <div className="content-campaign-evidence-clear"><strong>{slice.items.length ? "当前读取链闭合" : "可信空集合"}</strong><p>只证明当前数据截止面的正式读取结果，不授权内容生产、排期或发布。</p></div>}
          </section>

          <details className="content-campaign-audit-context">
            <summary>专业贡献与数据审计</summary>
            <section><h3>专业贡献归因</h3><ContributionLineage value={{ atomicSkillRef: null, logicRef: null, coworker: null, workshopContribution: CONTRIBUTIONS[slice.sliceId] }} /><p>当前视图没有可验证的数字同事运行记录，因此不制造运行事实。</p></section>
            <p className="content-campaign-audit-compat">原子 Skill · Logic 编排 · Master → Variant</p>
            <section className="content-campaign-metrics" aria-label="内容活动数量守恒">
              <div><span>权威切片</span><strong>3</strong><small>固定 canonical order</small></div>
              <div><span>读取可用</span><strong>{ready}</strong><small>其余失败关闭</small></div>
              <div><span>可评估</span><strong>{eligible}</strong><small>非示例业务数</small></div>
              <div><span>已挂接</span><strong>{response.page.count}</strong><small>等于三切片 items</small></div>
              <div><span>待核对</span><strong>{unmatched}</strong><small>未匹配 + 冲突</small></div>
              <div><span>数据截止</span><strong>{formatTime(response.dataCutoff)}</strong><small>统一 cutoff</small></div>
            </section>
            <section className="content-campaign-readonly"><div><h2>内容与活动 · 权威数据与内部草稿</h2><p>正式数据保持只读；内部活动草稿可创建和修订，对外发布仍需独立审批。</p></div><strong>内部草稿可写</strong></section>
          </details>

          <footer className="content-campaign-footnote"><span>租户 {response.tenant.orgId}/{response.tenant.projectId}</span><span>评估 {formatTime(response.evaluatedAt)}</span><span>无后续页：是</span><button type="button" onClick={load}>重新读取</button></footer>
        </aside>
      </div>
    </div>
  ) : null;

  return (
    <section className="content-campaign-page" aria-label="内容与活动工作台">
      <nav className="content-campaign-toolbar" aria-label="内容与活动主视图">
        <div role="tablist">
          {(["plan", "calendar", "content"] as const).map((sliceId) => (
            <button type="button" role="tab" aria-selected={selected === sliceId} className={selected === sliceId ? "is-active" : ""} key={sliceId} onClick={() => setSelected(sliceId)}>{TAB_LABELS[sliceId]}</button>
          ))}
        </div>
        <span>栖月汇微商城</span>
        <button type="button" title="新建内部活动草稿" onClick={() => { setIntent(""); setWorkflow(null); setSafeAction("已打开新的活动方案输入区，请填写正式经营目标。"); }}>＋ 新建活动</button>
      </nav>
      {safeAction ? <div className="content-campaign-safe-action" role="status"><span>{safeAction}</span><button type="button" aria-label="关闭操作提示" onClick={() => setSafeAction("")}>×</button></div> : null}
      <AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.dataCutoff} action={phase === "failed" ? <button type="button" onClick={load}>重新读取</button> : undefined}>{content}</AsyncStateBoundary>
    </section>
  );
}
