import { useMemo, useState } from "react";

import { aipEvidenceSdk } from "../../api/aipEvidence";
import type { EvidenceQuality, TelemetrySpan, UsageReceipt } from "../../api/aipEvidence/contracts";
import { PageChrome } from "../../components/PageChrome";

export type AuthorityObservabilitySummary = {
  spanCount: number;
  errorSpanCount: number;
  usageReceiptCount: number;
  measuredCount: number;
  estimatedCount: number;
  unknownCount: number;
};

export function summarizeAuthority(spans: TelemetrySpan[], receipts: UsageReceipt[]): AuthorityObservabilitySummary {
  const qualities: EvidenceQuality[] = [
    ...spans.map((span) => span.quality),
    ...receipts.map((receipt) => receipt.quality),
  ];
  return {
    spanCount: spans.length,
    errorSpanCount: spans.filter((span) => span.status === "error").length,
    usageReceiptCount: receipts.length,
    measuredCount: qualities.filter((quality) => quality === "measured").length,
    estimatedCount: qualities.filter((quality) => quality === "estimated").length,
    unknownCount: qualities.filter((quality) => quality === "unknown").length,
  };
}

export function formatSpanDuration(span: TelemetrySpan): string {
  if (!span.producerEndedAt) return "未知";
  const duration = new Date(span.producerEndedAt).getTime() - new Date(span.producerStartedAt).getTime();
  if (!Number.isFinite(duration) || duration < 0) return "无效";
  return duration >= 1000 ? `${(duration / 1000).toFixed(2)}s` : `${duration}ms`;
}

export function formatUsageQuantity(receipt: UsageReceipt): string {
  if (receipt.quantity === null) return "未知（未伪造 0）";
  const value = Number.isInteger(receipt.quantity) ? String(receipt.quantity) : receipt.quantity.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  return receipt.currency ? `${receipt.currency} ${value}` : `${value} ${receipt.unit}`;
}

export function filterAuthoritySpans(spans: TelemetrySpan[], query: string): TelemetrySpan[] {
  const keyword = query.trim().toLowerCase();
  if (!keyword) return spans;
  return spans.filter((span) => [span.traceId, span.spanId, span.name, span.provider, span.kind, span.status]
    .some((value) => value.toLowerCase().includes(keyword)));
}

type View = "overview" | "spans" | "usage";
type LoadState = "idle" | "loading" | "loaded" | "error";

const cardStyle = {
  border: "1px solid var(--aos-border)",
  background: "var(--aos-panel)",
  borderRadius: 4,
  padding: "18px",
} as const;

const thStyle = { textAlign: "left", padding: "10px 12px", color: "var(--aos-muted)", fontSize: 12 } as const;
const tdStyle = { padding: "11px 12px", borderTop: "1px solid var(--aos-border)", fontSize: 13, verticalAlign: "top" } as const;

function qualityTone(quality: EvidenceQuality): string {
  if (quality === "measured") return "var(--aos-green-600)";
  if (quality === "estimated") return "var(--aos-amber)";
  return "var(--aos-muted)";
}

export function ObservabilityPage() {
  const [lineageId, setLineageId] = useState("");
  const [spans, setSpans] = useState<TelemetrySpan[]>([]);
  const [receipts, setReceipts] = useState<UsageReceipt[]>([]);
  const [view, setView] = useState<View>("overview");
  const [query, setQuery] = useState("");
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);

  const summary = useMemo(() => summarizeAuthority(spans, receipts), [spans, receipts]);
  const filteredSpans = useMemo(() => filterAuthoritySpans(spans, query), [spans, query]);

  async function load() {
    const target = lineageId.trim();
    if (!target) {
      setError("请输入真实 Lineage ID");
      setLoadState("idle");
      return;
    }
    setError(null);
    setSpans([]);
    setReceipts([]);
    setLoadState("loading");
    try {
      const [nextSpans, nextReceipts] = await Promise.all([
        aipEvidenceSdk.spans(target),
        aipEvidenceSdk.usage(target),
      ]);
      setSpans(nextSpans);
      setReceipts(nextReceipts);
      setLoadState("loaded");
    } catch (caught) {
      setError(String((caught as Error).message || caught));
      setLoadState("error");
    }
  }

  function exportAuthority() {
    if (loadState !== "loaded") return;
    const blob = new Blob([JSON.stringify({ lineageId: lineageId.trim(), spans, usageReceipts: receipts }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `aip-authority-${lineageId.trim()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <PageChrome title="AIP 可观测性" lede="按 Lineage 查询权威 Telemetry Span 与 Usage Receipt；不推算趋势，不回填演示数据。">
      <div className="bp5-card" style={{ ...cardStyle, display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
        <label style={{ display: "grid", gap: 6, minWidth: 320 }}>
          <span className="muted">Lineage ID</span>
          <input
            aria-label="observability-lineage-id"
            value={lineageId}
            onChange={(event) => setLineageId(event.target.value)}
            placeholder="输入真实 lineage_id"
          />
        </label>
        <button type="button" className="btn primary" onClick={() => void load()} disabled={loadState === "loading"}>
          {loadState === "loading" ? "读取中…" : "读取权威证据"}
        </button>
        <button type="button" className="btn" onClick={exportAuthority} disabled={loadState !== "loaded"}>导出当前证据</button>
      </div>

      <div style={{ display: "flex", gap: 8, margin: "16px 0" }}>
        {(["overview", "spans", "usage"] as const).map((item) => (
          <button key={item} type="button" className={`btn ${view === item ? "primary" : ""}`} onClick={() => setView(item)} data-testid={`obs-tab-${item}`}>
            {item === "overview" ? "概览" : item === "spans" ? "Spans" : "Usage Receipts"}
          </button>
        ))}
      </div>

      {loadState === "idle" && !error && <div data-testid="observability-idle" className="callout info">请输入真实 Lineage ID。页面不会显示固定 Trace、合成趋势或推算 Token。</div>}
      {loadState === "loaded" && spans.length === 0 && receipts.length === 0 && <div data-testid="observability-empty" className="callout warning">该 Lineage 暂无权威 Span 或 Usage Receipt。</div>}
      {error && <div data-testid="observability-error" className="callout warning">权威可观测性读取失败：{error}</div>}

      {loadState === "loaded" && view === "overview" && (spans.length > 0 || receipts.length > 0) && (
        <div data-testid="observability-authority-summary">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
            {[
              ["Span", summary.spanCount],
              ["错误 Span", summary.errorSpanCount],
              ["Usage Receipt", summary.usageReceiptCount],
              ["实测", summary.measuredCount],
              ["估算", summary.estimatedCount],
              ["未知", summary.unknownCount],
            ].map(([label, value]) => <div key={label} style={cardStyle}><div className="muted">{label}</div><strong style={{ fontSize: 28 }}>{value}</strong></div>)}
          </div>
          <div className="callout info" style={{ marginTop: 14 }}>所有数量均由当前权威回包直接计数；未知用量保持 unknown，不折算为 0。</div>
        </div>
      )}

      {loadState === "loaded" && view === "spans" && (
        <section style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", marginBottom: 10 }}>
            <strong>Telemetry Spans（{filteredSpans.length}/{spans.length}）</strong>
            <input aria-label="span-filter" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="过滤 trace / span / provider" />
          </div>
          {spans.length === 0 ? <div className="muted">暂无权威 Span。</div> : (
            <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr><th style={thStyle}>名称</th><th style={thStyle}>Provider</th><th style={thStyle}>Trace / Span</th><th style={thStyle}>类型 / 状态</th><th style={thStyle}>时长</th><th style={thStyle}>质量</th><th style={thStyle}>观测时间</th></tr></thead>
              <tbody>{filteredSpans.map((span) => <tr key={span.spanRecordId}>
                <td style={tdStyle}>{span.name}</td><td style={tdStyle}>{span.provider}</td>
                <td style={{ ...tdStyle, fontFamily: "monospace" }}>{span.traceId}<br />{span.spanId}</td>
                <td style={tdStyle}>{span.kind} / {span.status}</td><td style={tdStyle}>{formatSpanDuration(span)}</td>
                <td style={{ ...tdStyle, color: qualityTone(span.quality) }}>{span.quality}</td><td style={tdStyle}>{new Date(span.observedAt).toLocaleString()}</td>
              </tr>)}</tbody>
            </table></div>
          )}
        </section>
      )}

      {loadState === "loaded" && view === "usage" && (
        <section style={cardStyle}>
          <strong>Usage Receipts（{receipts.length}）</strong>
          {receipts.length === 0 ? <div className="muted" style={{ marginTop: 10 }}>暂无权威 Usage Receipt。</div> : (
            <div style={{ overflowX: "auto", marginTop: 10 }}><table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr><th style={thStyle}>类型</th><th style={thStyle}>数量</th><th style={thStyle}>Provider</th><th style={thStyle}>Receipt</th><th style={thStyle}>质量</th><th style={thStyle}>观测时间</th></tr></thead>
              <tbody>{receipts.map((receipt) => <tr key={receipt.receiptId}>
                <td style={tdStyle}>{receipt.usageKind}</td><td style={tdStyle}>{formatUsageQuantity(receipt)}</td><td style={tdStyle}>{receipt.provider}</td>
                <td style={{ ...tdStyle, fontFamily: "monospace" }}>{receipt.receiptId}<br />{receipt.providerReceiptId}</td>
                <td style={{ ...tdStyle, color: qualityTone(receipt.quality) }}>{receipt.quality}</td><td style={tdStyle}>{new Date(receipt.observedAt).toLocaleString()}</td>
              </tr>)}</tbody>
            </table></div>
          )}
        </section>
      )}
    </PageChrome>
  );
}
