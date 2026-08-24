import { useEffect, useRef, useState } from "react";

import { listAsyncJobs, type AsyncJobItem, type AsyncJobProjection } from "../../api/aipAsyncJobs";

export type AsyncJobLoader = () => Promise<AsyncJobProjection>;
type Phase = "loading" | "ready" | "failed";

const AUTHORITY_LABELS = {
  research_job: "研究任务",
  query_job: "查询任务",
  knowledge_pipeline_run: "知识流水线",
} as const;

function short(value: string) { return value.length > 24 ? `${value.slice(0, 12)}…${value.slice(-8)}` : value; }

function JobDetail({ job }: { job: AsyncJobItem }) {
  const controls = [
    ["取消", job.permissions.canCancel],
    ["重试", job.permissions.canRetry],
    ["对账", job.permissions.canReconcile],
  ] as const;
  return <article className="async-job-detail" aria-label="异步任务证据详情">
    <header><div><small>{AUTHORITY_LABELS[job.jobRef.authorityType]}</small><h3 title={job.jobRef.jobId}>{short(job.jobRef.jobId)}</h3></div><strong className={`is-${job.displayStatus}`}>{job.displayStatus}</strong></header>
    <dl><div><dt>原始状态</dt><dd>{job.status}</dd></div><div><dt>进度</dt><dd>{job.progress.state}{job.progress.totalUnits === null ? "" : ` · ${job.progress.completedUnits ?? 0}/${job.progress.totalUnits}`}</dd></div><div><dt>authority</dt><dd>{job.jobRef.authority}</dd></div><div><dt>负责人</dt><dd>{job.owner ?? "unknown"}</dd></div><div><dt>checkpoint</dt><dd>{job.checkpointRef ? `${job.checkpointRef.resourceId}@${job.checkpointRef.revision}` : "无 exact checkpoint"}</dd></div><div><dt>Receipt</dt><dd>{job.receiptRefs.length}</dd></div><div><dt>部分产物</dt><dd>{job.partialRefs.length}</dd></div><div><dt>更新时间</dt><dd>{job.updatedAt ? new Date(job.updatedAt).toLocaleString("zh-CN", { hour12: false }) : "unknown"}</dd></div></dl>
    <section><h4>受控命令</h4><p>统一视图不复制命令状态机；按钮仅披露源 authority 返回的权限，本页不提交命令。</p><div className="async-job-controls">{controls.map(([label, allowed]) => <button type="button" disabled key={label} title={allowed ? "请前往对应 authority 执行并回读 Receipt" : "当前 authority 未授权"}>{label}<small>{allowed ? "authority 可用" : "失败关闭"}</small></button>)}</div></section>
    <section><h4>阻断与不确定性</h4>{job.blockedReasons.length ? <ul>{job.blockedReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : <p>当前无投影级 blocker；仍不等于外部执行或发布 GREEN。</p>}</section>
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
    <header><div><small>三 authority · 只读投影</small><h2>异步任务与研究进度</h2></div><button type="button" onClick={reload} disabled={phase === "loading"}>{phase === "loading" ? "读取中…" : "重新读取"}</button></header>
    <p>ResearchJob、QueryJob、KnowledgePipelineRun 保持独立；partial、unknown、checkpoint 与 Receipt 均按源事实展示。</p>
    {phase === "failed" ? <div className="async-job-state is-failed"><strong>读取失败关闭</strong><span>未自动重试、未创建任务、未触发 Provider。</span></div> : null}
    {phase === "ready" && projection?.count === 0 ? <div className="async-job-state"><strong>可信空集合</strong><span>当前租户没有可读取的异步任务。</span></div> : null}
    {projection?.items.length ? <div className="async-job-layout"><nav aria-label="异步任务列表">{projection.items.map((item) => <button type="button" key={`${item.jobRef.authorityType}:${item.jobRef.jobId}`} aria-current={item.jobRef.jobId === selected} onClick={() => setSelected(item.jobRef.jobId)}><span>{AUTHORITY_LABELS[item.jobRef.authorityType]}</span><strong title={item.jobRef.jobId}>{short(item.jobRef.jobId)}</strong><em>{item.displayStatus}</em></button>)}</nav>{job ? <JobDetail job={job} /> : null}</div> : null}
  </section>;
}
