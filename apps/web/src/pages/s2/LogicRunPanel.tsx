import type { ReactNode } from "react";

import type {
  JsonValue,
  LogicDryRun,
  LogicNodeResult,
  LogicNodeRunStatus,
  LogicProposedEdit,
  LogicRunStatus as CanonicalLogicRunStatus,
  LogicRunSummary,
} from "./logicRunContracts";
import "./LogicRunPanel.css";

export type LogicRunStatus = CanonicalLogicRunStatus;
export type LogicRunNodeStatus = LogicNodeRunStatus;
export type LogicRunLoadState = "idle" | "loading" | "ready" | "error";
export type LogicRunNodeView = LogicNodeResult;
export type LogicRunView = LogicDryRun;
export type LogicRunSummaryView = LogicRunSummary;

export interface LogicRunPanelProps {
  run: LogicRunView | null;
  runState: LogicRunLoadState;
  runError?: string | null;
  history: readonly LogicRunSummaryView[];
  historyState: LogicRunLoadState;
  historyError?: string | null;
  selectedRunId?: string | null;
  hasMoreHistory?: boolean;
  loadingMoreHistory?: boolean;
  onSelectRun: (runId: string) => void;
  onLocateNode?: (nodeId: string) => void;
  onRetryRun?: () => void;
  onRetryHistory?: () => void;
  onLoadMoreHistory?: () => void;
}

const NODE_STATUS_LABELS: Record<LogicRunNodeStatus, string> = {
  executed: "已执行",
  skipped: "已跳过",
  failed: "失败",
  canceled: "已取消",
};

function Tokens({ value }: { value: number | null }) {
  return <span>{value === null ? "未提供" : value}</span>;
}

function StatusBadge({ status }: { status: LogicRunStatus | LogicRunNodeStatus }) {
  const label = status === "succeeded"
    ? "成功"
    : status === "failed"
      ? "失败"
      : NODE_STATUS_LABELS[status];
  return <span className={`logic-run-panel__status is-${status}`}>{label}</span>;
}

function JsonPreview({ value }: { value: JsonValue }) {
  return <pre className="logic-run-panel__json">{JSON.stringify(value, null, 2)}</pre>;
}

function ProposedEdits({ edits, title }: { edits: readonly LogicProposedEdit[]; title: string }) {
  if (edits.length === 0) return null;
  return (
    <details className="logic-run-panel__drilldown">
      <summary>{title}（{edits.length}）</summary>
      <ol>
        {edits.map((edit, index) => (
          <li key={`${edit.source_node_id}-${edit.object_id}-${edit.field}-${index}`}>
            <dl className="logic-run-panel__facts is-compact">
              <div><dt>动作</dt><dd>{edit.action}</dd></div>
              <div><dt>对象</dt><dd>{edit.object_id}</dd></div>
              <div><dt>字段</dt><dd>{edit.field}</dd></div>
              <div><dt>来源节点</dt><dd>{edit.source_node_id}</dd></div>
              <div><dt>应用状态</dt><dd><code>applied=false</code></dd></div>
            </dl>
            <JsonPreview value={edit.value} />
          </li>
        ))}
      </ol>
    </details>
  );
}

function ErrorState({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div className="logic-run-panel__error" role="alert">
      <strong>{title}</strong>
      <span>{message}</span>
      {action}
    </div>
  );
}

function NodeResult({
  node,
  onLocateNode,
}: {
  node: LogicNodeResult;
  onLocateNode?: (nodeId: string) => void;
}) {
  const canLocate = Boolean(onLocateNode && (node.status === "failed" || node.error));
  const proposedCount = node.proposed_edits.length;
  return (
    <li className={`logic-run-panel__node is-${node.status}`} data-node-id={node.node_id}>
      <div className="logic-run-panel__node-heading">
        <div>
          <StatusBadge status={node.status} />
          <strong>{node.node_id}</strong>
          <span className="logic-run-panel__kind">{node.kind}</span>
        </div>
        {canLocate && (
          <button
            type="button"
            className="logic-run-panel__link-button"
            aria-label={`定位节点 ${node.node_id}`}
            onClick={() => onLocateNode?.(node.node_id)}
          >
            定位到画布
          </button>
        )}
      </div>
      <p className="logic-run-panel__summary">{node.summary || "服务端未提供步骤摘要"}</p>
      <dl className="logic-run-panel__facts is-compact">
        <div><dt>耗时</dt><dd>{node.elapsed_ms === null ? "未提供" : `${node.elapsed_ms} ms`}</dd></div>
        <div><dt>Token</dt><dd><Tokens value={node.usage?.total_tokens ?? null} /></dd></div>
        {node.selected_branch_path && <div><dt>命中分支</dt><dd>{node.selected_branch_path}</dd></div>}
        {node.usage?.model && <div><dt>模型</dt><dd>{node.usage.model}</dd></div>}
        {node.error?.reason && <div><dt>机器原因</dt><dd>{node.error.reason}</dd></div>}
        {node.truncated && <div><dt>输出</dt><dd>已安全截断</dd></div>}
        {proposedCount > 0 && <div><dt>提议编辑</dt><dd>{proposedCount} 条</dd></div>}
      </dl>
      {node.error && node.status === "failed" && (
        <div className="logic-run-panel__node-error" role="alert">
          <code>{node.error.code}</code>
          <span>{node.error.message}</span>
        </div>
      )}
      {node.tool_call && (
        <details className="logic-run-panel__drilldown">
          <summary>安全工具调用</summary>
          <dl className="logic-run-panel__facts is-compact">
            <div><dt>工具</dt><dd>{node.tool_call.tool}</dd></div>
            <div><dt>适配器</dt><dd>{node.tool_call.adapter}</dd></div>
            <div><dt>只读</dt><dd><code>read_only=true</code></dd></div>
            <div><dt>Dry-Run 安全</dt><dd><code>dry_run_safe=true</code></dd></div>
          </dl>
        </details>
      )}
      <details className="logic-run-panel__drilldown">
        <summary>安全输出{node.truncated ? "（已截断）" : ""}</summary>
        {node.truncated && <p className="logic-run-panel__truncated" role="status">服务端已按安全上限截断输出。</p>}
        <JsonPreview value={node.output} />
      </details>
      <ProposedEdits edits={node.proposed_edits} title="节点提议编辑" />
    </li>
  );
}

function RunDetail({
  run,
  onLocateNode,
}: {
  run: LogicRunView;
  onLocateNode?: (nodeId: string) => void;
}) {
  const writeContractBroken = run.production_written !== false;
  if (writeContractBroken) {
    return (
      <section className="logic-run-panel__detail" aria-label="运行详情">
        <div className="logic-run-panel__detail-heading">
          <div>
            <span className="logic-run-panel__eyebrow">服务端运行证据</span>
            <h3>{run.run_id}</h3>
          </div>
          <StatusBadge status={run.status} />
        </div>
        <ErrorState title="拒绝展示为安全试跑" message="服务端返回的 production_written 不是 false。" />
      </section>
    );
  }
  return (
    <section className="logic-run-panel__detail" aria-label="运行详情">
      <div className="logic-run-panel__detail-heading">
        <div>
          <span className="logic-run-panel__eyebrow">服务端运行证据</span>
          <h3>{run.run_id}</h3>
        </div>
        <StatusBadge status={run.status} />
      </div>

      <div className="logic-run-panel__safety" role="status">
        不写生产 · <code>production_written=false</code>
      </div>

      <dl className="logic-run-panel__facts">
        <div><dt>模式</dt><dd><code>{run.mode}</code></dd></div>
        <div><dt>执行版本</dt><dd>revision {run.evaluated_revision}</dd></div>
        <div className="is-wide"><dt>Graph hash</dt><dd><code>{run.graph_hash}</code></dd></div>
        <div><dt>开始时间</dt><dd><time dateTime={run.started_at}>{run.started_at}</time></dd></div>
        <div><dt>完成时间</dt><dd><time dateTime={run.finished_at}>{run.finished_at}</time></dd></div>
        <div><dt>真实耗时</dt><dd>{run.elapsed_ms} ms</dd></div>
        <div><dt>总 Token</dt><dd><Tokens value={run.total_tokens} /></dd></div>
        <div><dt>提议编辑</dt><dd>{run.proposed_edits.length} 条</dd></div>
      </dl>

      {run.error && (
        <ErrorState
          title={run.error.code}
          message={run.error.message}
          action={run.error.node_id && onLocateNode ? (
            <button
              type="button"
              className="logic-run-panel__link-button"
              onClick={() => onLocateNode(run.error?.node_id as string)}
            >
              定位节点 {run.error.node_id}
            </button>
          ) : undefined}
        />
      )}

      <ProposedEdits edits={run.proposed_edits} title="运行级提议编辑" />

      <div className="logic-run-panel__nodes-heading">
        <h4>逐节点结果</h4>
        <span>{run.node_results.length} 个节点</span>
      </div>
      {run.node_results.length === 0 ? (
        <p className="logic-run-panel__empty">服务端未返回节点结果。</p>
      ) : (
        <ol className="logic-run-panel__nodes">
          {run.node_results.map((node) => (
            <NodeResult key={node.node_id} node={node} onLocateNode={onLocateNode} />
          ))}
        </ol>
      )}
    </section>
  );
}

function HistoryList({
  history,
  historyState,
  historyError,
  selectedRunId,
  hasMoreHistory,
  loadingMoreHistory,
  onSelectRun,
  onRetryHistory,
  onLoadMoreHistory,
}: Pick<LogicRunPanelProps,
  | "history"
  | "historyState"
  | "historyError"
  | "selectedRunId"
  | "hasMoreHistory"
  | "loadingMoreHistory"
  | "onSelectRun"
  | "onRetryHistory"
  | "onLoadMoreHistory"
>) {
  return (
    <aside className="logic-run-panel__history" aria-label="服务端运行历史">
      <div className="logic-run-panel__history-heading">
        <div>
          <span className="logic-run-panel__eyebrow">不可变记录</span>
          <h3>运行历史</h3>
        </div>
        {historyState === "loading" && <span role="status">读取中…</span>}
      </div>

      {historyState === "error" && (
        <ErrorState
          title="运行历史读取失败"
          message={historyError || "服务端未提供错误详情。"}
          action={onRetryHistory ? (
            <button type="button" className="logic-run-panel__link-button" onClick={onRetryHistory}>重试</button>
          ) : undefined}
        />
      )}

      {historyState === "ready" && history.length === 0 && (
        <p className="logic-run-panel__empty">暂无服务端运行记录。</p>
      )}

      {historyState !== "error" && history.length > 0 && (
        <ul className="logic-run-panel__history-list">
          {history.map((item) => {
            const selected = item.run_id === selectedRunId;
            const nodeCounts = (["executed", "skipped", "failed", "canceled"] as const)
              .flatMap((status) => item.node_counts[status] === undefined
                ? []
                : [`${NODE_STATUS_LABELS[status]} ${item.node_counts[status]}`]);
            return (
              <li key={item.run_id}>
                <button
                  type="button"
                  className={`logic-run-panel__history-item${selected ? " is-selected" : ""}`}
                  aria-pressed={selected}
                  disabled={item.production_written !== false}
                  onClick={() => {
                    if (item.production_written === false) onSelectRun(item.run_id);
                  }}
                >
                  <span className="logic-run-panel__history-title">
                    <strong>{item.run_id}</strong>
                    <StatusBadge status={item.status} />
                  </span>
                  <span><time dateTime={item.started_at}>{item.started_at}</time></span>
                  <span>revision {item.evaluated_revision} · {item.elapsed_ms} ms</span>
                  <span>Token：<Tokens value={item.total_tokens} /></span>
                  {nodeCounts.length > 0 && <span>节点：{nodeCounts.join(" · ")}</span>}
                  {item.error_code && <span>错误：<code>{item.error_code}</code></span>}
                  <span className={item.production_written === false ? "is-safe" : "is-unsafe"}>
                    production_written={String(item.production_written)}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {historyState !== "error" && hasMoreHistory && (
        <button
          type="button"
          className="logic-run-panel__load-more"
          disabled={loadingMoreHistory || !onLoadMoreHistory}
          onClick={onLoadMoreHistory}
        >
          {loadingMoreHistory ? "正在读取更多…" : "加载更多运行记录"}
        </button>
      )}
    </aside>
  );
}

export function LogicRunPanel(props: LogicRunPanelProps) {
  const {
    run,
    runState,
    runError,
    onLocateNode,
    onRetryRun,
  } = props;

  let detail: ReactNode;
  if (runState === "loading") {
    detail = <p className="logic-run-panel__empty" role="status">正在读取服务端运行详情…</p>;
  } else if (runState === "error") {
    detail = (
      <ErrorState
        title="安全试跑或运行详情读取失败"
        message={runError || "服务端未提供错误详情。"}
        action={onRetryRun ? (
          <button type="button" className="logic-run-panel__link-button" onClick={onRetryRun}>重试</button>
        ) : undefined}
      />
    );
  } else if (runState === "ready" && run) {
    detail = <RunDetail run={run} onLocateNode={onLocateNode} />;
  } else if (runState === "ready") {
    detail = <p className="logic-run-panel__empty">服务端未返回该次运行详情。</p>;
  } else {
    detail = <p className="logic-run-panel__empty">选择一条服务端运行记录查看逐节点结果。</p>;
  }

  return (
    <div className="logic-run-panel">
      <HistoryList {...props} />
      <div className="logic-run-panel__detail-shell">{detail}</div>
    </div>
  );
}
