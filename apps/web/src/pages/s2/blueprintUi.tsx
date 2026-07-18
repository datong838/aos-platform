import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function BpToolbar({ children }: { children: ReactNode }) {
  return (
    <div className="filter-bar" style={{ flexWrap: "wrap", gap: 8, marginBottom: "0.75rem" }}>
      {children}
    </div>
  );
}

export function BpTabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: string; label: string }[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="bp-tabs" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={active === t.id}
          className={active === t.id ? "bp-tab is-active" : "bp-tab"}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function BpMetricGrid({
  items,
}: {
  items: { code?: string; label: string; value: string | number; tone?: "ok" | "warn" | "bad" | "muted" }[];
}) {
  return (
    <div className="bp-metric-grid">
      {items.map((m) => (
        <div key={m.code || m.label} className={`bp-metric bp-metric-${m.tone || "muted"}`}>
          {m.code && <div className="bp-metric-code">{m.code}</div>}
          <div className="bp-metric-label">{m.label}</div>
          <div className="bp-metric-value">{m.value}</div>
        </div>
      ))}
    </div>
  );
}

export function BpStagePipeline({
  stages,
}: {
  stages: {
    step: string;
    title: string;
    subtitle?: string;
    status: string;
    progress?: number;
    tone?: "done" | "active" | "wait";
    href?: string;
    linkLabel?: string;
  }[];
}) {
  return (
    <div className="bp-stage-stack">
      {stages.map((s, i) => (
        <div key={s.step}>
          <div className={`bp-stage-card bp-stage-${s.tone || "wait"}`}>
            <div className="bp-stage-head">
              <div>
                <div className="bp-stage-step">{s.step}</div>
                <div className="bp-stage-title">{s.title}</div>
                {s.subtitle && <p className="muted" style={{ fontSize: "0.75rem", marginTop: 4 }}>{s.subtitle}</p>}
                {s.href &&
                  (s.href.startsWith("#") ? (
                    <a href={s.href} className="nav-link" style={{ fontSize: "0.75rem", display: "inline-block", marginTop: 6 }}>
                      {s.linkLabel || "查看 →"}
                    </a>
                  ) : (
                    <Link to={s.href} className="nav-link" style={{ fontSize: "0.75rem", display: "inline-block", marginTop: 6 }}>
                      {s.linkLabel || "查看 →"}
                    </Link>
                  ))}
              </div>
              <span className="bp-stage-status">{s.status}</span>
            </div>
            {s.progress != null && s.progress > 0 && s.progress < 1 && (
              <div className="bp-progress">
                <div className="bp-progress-bar" style={{ width: `${Math.round(s.progress * 100)}%` }} />
              </div>
            )}
          </div>
          {i < stages.length - 1 && <div className="bp-stage-arrow">↓</div>}
        </div>
      ))}
    </div>
  );
}

export function BpSplit({ left, right }: { left: ReactNode; right: ReactNode }) {
  return (
    <div className="bp-split">
      <div className="bp-split-left">{left}</div>
      <div className="bp-split-right">{right}</div>
    </div>
  );
}

export function BpBanner({ tone, children }: { tone: "warn" | "info"; children: ReactNode }) {
  return <div className={`bp-banner bp-banner-${tone}`}>{children}</div>;
}

export function BpTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: ReactNode[][];
}) {
  return (
    <div className="bp-table-wrap">
      <table className="data-table bp-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, i) => (
            <tr key={i}>
              {cells.map((cell, j) => (
                <td key={j}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function BpLinkRow({ links }: { links: { to: string; label: string }[] }) {
  return (
    <p className="muted" style={{ marginTop: "0.75rem" }}>
      {links.map((l, i) => (
        <span key={l.to}>
          {i > 0 ? " · " : null}
          <Link to={l.to}>{l.label}</Link>
        </span>
      ))}
    </p>
  );
}

export function BpDraftCard({
  title,
  meta,
  preview,
  status,
  tag,
  actions,
}: {
  title: string;
  meta: string;
  preview?: string;
  status: "proposed" | "approved" | "rejected";
  tag?: string;
  actions?: ReactNode;
}) {
  const statusLabel =
    status === "proposed" ? "待审" : status === "approved" ? "已通过" : "已驳回";
  const tone =
    status === "proposed" ? "pending" : status === "approved" ? "done" : "reject";
  return (
    <div className={`bp-draft-card bp-draft-${tone}`}>
      <div className="bp-draft-head">
        <div>
          {tag && <span className="bp-tag bp-tag-warn">{tag}</span>}
          <div className="bp-draft-title">{title}</div>
          <div className="muted" style={{ fontSize: "0.75rem", marginTop: 4 }}>
            {meta}
          </div>
          {preview && (
            <div className="bp-draft-preview">{preview}</div>
          )}
        </div>
        <span className={`bp-draft-badge bp-draft-badge-${tone}`}>{statusLabel}</span>
      </div>
      {actions && <div className="bp-draft-actions">{actions}</div>}
    </div>
  );
}

type LineageStep = {
  phase: string;
  title: string;
  subtitle?: string;
  tone?: "input" | "process" | "fuse" | "output" | "backfill" | "gov";
};

export function BpLineageTimeline({ steps }: { steps: LineageStep[] }) {
  return (
    <div className="bp-lineage-panel">
      {steps.map((s, i) => (
        <div key={`${s.phase}-${i}`} className={`bp-lineage-step bp-lineage-${s.tone || "process"}`}>
          <div className="bp-lineage-phase">{s.phase}</div>
          <div>
            <div className="bp-lineage-title">{s.title}</div>
            {s.subtitle && (
              <div className="muted" style={{ fontSize: "0.75rem", marginTop: 4 }}>
                {s.subtitle}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export function BpDomainPanel({
  tone,
  title,
  hint,
  children,
}: {
  tone: "workshop" | "aip" | "ontology" | "data" | "apollo";
  title: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <section className={`bp-domain bp-domain-${tone}`}>
      <h2>{title}</h2>
      {hint && <p className="hint">{hint}</p>}
      {children}
    </section>
  );
}

export function BpIndexTile({
  to,
  eyebrow,
  title,
  desc,
  accent,
}: {
  to: string;
  eyebrow: string;
  title: string;
  desc: string;
  accent?: "sky" | "amber" | "violet" | "cyan" | "emerald" | "indigo";
}) {
  return (
    <Link to={to} className={`bp-index-tile bp-index-accent-${accent || "sky"}`}>
      <div className="bp-index-eyebrow">{eyebrow}</div>
      <div className="bp-index-title">{title}</div>
      <p className="bp-index-desc">{desc}</p>
    </Link>
  );
}

export function BpHeroLink({
  to,
  eyebrow,
  title,
  desc,
  cta,
  accent = "sky",
}: {
  to: string;
  eyebrow: string;
  title: string;
  desc: string;
  cta: string;
  accent?: "sky" | "amber" | "violet" | "indigo";
}) {
  return (
    <Link to={to} className={`bp-hero-link bp-hero-${accent}`}>
      <div>
        <div className="bp-index-eyebrow">{eyebrow}</div>
        <div className="bp-hero-title">{title}</div>
        <p className="bp-index-desc">{desc}</p>
      </div>
      <span className="bp-hero-cta">{cta}</span>
    </Link>
  );
}

export function BpDiscoverCard({
  to,
  onClick,
  title,
  badge,
  meta,
  accent = "violet",
  cta = "打开 →",
}: {
  to?: string;
  onClick?: () => void;
  title: string;
  badge?: { label: string; tone: "ok" | "warn" | "bad" };
  meta: string;
  accent?: "violet" | "muted";
  cta?: string;
}) {
  const className = `bp-discover-card bp-discover-${accent}`;
  const inner = (
    <>
      <div className="bp-discover-head">
        <span className="bp-discover-title">{title}</span>
        {badge && (
          <span className={`bp-discover-badge bp-discover-badge-${badge.tone}`}>{badge.label}</span>
        )}
      </div>
      <p className="bp-discover-meta">{meta}</p>
      <span className="bp-discover-cta">{cta}</span>
    </>
  );
  if (onClick) {
    return (
      <button
        type="button"
        className={className}
        onClick={onClick}
        style={{ cursor: "pointer", textAlign: "left", width: "100%", border: "none", font: "inherit" }}
      >
        {inner}
      </button>
    );
  }
  return (
    <Link to={to || "#"} className={className}>
      {inner}
    </Link>
  );
}

export function BpVarBar({
  chips,
  trailing,
}: {
  chips: { label: string; tone?: "sky" | "amber" | "violet" | "emerald" | "muted" }[];
  trailing?: string;
}) {
  return (
    <div className="bp-var-bar">
      <span className="muted" style={{ fontSize: "0.65rem" }}>
        变量条
      </span>
      {chips.map((c) => (
        <span key={c.label} className={`bp-var-chip bp-var-${c.tone || "muted"}`}>
          {c.label}
        </span>
      ))}
      {trailing && <span className="bp-var-trail">{trailing}</span>}
    </div>
  );
}

export function BpWsGrid({
  filter,
  table,
  objectView,
}: {
  filter: ReactNode;
  table: ReactNode;
  objectView: ReactNode;
}) {
  return (
    <div className="bp-ws-grid">
      <div className="bp-ws-filter">{filter}</div>
      <div className="bp-ws-table">{table}</div>
      <div className="bp-ws-object">{objectView}</div>
    </div>
  );
}

export function BpPropGrid({ items }: { items: { label: string; value: string; tone?: string }[] }) {
  return (
    <div className="bp-prop-grid">
      {items.map((p) => (
        <div key={p.label}>
          <div className="bp-prop-label">{p.label}</div>
          <div className={p.tone ? `bp-prop-value bp-prop-${p.tone}` : "bp-prop-value"}>{p.value}</div>
        </div>
      ))}
    </div>
  );
}

export function flattenRecordProps(
  value: unknown,
  maxKeys = 12,
): { label: string; value: string; tone?: string }[] {
  if (value == null) return [{ label: "value", value: String(value) }];
  if (Array.isArray(value)) {
    return [{ label: "items", value: String(value.length), tone: "muted" }];
  }
  if (typeof value !== "object") {
    return [{ label: "value", value: String(value) }];
  }
  return Object.entries(value as Record<string, unknown>)
    .slice(0, maxKeys)
    .map(([label, v]) => ({
      label,
      value:
        typeof v === "object" && v !== null
          ? Array.isArray(v)
            ? `[${v.length}]`
            : JSON.stringify(v)
          : String(v ?? "—"),
      tone:
        label === "ok" && v === true
          ? "ok"
          : /error|fail|reject/i.test(label)
            ? "warn"
            : undefined,
    }));
}

/** 87 · 主区 PropGrid + 折叠完整 JSON（禁 JSON 主面板） */
export function BpDebugPanel({
  value,
  title = "完整 JSON",
}: {
  value: unknown;
  title?: string;
}) {
  if (value == null || value === "") return null;

  let parsed: unknown = value;
  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value);
    } catch {
      return (
        <details>
          <summary className="muted">{title}</summary>
          <pre className="card" style={{ fontSize: "0.65rem", whiteSpace: "pre-wrap" }}>
            {value}
          </pre>
        </details>
      );
    }
  }

  const items = flattenRecordProps(parsed);
  const raw = typeof value === "string" ? value : JSON.stringify(parsed, null, 2);

  return (
    <div style={{ marginTop: "0.5rem" }}>
      {items.length > 0 && <BpPropGrid items={items} />}
      <details style={{ marginTop: items.length > 0 ? "0.5rem" : 0 }}>
        <summary className="muted">{title}</summary>
        <pre className="card" style={{ fontSize: "0.65rem", whiteSpace: "pre-wrap" }}>
          {raw}
        </pre>
      </details>
    </div>
  );
}

export function BpToolGrid({
  catalog,
  enabled,
  detail,
}: {
  catalog: ReactNode;
  enabled: ReactNode;
  detail: ReactNode;
}) {
  return (
    <div className="bp-tool-grid">
      <div className="bp-tool-col">{catalog}</div>
      <div className="bp-tool-col">{enabled}</div>
      <div className="bp-tool-col">{detail}</div>
    </div>
  );
}

export function BpMaturityStairs({
  steps,
  active,
  onSelect,
}: {
  steps: {
    level: number;
    label: string;
    title: string;
    desc: string;
    foot?: ReactNode;
    tone?: "rose";
  }[];
  active: number;
  onSelect: (level: number) => void;
}) {
  return (
    <div className="bp-maturity-grid">
      {steps.map((s) => (
        <button
          key={s.level}
          type="button"
          className={
            active === s.level
              ? "bp-maturity-card is-active"
              : s.tone === "rose"
                ? "bp-maturity-card is-l4"
                : "bp-maturity-card"
          }
          onClick={() => onSelect(s.level)}
        >
          <div className="bp-maturity-level">{s.label}{active === s.level ? " · 当前" : ""}</div>
          <div className="bp-maturity-title">{s.title}</div>
          <p className="bp-maturity-desc">{s.desc}</p>
          {s.foot}
        </button>
      ))}
    </div>
  );
}

export function BpScoreGrid({
  items,
}: {
  items: { value: string; label: string; hint?: string; tone: "ok" | "warn" | "bad" }[];
}) {
  return (
    <div className="bp-score-grid">
      {items.map((i) => (
        <div key={i.label} className={`bp-score-card bp-score-${i.tone}`}>
          <div className="bp-score-value">{i.value}</div>
          <div className="bp-score-label">{i.label}</div>
          {i.hint && <div className="bp-score-hint">{i.hint}</div>}
        </div>
      ))}
    </div>
  );
}

export function BpKvList({
  rows,
}: {
  rows: { key: string; desc?: string; value: string; mono?: boolean }[];
}) {
  return (
    <div className="bp-kv-list">
      {rows.map((r) => (
        <div key={r.key} className="bp-kv-row">
          <div>
            <div className="bp-kv-key">{r.key}</div>
            {r.desc && <div className="bp-kv-desc">{r.desc}</div>}
          </div>
          <span className={r.mono ? "bp-kv-value mono" : "bp-kv-value"}>{r.value}</span>
        </div>
      ))}
    </div>
  );
}
