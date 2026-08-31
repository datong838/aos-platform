import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { aipEvidenceSdk } from "../../api/aipEvidence";
import { aipActionsSdk, type ActionDraftBundle } from "../../api/aipActions";
import { listAssistSubjects, type AssistSubjectOption } from "../../api/aipWorkbench";
import { LINEAGE_ROOT_TYPES, type EvidenceQuality, type LineageRootType, type TelemetrySpan, type UsageReceipt } from "../../api/aipEvidence/contracts";
import { PageChrome } from "../../components/PageChrome";
import { actionDisplayName, businessDisplayName, statusDisplayName } from "../../lib/aipChineseLabels";

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

function qualityLabel(quality: EvidenceQuality): string {
  return quality === "measured" ? "权威实测" : quality === "estimated" ? "估算证据" : "质量待核验";
}

function spanKindLabel(kind: TelemetrySpan["kind"]): string {
  return ({ internal: "内部处理", server: "服务端处理", client: "客户端调用", producer: "生产者", consumer: "消费者", model: "模型调用", tool: "工具调用" } as Record<string, string>)[kind] || kind;
}

function spanStatusLabel(status: TelemetrySpan["status"]): string {
  return status === "ok" ? "成功" : status === "error" ? "错误" : "状态未设置";
}

function usageKindLabel(kind: UsageReceipt["usageKind"]): string {
  return ({ input_token: "输入 Token", output_token: "输出 Token", cached_token: "缓存 Token", cost: "调用成本", latency: "调用时延", tool_unit: "工具计量单位" } as Record<string, string>)[kind] || kind;
}

function spanBusinessName(name: string): string {
  const labels: Record<string, string> = { "model.invoke": "模型生成", "tool.call": "业务工具调用", "queue.wait": "队列等待", retry: "执行重试" };
  return labels[name.toLowerCase()] || businessDisplayName(name, name);
}

export function ObservabilityPage() {
  const deepLink = useMemo(() => parseObservabilityDeepLink(window.location.search), []);
  const [lineageId, setLineageId] = useState(deepLink.lineageId);
  const [rootContext, setRootContext] = useState<{ rootType: LineageRootType; rootId: string } | null>(deepLink.rootType ? { rootType: deepLink.rootType, rootId: deepLink.rootId } : null);
  const [spans, setSpans] = useState<TelemetrySpan[]>([]);
  const [receipts, setReceipts] = useState<UsageReceipt[]>([]);
  const [recentActions, setRecentActions] = useState<ActionDraftBundle[]>([]);
  const [recentRuns, setRecentRuns] = useState<AssistSubjectOption[]>([]);
  const [selectionType, setSelectionType] = useState<"task_run" | "action">("task_run");
  const [selectionId, setSelectionId] = useState("");
  const [selectionState, setSelectionState] = useState<"loading" | "loaded" | "error">("loading");
  const [view, setView] = useState<View>("overview");
  const [query, setQuery] = useState("");
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);

  const summary = useMemo(() => summarizeAuthority(spans, receipts), [spans, receipts]);
  const filteredSpans = useMemo(() => filterAuthoritySpans(spans, query), [spans, query]);
  const retrySpans = useMemo(() => spans.filter((span) => span.name.toLowerCase().includes("retry")), [spans]);
  const queueSpans = useMemo(() => spans.filter((span) => span.name.toLowerCase().includes("queue")), [spans]);
  const tokenReceipts = useMemo(() => receipts.filter((receipt) => receipt.usageKind.includes("token")), [receipts]);
  const costReceipts = useMemo(() => receipts.filter((receipt) => receipt.usageKind === "cost"), [receipts]);

  useEffect(() => {
    let active = true;
    void Promise.all([aipActionsSdk.list(30), listAssistSubjects(30)]).then(([actions, runs]) => {
      if (!active) return;
      setRecentActions(actions.items);
      setRecentRuns(runs.items);
      setSelectionState("loaded");
    }).catch(() => {
      if (!active) return;
      setRecentActions([]);
      setRecentRuns([]);
      setSelectionState("error");
    });
    return () => { active = false; };
  }, []);

  const load = useCallback(async (requestedLineageId?: string) => {
    const target = (requestedLineageId ?? lineageId).trim();
    if (!target) {
      setError("请输入真实谱系标识");
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

  const loadFromBusinessRecord = useCallback(async () => {
    const target = selectionId.trim();
    if (!target) {
      setError("请选择真实任务运行或受控动作");
      return;
    }
    setError(null);
    setSpans([]);
    setReceipts([]);
    setLoadState("loading");
    try {
      const chain = await aipEvidenceSdk.evidenceChain(selectionType, target);
      if (!chain.lineageId) {
        setLineageId("");
        setRootContext({ rootType: selectionType, rootId: target });
        setLoadState("loaded");
        return;
      }
      setLineageId(chain.lineageId);
      setRootContext({ rootType: selectionType, rootId: target });
      setSpans(chain.spans);
      setReceipts(chain.usageReceipts);
      setLoadState("loaded");
    } catch (caught) {
      setError(String((caught as Error).message || caught));
      setLoadState("error");
    }
  }, [selectionId, selectionType]);

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
      root: rootContext,
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
    <PageChrome title="运行可观测性" lede="按真实决策谱系查询调用轨迹与用量凭证；不推算趋势，不回填演示数据。">
      <div
        data-testid="observability-ops-stats"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 12 }}
      >
        {[
          { label: "加载态", value: loadState === "loaded" ? "已载" : loadState === "loading" ? "读取中" : loadState === "error" ? "失败" : "空闲" },
          { label: "视图", value: view === "overview" ? "概览" : view === "spans" ? "调用轨迹" : "用量凭证" },
          { label: "调用轨迹", value: loadState !== "loaded" ? "—" : spans.length ? String(spans.length) : "缺证" },
          { label: "用量凭证", value: loadState !== "loaded" ? "—" : receipts.length ? String(receipts.length) : "缺证" },
          { label: "筛选命中", value: loadState !== "loaded" ? "—" : spans.length ? String(filteredSpans.length) : "缺证" },
          { label: "谱系来源", value: rootContext ? "业务记录" : lineageId.trim() ? "高级定位" : "待选择" },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{s.value}</div>
          </div>
        ))}
      </div>
      <section className="bp5-card" style={{ ...cardStyle, marginBottom: 12 }} data-testid="observability-business-selector">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <div><strong>选择要诊断的业务运行</strong><div className="muted" style={{ marginTop: 4 }}>从真实任务运行或受控动作解析服务端 exact lineageId，不接受前端猜测。</div></div>
          <span className="muted">{selectionState === "loading" ? "读取中…" : selectionState === "error" ? "最近记录读取失败，可使用高级定位" : `任务运行 ${recentRuns.length} 条 · 受控动作 ${recentActions.length} 条`}</span>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <select aria-label="observability-task-run-record" value={selectionType === "task_run" ? selectionId : ""} onChange={(event) => { setSelectionType("task_run"); setSelectionId(event.target.value); }} style={{ minWidth: "min(26rem, 100%)", flex: "1 1 22rem" }}>
            <option value="">请选择最近任务运行</option>
            {recentRuns.map((item) => <option key={item.subject.taskRunRef.resourceId} value={item.subject.taskRunRef.resourceId}>{item.taskTitle} · {statusDisplayName(item.runStatus)} · {item.owner}</option>)}
          </select>
          <select aria-label="observability-action-record" value={selectionType === "action" ? selectionId : ""} onChange={(event) => { setSelectionType("action"); setSelectionId(event.target.value); }} style={{ minWidth: "min(26rem, 100%)", flex: "1 1 22rem" }}>
            <option value="">请选择最近受控动作</option>
            {recentActions.map((item) => <option key={item.proposal.id} value={item.proposal.id}>{actionDisplayName(item.proposal.actionType.actionTypeId)} · {item.proposal.purpose} · {statusDisplayName(item.proposal.status)}</option>)}
          </select>
          <button type="button" className="btn primary" onClick={() => void loadFromBusinessRecord()} disabled={loadState === "loading" || !selectionId.trim()}>{loadState === "loading" ? "读取中…" : "查看运行证据"}</button>
        </div>
      </section>
      <details className="bp5-card" style={{ ...cardStyle, marginBottom: 12 }} data-testid="observability-advanced-locator">
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>高级定位：exact lineageId</summary>
      <div style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap", marginTop: 12 }}>
        <label style={{ display: "grid", gap: 6, minWidth: 320 }}>
          <span className="muted">谱系标识</span>
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
              ? "导出当前已读取的调用轨迹与用量凭证 JSON"
              : "请先读取权威证据后再导出；空闲/失败态不提供演示文件"
          }
        >
          {loadState === "loaded" ? "导出当前证据" : "导出（需先读取）"}
        </button>
        {rootContext && (
          <Link
            className="btn"
            to={`/aip/lineage?rootType=${encodeURIComponent(rootContext.rootType)}&rootId=${encodeURIComponent(rootContext.rootId)}`}
            data-testid="observability-back-lineage"
            style={{ textDecoration: "none" }}
          >
            返回 exact 谱系 →
          </Link>
        )}
      </div>
      </details>

      <div style={{ display: "flex", gap: 8, margin: "16px 0" }}>
        {(["overview", "spans", "usage"] as const).map((item) => (
          <button key={item} type="button" className={`btn ${view === item ? "primary" : ""}`} onClick={() => setView(item)} data-testid={`obs-tab-${item}`}>
            {item === "overview" ? "概览" : item === "spans" ? "调用轨迹" : "用量凭证"}
          </button>
        ))}
      </div>

      {loadState === "idle" && !error && <div data-testid="observability-idle" className="callout info">请输入真实谱系标识。页面不会显示固定调用链、合成趋势或推算用量。</div>}
      {loadState === "loaded" && spans.length === 0 && receipts.length === 0 && <div data-testid="observability-empty" className="callout warning">该决策谱系暂无权威运行片段或用量凭证。</div>}
      {error && <div data-testid="observability-error" className="callout warning">权威可观测性读取失败：{error}</div>}

      {loadState === "loaded" && (
        <div data-testid="observability-evidence-status" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: 12, marginBottom: 14 }}>
          <div style={cardStyle}>
            <strong>运行片段</strong>
            <div className={spans.length ? "callout success" : "callout warning"} style={{ marginTop: 10 }}>
              {missingAuthorityReason("span", spans.length) ?? `已写入 ${spans.length} 条权威 Span。`}
            </div>
          </div>
          <div style={cardStyle}>
            <strong>用量凭证</strong>
            <div className={receipts.length ? "callout success" : "callout warning"} style={{ marginTop: 10 }}>
              {missingAuthorityReason("usage", receipts.length) ?? `已写入 ${receipts.length} 条权威用量凭证。`}
            </div>
          </div>
        </div>
      )}

      {loadState === "loaded" && view === "overview" && (
        <div data-testid="observability-authority-summary">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
            {[
              ["运行步骤", spans.length ? summary.spanCount : "缺证"],
              ["错误步骤", spans.length ? summary.errorSpanCount : "缺证"],
              ["执行重试", spans.length ? retrySpans.length : "缺证"],
              ["队列等待", spans.length ? queueSpans.length : "缺证"],
              ["Token 凭证", receipts.length ? tokenReceipts.length : "缺证"],
              ["成本凭证", receipts.length ? costReceipts.length : "缺证"],
            ].map(([label, value]) => <div key={label} style={cardStyle}><div className="muted">{label}</div><strong style={{ fontSize: 28 }}>{value}</strong></div>)}
          </div>
          <div className="callout info" style={{ marginTop: 14 }}>所有数量均由当前权威回包直接计数；未知用量保持 unknown，不折算为 0。</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 12, marginTop: 14 }} data-testid="observability-operating-meaning">
            <div style={cardStyle}><strong>预算约束</strong><p className="muted">当前 lineage 回包未包含预算快照，因此不展示余额或消耗比例。</p><Link to="/aip/capacity">到容量与预算核对 →</Link></div>
            <div style={cardStyle}><strong>告警处置</strong><p className="muted">仅错误 Span 不能冒充业务告警；需到告警 authority 读取关联对象后处置。</p><Link to="/workshop/inbox">进入风险告警管理 →</Link></div>
            <div style={cardStyle}><strong>质量与问题</strong><p className="muted">从同一业务记录进入评测和草稿审批，保留问题整改上下文。</p><Link to={rootContext ? `/aip/evals?rootType=${encodeURIComponent(rootContext.rootType)}&rootId=${encodeURIComponent(rootContext.rootId)}` : "/aip/evals"}>查看评测与问题 →</Link></div>
          </div>
        </div>
      )}

      {loadState === "loaded" && view === "spans" && (
        <section style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", marginBottom: 10 }}>
            <strong>调用遥测轨迹（{filteredSpans.length}/{spans.length}）</strong>
            <input aria-label="span-filter" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="过滤 trace / span / provider" />
          </div>
          {spans.length === 0 ? <div className="muted">暂无权威运行片段。</div> : (
            <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr><th style={thStyle}>业务步骤</th><th style={thStyle}>执行方</th><th style={thStyle}>类型 / 状态</th><th style={thStyle}>时长</th><th style={thStyle}>质量</th><th style={thStyle}>观测时间</th><th style={thStyle}>审计详情</th></tr></thead>
              <tbody>{filteredSpans.map((span) => <tr key={span.spanRecordId}>
                <td style={tdStyle}>{spanBusinessName(span.name)}</td><td style={tdStyle}>{businessDisplayName(span.provider, span.provider)}</td>
                <td style={tdStyle}>{spanKindLabel(span.kind)} / {spanStatusLabel(span.status)}</td><td style={tdStyle}>{formatSpanDuration(span)}</td>
                <td style={{ ...tdStyle, color: qualityTone(span.quality) }}>{qualityLabel(span.quality)}</td><td style={tdStyle}>{new Date(span.observedAt).toLocaleString()}</td>
                <td style={tdStyle}><details><summary>技术标识</summary><code style={{ overflowWrap: "anywhere" }}>trace={span.traceId}<br />span={span.spanId}<br />receipt={span.providerReceiptId}</code></details></td>
              </tr>)}</tbody>
            </table></div>
          )}
        </section>
      )}

      {loadState === "loaded" && view === "usage" && (
        <section style={cardStyle}>
          <strong>用量凭证（{receipts.length}）</strong>
          {receipts.length === 0 ? <div className="muted" style={{ marginTop: 10 }}>暂无权威用量凭证。</div> : (
            <div style={{ overflowX: "auto", marginTop: 10 }}><table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr><th style={thStyle}>业务计量</th><th style={thStyle}>数量</th><th style={thStyle}>执行方</th><th style={thStyle}>质量</th><th style={thStyle}>观测时间</th><th style={thStyle}>审计详情</th></tr></thead>
              <tbody>{receipts.map((receipt) => <tr key={receipt.receiptId}>
                <td style={tdStyle}>{usageKindLabel(receipt.usageKind)}</td><td style={tdStyle}>{formatUsageQuantity(receipt)}</td><td style={tdStyle}>{businessDisplayName(receipt.provider, receipt.provider)}</td>
                <td style={{ ...tdStyle, color: qualityTone(receipt.quality) }}>{qualityLabel(receipt.quality)}</td><td style={tdStyle}>{new Date(receipt.observedAt).toLocaleString()}</td>
                <td style={tdStyle}><details><summary>技术标识</summary><code style={{ overflowWrap: "anywhere" }}>receipt={receipt.receiptId}<br />providerReceipt={receipt.providerReceiptId}</code></details></td>
              </tr>)}</tbody>
            </table></div>
          )}
        </section>
      )}
    </PageChrome>
  );
}
