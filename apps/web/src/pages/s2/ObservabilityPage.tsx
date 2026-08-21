import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { aipEvidenceSdk } from "../../api/aipEvidence";
import { LINEAGE_ROOT_TYPES, type EvidenceQuality, type LineageRootType, type TelemetrySpan, type UsageReceipt } from "../../api/aipEvidence/contracts";
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

export type ObservabilityDeepLink = {
  lineageId: string;
  rootType: LineageRootType | null;
  rootId: string;
};

export function parseObservabilityDeepLink(search: string): ObservabilityDeepLink {
  const params = new URLSearchParams(search);
  const lineageId = params.get("lineageId")?.trim() ?? "";
  const rootId = params.get("rootId")?.trim() ?? "";
  const rawRootType = params.get("rootType")?.trim() ?? "";
  const rootType = LINEAGE_ROOT_TYPES.includes(rawRootType as LineageRootType)
    ? rawRootType as LineageRootType
    : null;
  return { lineageId, rootType: rootType && rootId ? rootType : null, rootId: rootType && rootId ? rootId : "" };
}

export function missingAuthorityReason(kind: "span" | "usage", count: number): string | null {
  if (count > 0) return null;
  return kind === "span"
    ? "缺失：当前权威 Lineage 尚未写入 Telemetry Span；这不是业务数量 0。"
    : "缺失：当前权威 Lineage 尚未写入 Usage Receipt；这不是 Token 或费用 0。";
}

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
  const deepLink = useMemo(() => parseObservabilityDeepLink(window.location.search), []);
  const [lineageId, setLineageId] = useState(deepLink.lineageId);
  const [spans, setSpans] = useState<TelemetrySpan[]>([]);
  const [receipts, setReceipts] = useState<UsageReceipt[]>([]);
  const [view, setView] = useState<View>("overview");
  const [query, setQuery] = useState("");
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);

  const summary = useMemo(() => summarizeAuthority(spans, receipts), [spans, receipts]);
  const filteredSpans = useMemo(() => filterAuthoritySpans(spans, query), [spans, query]);

  const load = useCallback(async (requestedLineageId?: string) => {
    const target = (requestedLineageId ?? lineageId).trim();
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
  }, [lineageId]);

  useEffect(() => {
    if (!deepLink.lineageId) return;
    void load(deepLink.lineageId);
    // deep-link auto query once per URL change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepLink.lineageId]);

  function exportAuthority() {
    if (loadState !== "loaded") return;
    const blob = new Blob([JSON.stringify({
      lineageId: lineageId.trim(),
      root: deepLink.rootType ? { rootType: deepLink.rootType, rootId: deepLink.rootId } : null,
      spans,
      usageReceipts: receipts,
      missingEvidence: {
        spans: missingAuthorityReason("span", spans.length),
        usageReceipts: missingAuthorityReason("usage", receipts.length),
      },
    }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `aip-authority-${lineageId.trim()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <PageChrome title="AIP 可观测性" lede="按 Lineage 查询权威 Telemetry Span 与 Usage Receipt；不推算趋势，不回填演示数据。">
      <div
        data-testid="observability-ops-stats"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 12 }}
      >
        {[
          { label: "加载态", value: loadState === "loaded" ? "已载" : loadState === "loading" ? "读取中" : loadState === "error" ? "失败" : "空闲" },
          { label: "视图", value: view === "overview" ? "概览" : view === "spans" ? "Spans" : "Usage" },
          { label: "Spans", value: String(spans.length) },
          { label: "Usage", value: String(receipts.length) },
          { label: "筛选命中", value: String(filteredSpans.length) },
          { label: "输入", value: lineageId.trim() ? "已填" : "待填" },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{s.value}</div>
          </div>
        ))}
      </div>
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
        <button
          type="button"
          className="btn"
          onClick={exportAuthority}
          disabled={loadState !== "loaded"}
          data-testid="observability-export"
          title={
            loadState === "loaded"
              ? "导出当前已读取的 Span / Usage JSON"
              : "请先读取权威证据后再导出；空闲/失败态不提供演示文件"
          }
        >
          {loadState === "loaded" ? "导出当前证据" : "导出（需先读取）"}
        </button>
        {deepLink.rootType && (
          <Link
            className="btn"
            to={`/aip/lineage?rootType=${encodeURIComponent(deepLink.rootType)}&rootId=${encodeURIComponent(deepLink.rootId)}`}
            data-testid="observability-back-lineage"
            style={{ textDecoration: "none" }}
          >
            返回 exact 谱系 →
          </Link>
        )}
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

      {loadState === "loaded" && (
        <div data-testid="observability-evidence-status" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: 12, marginBottom: 14 }}>
          <div style={cardStyle}>
            <strong>Telemetry Span</strong>
            <div className={spans.length ? "callout success" : "callout warning"} style={{ marginTop: 10 }}>
              {missingAuthorityReason("span", spans.length) ?? `已写入 ${spans.length} 条权威 Span。`}
            </div>
          </div>
          <div style={cardStyle}>
            <strong>Usage Receipt</strong>
            <div className={receipts.length ? "callout success" : "callout warning"} style={{ marginTop: 10 }}>
              {missingAuthorityReason("usage", receipts.length) ?? `已写入 ${receipts.length} 条权威 Usage Receipt。`}
            </div>
          </div>
        </div>
      )}

      {loadState === "loaded" && view === "overview" && (
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
