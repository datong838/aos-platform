import type { ReactNode } from "react";

import type {
  LogicPublication,
  LogicPublicationEvalGate,
} from "./logicPublicationContracts";

export type LogicPublicationLoadState = "idle" | "loading" | "ready" | "error";

export interface LogicPublicationPanelProps {
  graphId: string;
  graphRevision: number;
  graphHash: string;
  evalSuiteId: string | null;
  evalReportId: string | null;
  evalGate?: LogicPublicationEvalGate | null;
  publishDisabledReason: string;
  publishing: boolean;
  publication: LogicPublication | null;
  publicationState: LogicPublicationLoadState;
  publicationError?: string | null;
  publications: readonly LogicPublication[];
  publicationsState: LogicPublicationLoadState;
  publicationsError?: string | null;
  selectedPublicationId?: string | null;
  automationDisabledReason?: string;
  onPublish: () => void;
  onSelectPublication: (publicationId: string) => void;
  onRetryPublication?: () => void;
  onRetryPublications?: () => void;
}

const HASH_RE = /^[0-9a-f]{64}$/;
const DEFAULT_AUTOMATION_DISABLED_REASON = "请先完成正式发布，并在上线执行审批中补齐生产调度与执行器条件；自动化只绑定不可变发布版本";

const panelStyle = {
  border: "1px solid var(--aos-border)",
  borderRadius: 2,
  padding: 12,
} as const;

const factsStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: 8,
  margin: "8px 0 0",
} as const;

const factStyle = {
  display: "grid",
  gap: 2,
  minWidth: 0,
  padding: 8,
  background: "var(--aos-surface-hover)",
  borderRadius: 2,
} as const;

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function Timestamp({ value }: { value: string }) {
  return <time dateTime={value}>{new Date(value).toLocaleString()}</time>;
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={factStyle}>
      <dt style={{ color: "var(--aos-muted)", fontSize: "0.68rem" }}>{label}</dt>
      <dd style={{ margin: 0, overflowWrap: "anywhere", fontSize: "0.75rem" }}>{children}</dd>
    </div>
  );
}

function GateFacts({ gate }: { gate: LogicPublicationEvalGate }) {
  return (
    <dl style={factsStyle}>
      <Fact label="门控结论">通过</Fact>
      <Fact label="通过率">{percent(gate.pass_rate)}</Fact>
      <Fact label="阈值">{percent(gate.threshold)}</Fact>
      <Fact label="用例">通过 {gate.passed} / 失败 {gate.failed} / 总计 {gate.total}</Fact>
      <Fact label="评测时间"><Timestamp value={gate.run_at} /></Fact>
    </dl>
  );
}

function ErrorState({
  title,
  message,
  retryLabel,
  onRetry,
}: {
  title: string;
  message: string;
  retryLabel: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" style={{ marginTop: 8, padding: 8, color: "var(--aos-red)", background: "var(--aos-red-bg)" }}>
      <strong>{title}</strong>
      <span style={{ display: "block", marginTop: 3 }}>{message}</span>
      {onRetry && <button type="button" className="btn" style={{ marginTop: 6 }} onClick={onRetry}>{retryLabel}</button>}
    </div>
  );
}

function PublicationDetail({ publication }: { publication: LogicPublication }) {
  return (
    <div data-publication-id={publication.publication_id}>
      <p style={{ margin: "8px 0", color: "var(--aos-text-secondary)", fontSize: "0.75rem" }}>
        业务逻辑修订 {publication.graph_revision} 已完成正式发布和证据回读 · <Timestamp value={publication.created_at} />
      </p>
      <GateFacts gate={publication.eval_gate} />
      <details style={{ marginTop: 8 }}>
        <summary>发布技术标识（审计用）</summary>
        <dl style={factsStyle}>
          <Fact label="发布记录 ID"><code>{publication.publication_id}</code></Fact>
          <Fact label="业务逻辑图">{publication.graph_id} · 修订 {publication.graph_revision}</Fact>
          <Fact label="内容摘要"><code>{publication.graph_hash}</code></Fact>
          <Fact label="安全试跑记录"><code>{publication.dry_run_id}</code></Fact>
          <Fact label="评测套件"><code>{publication.eval_suite_id}</code></Fact>
          <Fact label="评测报告"><code>{publication.eval_report_id}</code></Fact>
          <Fact label="发布人">{publication.actor}</Fact>
        </dl>
      </details>
      <p style={{ margin: "8px 0 0", color: "var(--aos-muted)", fontSize: "0.7rem" }}>
        发布详情来自服务端不可变快照；查看历史发布不会修改当前画布或运行记录。
      </p>
    </div>
  );
}

function intrinsicDisabledReason(props: LogicPublicationPanelProps): string {
  if (props.publishDisabledReason) return props.publishDisabledReason;
  if (!props.graphId.trim()) return "请先选择或新建业务逻辑";
  if (!Number.isSafeInteger(props.graphRevision) || props.graphRevision < 1) return "当前业务逻辑修订号无效，请刷新后重试";
  if (!HASH_RE.test(props.graphHash)) return "当前业务逻辑内容摘要无效，请重新保存并回读";
  if (!props.evalSuiteId?.trim()) return "请选择与当前修订绑定的评测套件";
  if (!props.evalReportId?.trim()) return "请选择与当前修订绑定的评测报告";
  if (!props.evalGate) return "请先读取当前修订的真实评测门控证据";
  return "";
}

export function LogicPublicationPanel(props: LogicPublicationPanelProps) {
  const disabledReason = intrinsicDisabledReason(props);
  const publishDisabled = props.publishing || Boolean(disabledReason);
  const automationReason = props.automationDisabledReason || DEFAULT_AUTOMATION_DISABLED_REASON;

  return (
    <section style={panelStyle} aria-label="Logic 发布治理">
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <div>
          <h3 style={{ margin: 0, fontSize: "0.84rem" }}>发布治理</h3>
          <p style={{ margin: "3px 0 0", color: "var(--aos-muted)", fontSize: "0.72rem" }}>
            只发布已保存并通过评测的精确修订；发布后必须回读确认正式记录才算成功。
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          disabled={publishDisabled}
          title={props.publishing ? "发布请求正在处理，请勿重复提交" : disabledReason || "发布当前已确认修订"}
          onClick={() => {
            if (!publishDisabled) props.onPublish();
          }}
        >
          {props.publishing ? "发布中…" : "发布当前修订"}
        </button>
      </div>

      <details style={{ marginTop: 8 }}>
        <summary>当前修订技术标识（审计用）</summary>
        <dl style={factsStyle}>
          <Fact label="业务逻辑图">{props.graphId || "未加载"} · 修订 {props.graphRevision || "—"}</Fact>
          <Fact label="内容摘要"><code>{props.graphHash || "—"}</code></Fact>
          <Fact label="评测套件"><code>{props.evalSuiteId || "未选择"}</code></Fact>
          <Fact label="评测报告"><code>{props.evalReportId || "未选择"}</code></Fact>
        </dl>
      </details>
      {props.evalGate ? <GateFacts gate={props.evalGate} /> : (
        <p style={{ margin: "8px 0 0", color: "var(--aos-muted)", fontSize: "0.72rem" }}>请先读取与当前修订和内容摘要绑定的真实评测门控证据。</p>
      )}
      <div role="status" data-testid="logic-publish-gate-reason" style={{ marginTop: 8, color: disabledReason ? "var(--aos-amber-700)" : "var(--aos-green-700)", fontSize: "0.72rem" }}>
        {props.publishing ? "发布请求处理中；正在等待提交与回读完成" : disabledReason || "已满足受治理发布门禁"}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 0.8fr) minmax(280px, 1.2fr)", gap: 10, marginTop: 12 }}>
        <section style={panelStyle} aria-label="发布历史">
          <h4 style={{ margin: 0, fontSize: "0.78rem" }}>发布历史</h4>
          {props.publicationsState === "loading" && <p>正在读取发布历史…</p>}
          {props.publicationsState === "error" && (
            <ErrorState
              title="发布历史读取失败"
              message={props.publicationsError || "未知错误"}
              retryLabel="重试发布历史"
              onRetry={props.onRetryPublications}
            />
          )}
          {props.publicationsState === "ready" && props.publications.length === 0 && (
            <p style={{ color: "var(--aos-muted)", fontSize: "0.75rem" }}>暂无服务端发布记录。</p>
          )}
          {props.publications.length > 0 && (
            <ol style={{ display: "grid", gap: 6, margin: "8px 0 0", padding: 0, listStyle: "none" }}>
              {props.publications.map((item, index) => {
                const selected = item.publication_id === props.selectedPublicationId;
                return (
                  <li key={item.publication_id}>
                    <button
                      type="button"
                      aria-pressed={selected}
                      className="btn"
                      style={{ display: "block", width: "100%", textAlign: "left" }}
                      onClick={() => props.onSelectPublication(item.publication_id)}
                    >
                      <strong>正式发布记录 {index + 1}</strong>
                      <span style={{ display: "block", marginTop: 2, fontSize: "0.7rem", color: "var(--aos-muted)" }}>
                        修订 {item.graph_revision} · <Timestamp value={item.created_at} />
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          )}
        </section>

        <section style={panelStyle} aria-label="发布详情">
          <h4 style={{ margin: 0, fontSize: "0.78rem" }}>发布详情</h4>
          {props.publicationState === "idle" && <p style={{ color: "var(--aos-muted)", fontSize: "0.75rem" }}>选择一条服务端发布记录查看不可变详情。</p>}
          {props.publicationState === "loading" && <p>正在读取发布详情…</p>}
          {props.publicationState === "error" && (
            <ErrorState
              title="发布详情读取失败"
              message={props.publicationError || "未知错误"}
              retryLabel="重试发布详情"
              onRetry={props.onRetryPublication}
            />
          )}
          {props.publicationState === "ready" && props.publication && (
            <PublicationDetail publication={props.publication} />
          )}
          {props.publicationState === "ready" && !props.publication && (
            <p style={{ color: "var(--aos-muted)", fontSize: "0.75rem" }}>服务端未返回发布详情。</p>
          )}
        </section>
      </div>

      <section style={{ ...panelStyle, marginTop: 10, background: "var(--aos-surface-hover)" }} aria-label="Logic 自动化绑定">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
          <div>
            <h4 style={{ margin: 0, fontSize: "0.78rem" }}>自动化</h4>
            <p style={{ margin: "3px 0 0", color: "var(--aos-muted)", fontSize: "0.72rem" }}>
              自动化仅可绑定不可变的正式发布版本；不能绑定当前可编辑草稿。
            </p>
          </div>
          <a className="btn" href="/aip/production-contracts" title={automationReason}>进入上线执行审批补齐自动化条件 →</a>
        </div>
        <p style={{ margin: "6px 0 0", color: "var(--aos-amber-700)", fontSize: "0.7rem" }}>{automationReason}</p>
      </section>
    </section>
  );
}
