import { Link } from "react-router-dom";

type Props = {
  status: string;
  owner: string;
  reasons: string[];
  observedAt?: string | null;
  expiresAt?: string | null;
  actionLabel: string;
  actionHref?: string;
  onAction?: () => void;
  actionDisabled?: boolean;
  technicalCodes?: string[];
  testId?: string;
};

function unique(values: string[]): string[] {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function timeLabel(value?: string | null): string {
  if (!value || Number.isNaN(Date.parse(value))) return "未提供";
  return new Date(value).toLocaleString();
}

export function AipReadinessActionCard({
  status,
  owner,
  reasons,
  observedAt,
  expiresAt,
  actionLabel,
  actionHref,
  onAction,
  actionDisabled = false,
  technicalCodes = [],
  testId = "aip-readiness-action-card",
}: Props) {
  const businessReasons = unique(reasons);
  const codes = unique(technicalCodes);
  return (
    <section className="notice" role="note" data-testid={testId} style={{ padding: 14, marginBottom: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10 }}>
        <div><strong>当前状态</strong><div>{status}</div></div>
        <div><strong>责任方</strong><div>{owner}</div></div>
        <div><strong>证据时间</strong><div>生成 {timeLabel(observedAt)}<br />证据到期 {timeLabel(expiresAt)}</div></div>
      </div>
      <div style={{ marginTop: 10 }}>
        <strong>需要处理</strong>
        {businessReasons.length ? <ul style={{ margin: "6px 0 0", paddingLeft: 20 }}>{businessReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : <p style={{ marginBottom: 0 }}>尚无可归因的业务原因，请刷新权威状态后再判断。</p>}
      </div>
      <div style={{ marginTop: 12 }}>
        {actionHref ? <Link className="btn primary" to={actionHref}>{actionLabel}</Link> : <button className="btn primary" type="button" onClick={onAction} disabled={actionDisabled}>{actionLabel}</button>}
      </div>
      {codes.length ? <details style={{ marginTop: 10 }}><summary>技术标识（审计用）</summary><code>{codes.join(" · ")}</code></details> : null}
    </section>
  );
}
