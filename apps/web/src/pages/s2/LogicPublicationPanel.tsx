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
const DEFAULT_AUTOMATION_DISABLED_REASON = "生产调度与执行器尚未闭环；自动化只能绑定不可变 publication，当前保持禁用";

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
      <dl style={factsStyle}>
        <Fact label="Publication ID"><code>{publication.publication_id}</code></Fact>
        <Fact label="已发布 Graph">{publication.graph_id} · revision {publication.graph_revision}</Fact>
        <Fact label="Graph hash"><code>{publication.graph_hash}</code></Fact>
        <Fact label="成功 Dry-Run"><code>{publication.dry_run_id}</code></Fact>
        <Fact label="Eval suite"><code>{publication.eval_suite_id}</code></Fact>
        <Fact label="Eval report"><code>{publication.eval_report_id}</code></Fact>
        <Fact label="发布人">{publication.actor}</Fact>
        <Fact label="发布时间"><Timestamp value={publication.created_at} /></Fact>
      </dl>
      <GateFacts gate={publication.eval_gate} />
      <p style={{ margin: "8px 0 0", color: "var(--aos-muted)", fontSize: "0.7rem" }}>
        发布详情来自服务端不可变快照；查看旧 publication 不会修改当前画布或运行历史。
      </p>
    </div>
  );
}

function intrinsicDisabledReason(props: LogicPublicationPanelProps): string {
  if (props.publishDisabledReason) return props.publishDisabledReason;
  if (!props.graphId.trim()) return "Logic Graph 尚未加载";
  if (!Number.isSafeInteger(props.graphRevision) || props.graphRevision < 1) return "服务端 revision 无效";
  if (!HASH_RE.test(props.graphHash)) return "服务端 graph hash 无效";
  if (!props.evalSuiteId?.trim()) return "请选择与当前 revision 绑定的 Eval suite";
  if (!props.evalReportId?.trim()) return "请选择与当前 revision 绑定的 Eval report";
  if (!props.evalGate) return "尚未读取真实 Eval 门控证据";
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
            只发布服务端已保存的精确 revision/hash；POST 后必须完成 publication 详情回读才算成功。
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          disabled={publishDisabled}
          title={props.publishing ? "发布请求正在处理，请勿重复提交" : disabledReason || "发布当前已确认 revision"}
          onClick={() => {
            if (!publishDisabled) props.onPublish();
          }}
        >
          {props.publishing ? "发布中…" : "发布当前 revision"}
        </button>
      </div>

      <dl style={factsStyle}>
        <Fact label="当前 Graph">{props.graphId || "未加载"} · revision {props.graphRevision || "—"}</Fact>
        <Fact label="当前 Graph hash"><code>{props.graphHash || "—"}</code></Fact>
        <Fact label="Eval suite"><code>{props.evalSuiteId || "未选择"}</code></Fact>
        <Fact label="Eval report"><code>{props.evalReportId || "未选择"}</code></Fact>
      </dl>
      {props.evalGate ? <GateFacts gate={props.evalGate} /> : (
        <p style={{ margin: "8px 0 0", color: "var(--aos-muted)", fontSize: "0.72rem" }}>尚未读取与当前 revision/hash 绑定的真实 Eval 门控证据。</p>
      )}
      <div role="status" data-testid="logic-publish-gate-reason" style={{ marginTop: 8, color: disabledReason ? "var(--aos-amber-700)" : "var(--aos-green-700)", fontSize: "0.72rem" }}>
        {props.publishing ? "发布请求处理中；等待 POST 与 GET 回读完成" : disabledReason || "已满足受治理发布门禁"}
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
              {props.publications.map((item) => {
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
                      <strong>{item.publication_id}</strong>
                      <span style={{ display: "block", marginTop: 2, fontSize: "0.7rem", color: "var(--aos-muted)" }}>
                        revision {item.graph_revision} · <Timestamp value={item.created_at} />
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
              自动化仅可绑定不可变 publication；不能绑定当前可编辑草稿 revision。
            </p>
          </div>
          <button type="button" className="btn" disabled title={automationReason}>绑定自动化（禁用）</button>
        </div>
        <p style={{ margin: "6px 0 0", color: "var(--aos-amber-700)", fontSize: "0.7rem" }}>{automationReason}</p>
      </section>
    </section>
  );
}
