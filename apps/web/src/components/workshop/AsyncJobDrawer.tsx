import { useEffect, useRef, useState } from "react";

import { listAsyncJobs, type AsyncJobItem, type AsyncJobProjection } from "../../api/aipAsyncJobs";

export type AsyncJobLoader = () => Promise<AsyncJobProjection>;
type Phase = "loading" | "ready" | "failed";

const AUTHORITY_LABELS = {
  research_job: "研究任务",
  query_job: "查询任务",
  knowledge_pipeline_run: "知识流水线",
} as const;

const STATUS_LABELS: Record<string, string> = {
  queued: "等待开始",
  pending: "等待处理",
  running: "进行中",
  succeeded: "已完成",
  completed: "已完成",
  partial: "部分完成",
  failed: "处理失败",
  cancelled: "已取消",
  blocked: "等待业务条件",
  unknown: "待核对",
};

const statusLabel = (value: string) => STATUS_LABELS[value] ?? "待核对";

function JobDetail({ job }: { job: AsyncJobItem }) {
  const controls = [
    ["取消", job.permissions.canCancel],
    ["重试", job.permissions.canRetry],
    ["对账", job.permissions.canReconcile],
  ] as const;
  return <article className="async-job-detail" aria-label="异步任务证据详情">
    <header><div><small>{AUTHORITY_LABELS[job.jobRef.authorityType]}</small><h3>{job.owner ? `${job.owner} 的业务任务` : "未分配业务任务"}</h3></div><strong className={`is-${job.displayStatus}`}>{statusLabel(job.displayStatus)}</strong></header>
    <dl><div><dt>任务状态</dt><dd>{statusLabel(job.status)}</dd></div><div><dt>业务进度</dt><dd>{statusLabel(job.progress.state)}{job.progress.totalUnits === null ? "" : ` · ${job.progress.completedUnits ?? 0}/${job.progress.totalUnits}`}</dd></div><div><dt>负责人</dt><dd>{job.owner ?? "待分配"}</dd></div><div><dt>处理结果</dt><dd>{job.receiptRefs.length ? "已有正式回读结果" : "尚无正式结果"}</dd></div><div><dt>阶段产物</dt><dd>{job.partialRefs.length}</dd></div><div><dt>更新时间</dt><dd>{job.updatedAt ? new Date(job.updatedAt).toLocaleString("zh-CN", { hour12: false }) : "待核对"}</dd></div></dl>
    <details><summary>查看任务审计信息</summary><dl><div><dt>任务编号</dt><dd>{job.jobRef.jobId}</dd></div><div><dt>原始状态</dt><dd>{job.status}</dd></div><div><dt>数据权威</dt><dd>{job.jobRef.authority}</dd></div><div><dt>进度断点</dt><dd>{job.checkpointRef ? `${job.checkpointRef.resourceId}@${job.checkpointRef.revision}` : "无精确断点"}</dd></div><div><dt>回读凭证</dt><dd>{job.receiptRefs.length}</dd></div></dl></details>
    <section><h4>可用操作</h4><p>当前页面只展示业务进度；需要变更任务时，应在对应业务流程完成确认。</p><div className="async-job-controls">{controls.map(([label, allowed]) => <button type="button" disabled key={label} title={allowed ? "请前往对应业务流程确认" : "当前不可操作"}>{label}<small>{allowed ? "需业务确认" : "当前不可用"}</small></button>)}</div></section>
    <section><h4>待补条件</h4>{job.blockedReasons.length ? <ul>{job.blockedReasons.map((reason) => <li key={reason}>需要补充正式业务数据</li>)}</ul> : <p>当前没有待补条件。</p>}<details><summary>查看原始原因</summary>{job.blockedReasons.length ? <ul>{job.blockedReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : <p>无</p>}</details></section>
  </article>;
}

export function AsyncJobDrawer({ load = listAsyncJobs }: { load?: AsyncJobLoader }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [projection, setProjection] = useState<AsyncJobProjection | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const request = useRef(0);
  const reload = () => {
    const id = ++request.current; setPhase("loading");
    void load().then((next) => { if (id !== request.current) return; setProjection(next); setSelected((current) => next.items.some((item) => item.jobRef.jobId === current) ? current : next.items[0]?.jobRef.jobId ?? null); setPhase("ready"); }, () => { if (id === request.current) { setProjection(null); setSelected(null); setPhase("failed"); } });
  };
  useEffect(() => { reload(); return () => { request.current += 1; }; }, [load]);
  const job = projection?.items.find((item) => item.jobRef.jobId === selected) ?? null;
  return <section className="async-job-drawer" aria-label="统一异步任务抽屉">
    <header><div><small>经营研究 · 只读</small><h2>研究任务与业务进度</h2></div><button type="button" onClick={reload} disabled={phase === "loading"}>{phase === "loading" ? "读取中…" : "重新读取"}</button></header>
    <p>研究、查询与知识整理任务分别展示；阶段结果、待核对状态和正式回读结果均以当前租户数据为准。</p>
    {phase === "failed" ? <div className="async-job-state is-failed"><strong>读取失败关闭</strong><span>未自动重试、未创建任务、未触发 Provider。</span></div> : null}
    {phase === "ready" && projection?.count === 0 ? <div className="async-job-state"><strong>可信空集合</strong><span>当前租户没有可读取的异步任务。</span></div> : null}
    {projection?.items.length ? <div className="async-job-layout"><nav aria-label="异步任务列表">{projection.items.map((item) => <button type="button" key={`${item.jobRef.authorityType}:${item.jobRef.jobId}`} aria-current={item.jobRef.jobId === selected} onClick={() => setSelected(item.jobRef.jobId)}><span>{AUTHORITY_LABELS[item.jobRef.authorityType]}</span><strong>{item.owner ? `${item.owner} 的业务任务` : "未分配业务任务"}</strong><em>{statusLabel(item.displayStatus)}</em></button>)}</nav>{job ? <JobDetail job={job} /> : null}</div> : null}
  </section>;
}
