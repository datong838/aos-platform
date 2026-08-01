/**
 * E2.5 — AIP 可观测性页面（深度完善）
 *
 * 5 Tabs: Overview / Traces / Metrics / Alerts / Dashboards
 * 顶部工具栏：时间范围（1h/6h/24h/7d）+ 刷新 + 自动刷新 + 导出
 *
 * W2-A5：Overview/Traces 优先走 /v1/aip/observability/*；失败降级 MOCK + 演示路径。
 *
 * 纯函数集中在文件顶部（formatXxx / filter / aggregate），便于测试。
 */
import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPut } from "../../api/client";
import { PageChrome } from "../../components/PageChrome";
import { BpBadge } from "../../components/bp";

/* ----------------------------------------------------------------------------
 * 类型
 * ------------------------------------------------------------------------- */
export type ObsTab = "overview" | "traces" | "metrics" | "alerts" | "dashboards";
export type TimeRange = "1h" | "6h" | "24h" | "7d";
export type AlertSeverity = "critical" | "warning" | "info";
export type AlertStatus = "firing" | "acknowledged" | "silenced";

export type KpiCard = {
  key: string;
  label: string;
  value: string;
  deltaPct: number;
  unit: string;
};

export type TrendPoint = {
  t: string;
  requests: number;
  latencyMs: number;
  errors: number;
};

export type TraceRow = {
  traceId: string;
  rootSpan: string;
  service: string;
  durationMs: number;
  status: "ok" | "error";
  spans: number;
  startedAt: string;
};

export type TraceSpan = {
  id: string;
  name: string;
  service: string;
  startMs: number;
  durationMs: number;
  level: number;
  kind: "parent" | "nested" | "ai" | "db";
};

export type MetricSeries = {
  name: string;
  unit: string;
  values: number[];
};

export type AlertRow = {
  id: string;
  name: string;
  severity: AlertSeverity;
  status: AlertStatus;
  firedAt: string;
  value: string;
};

type AlertApiRow = {
  id?: string;
  name?: string;
  status?: string;
  config?: { severity?: string; firedAt?: string; value?: string };
};

export type DashboardWidget = {
  id: string;
  title: string;
  type: "line" | "bar" | "kpi" | "table";
  data: number[];
};

/** live=真实/采样 API；demo=MOCK 演示路径 */
export type ObsDataMode = "live" | "demo" | "loading";

export type ObsSummaryResponse = {
  source?: string;
  range?: string;
  kpis?: Array<Partial<KpiCard> & { key?: string; label?: string; value?: string }>;
  trend?: Array<Partial<TrendPoint>>;
};

export type ObsTracesResponse = {
  source?: string;
  items?: Array<Partial<TraceRow>>;
};

/* ----------------------------------------------------------------------------
 * 纯函数：格式化 / 计算 / 筛选
 * ------------------------------------------------------------------------- */

/**格式化数字：>=1B → x.xx B；>=1M → x.xx M；>=1K → x.x K；否则原样。*/
export function formatCount(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

/**格式化毫秒为人类可读：>=1000 → x.xx s；否则 xxx ms。*/
export function formatDuration(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${Math.round(ms)}ms`;
}

/**百分比格式化，deltaIn 为百分点变化（正负）。*/
export function formatDelta(deltaPct: number): string {
  const sign = deltaPct > 0 ? "+" : "";
  return `${sign}${deltaPct.toFixed(1)}%`;
}

/**根据 delta 方向给出颜色 token：上升为绿色（好）、下降红色（差）、0 灰色。*/
export function deltaTone(deltaPct: number): "up" | "down" | "flat" {
  if (deltaPct > 0.5) return "up";
  if (deltaPct < -0.5) return "down";
  return "flat";
}

/**根据延迟 ms 返回 p95 等级。*/
export function latencyLevel(ms: number): "good" | "warn" | "bad" {
  if (ms <= 200) return "good";
  if (ms <= 800) return "warn";
  return "bad";
}

/**根据错误率（0-1）返回等级。*/
export function errorRateLevel(rate: number): "good" | "warn" | "bad" {
  if (rate <= 0.01) return "good";
  if (rate <= 0.05) return "warn";
  return "bad";
}

/**按关键字过滤追踪行（traceId / rootSpan / service 任一命中）。*/
export function filterTraces(rows: TraceRow[], q: string): TraceRow[] {
  const k = q.trim().toLowerCase();
  if (!k) return rows;
  return rows.filter(
    (r) =>
      r.traceId.toLowerCase().includes(k) ||
      r.rootSpan.toLowerCase().includes(k) ||
      r.service.toLowerCase().includes(k),
  );
}

/**按严重程度过滤告警；severity === "all" 返回全部。*/
export function filterAlerts(rows: AlertRow[], sev: AlertSeverity | "all"): AlertRow[] {
  if (sev === "all") return rows;
  return rows.filter((r) => r.severity === sev);
}

/**聚合告警状态计数。*/
export function countAlertStatus(rows: AlertRow[]): Record<AlertStatus, number> {
  const acc: Record<AlertStatus, number> = { firing: 0, acknowledged: 0, silenced: 0 };
  for (const r of rows) acc[r.status] += 1;
  return acc;
}

/**把 spans 归一化成 0-100 的百分比，用于瀑布图渲染。*/
export function normalizeSpans(spans: TraceSpan[]): TraceSpan[] {
  if (spans.length === 0) return spans;
  const maxEnd = spans.reduce((m, s) => Math.max(m, s.startMs + s.durationMs), 0);
  if (maxEnd <= 0) return spans;
  return spans.map((s) => ({
    ...s,
    startMs: (s.startMs / maxEnd) * 100,
    durationMs: (s.durationMs / maxEnd) * 100,
  }));
}

/**计算趋势序列的平均值（便于 KPI 趋势条）。*/
export function avgTrend(points: TrendPoint[], key: keyof Pick<TrendPoint, "requests" | "latencyMs" | "errors">): number {
  if (points.length === 0) return 0;
  const sum = points.reduce((acc, p) => acc + p[key], 0);
  return sum / points.length;
}

/**将数字序列转成 SVG path（min/max 归一化到 0-height）。*/
export function sparklinePath(values: number[], width = 120, height = 32): string {
  if (values.length === 0) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = values.length > 1 ? width / (values.length - 1) : 0;
  return values
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / range) * height;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

/**时间范围选择 → 按钮可点项。*/
export const TIME_RANGES: TimeRange[] = ["1h", "6h", "24h", "7d"];

/**时间范围 → 估算的数据点数量（用于 mock 趋势）。*/
export function pointsForRange(range: TimeRange): number {
  switch (range) {
    case "1h": return 12;
    case "6h": return 24;
    case "24h": return 48;
    case "7d": return 56;
  }
}

/* ----------------------------------------------------------------------------
 * Mock 数据（可被测试引用，避免硬编码在组件内）
 * ------------------------------------------------------------------------- */
export const MOCK_KPIS: KpiCard[] = [
  { key: "requests", label: "请求量", value: "12.4K", deltaPct: 8.2, unit: "req" },
  { key: "latency", label: "P95 延迟", value: "284ms", deltaPct: -3.1, unit: "ms" },
  { key: "errors", label: "错误率", value: "0.42%", deltaPct: -12.5, unit: "%" },
  { key: "tokens", label: "Token 消耗", value: "2.84M", deltaPct: 15.6, unit: "tok" },
];

export const MOCK_TREND: TrendPoint[] = Array.from({ length: 12 }, (_, i) => ({
  t: `${i * 5}m`,
  requests: 800 + Math.round(Math.sin(i / 2) * 200 + i * 30),
  latencyMs: 220 + Math.round(Math.cos(i / 3) * 60),
  errors: Math.max(0, Math.round((i % 4) - 1)),
}));

export const MOCK_TRACES: TraceRow[] = [
  { traceId: "t_001", rootSpan: "sendEmailWithTaskPriority", service: "aip-functions", durationMs: 12261, status: "ok", spans: 13, startedAt: "10:42:18" },
  { traceId: "t_002", rootSpan: "llm_summarize", service: "llm-router", durationMs: 6012, status: "error", spans: 4, startedAt: "10:41:55" },
  { traceId: "t_003", rootSpan: "query.objects", service: "ontology-api", durationMs: 348, status: "ok", spans: 6, startedAt: "10:41:30" },
  { traceId: "t_004", rootSpan: "buildDecision", service: "decision-engine", durationMs: 1840, status: "ok", spans: 8, startedAt: "10:40:12" },
  { traceId: "t_005", rootSpan: "sendEmail", service: "notify-svc", durationMs: 2450, status: "ok", spans: 3, startedAt: "10:39:44" },
];

export const MOCK_SPANS: TraceSpan[] = [
  { id: "s1", name: "sendEmailWithTaskPriority", service: "aip-functions", startMs: 0, durationMs: 12261, level: 0, kind: "parent" },
  { id: "s2", name: "用户代码", service: "aip-functions", startMs: 490, durationMs: 11650, level: 1, kind: "nested" },
  { id: "s3", name: "关联对象", service: "ontology-api", startMs: 490, durationMs: 1840, level: 1, kind: "db" },
  { id: "s4", name: "函数调用", service: "aip-functions", startMs: 1960, durationMs: 6750, level: 1, kind: "nested" },
  { id: "s5", name: "Claude 3.5", service: "llm-router", startMs: 1960, durationMs: 6000, level: 2, kind: "ai" },
  { id: "s6", name: "sendEmail", service: "notify-svc", startMs: 9180, durationMs: 2450, level: 1, kind: "nested" },
];

export const MOCK_METRICS: MetricSeries[] = [
  { name: "请求量", unit: "req/s", values: [120, 180, 150, 200, 240, 210, 260] },
  { name: "延迟", unit: "ms", values: [220, 280, 240, 300, 260, 320, 284] },
  { name: "Token", unit: "tok/s", values: [4000, 5200, 4800, 5600, 6100, 5800, 6400] },
];

export const MOCK_ALERTS: AlertRow[] = [
  { id: "a1", name: "P95 延迟 > 800ms", severity: "critical", status: "firing", firedAt: "10:44:02", value: "942ms" },
  { id: "a2", name: "错误率 > 5%", severity: "warning", status: "acknowledged", firedAt: "10:40:18", value: "6.1%" },
  { id: "a3", name: "Token 配额 80%", severity: "warning", status: "firing", firedAt: "10:35:55", value: "82%" },
  { id: "a4", name: "Pod 重启", severity: "info", status: "silenced", firedAt: "10:20:11", value: "1 次" },
  { id: "a5", name: "队列积压 > 1000", severity: "critical", status: "acknowledged", firedAt: "10:15:30", value: "1280" },
];

export const MOCK_WIDGETS: DashboardWidget[] = [
  { id: "w1", title: "请求 QPS", type: "line", data: [120, 180, 150, 200, 240, 210] },
  { id: "w2", title: "错误率", type: "kpi", data: [0.42] },
  { id: "w3", title: "服务耗时", type: "bar", data: [320, 180, 240, 120, 410] },
  { id: "w4", title: "Top 调用", type: "table", data: [5, 3, 2, 1] },
];

/**将 summary API 的 kpis 映射为页面 KpiCard；空响应保持真实空态。*/
export function mapSummaryToKpis(res: ObsSummaryResponse | null | undefined): KpiCard[] {
  const items = res?.kpis;
  if (!items || items.length === 0) return [];
  return items.map((k, i) => ({
      key: k.key || `kpi-${i}`,
      label: k.label || "未命名指标",
      value: k.value ?? "0",
      deltaPct: typeof k.deltaPct === "number" ? k.deltaPct : 0,
      unit: k.unit || "",
    }));
}

/**将 summary API 的 trend 映射为 TrendPoint[]。*/
export function mapSummaryToTrend(res: ObsSummaryResponse | null | undefined): TrendPoint[] {
  const items = res?.trend;
  if (!items || items.length === 0) return [];
  return items.map((p, i) => ({
    t: p.t || `${i * 5}m`,
    requests: typeof p.requests === "number" ? p.requests : 0,
    latencyMs: typeof p.latencyMs === "number" ? p.latencyMs : 0,
    errors: typeof p.errors === "number" ? p.errors : 0,
  }));
}

/**将 traces API items 映射为 TraceRow[]。*/
export function mapTraceItems(res: ObsTracesResponse | null | undefined): TraceRow[] {
  const items = res?.items;
  if (!items || items.length === 0) return [];
  return items.map((r, i) => {
    const status = r.status === "error" ? "error" : "ok";
    return {
      traceId: r.traceId || `t_api_${i}`,
      rootSpan: r.rootSpan || "未知路由",
      service: r.service || "aos-api",
      durationMs: typeof r.durationMs === "number" ? r.durationMs : 0,
      status,
      spans: typeof r.spans === "number" ? r.spans : 0,
      startedAt: r.startedAt || "—",
    };
  });
}

export function mapAlertItems(items: AlertApiRow[] | null | undefined): AlertRow[] {
  return (items || []).filter((item) => item.id).map((item) => ({
    id: String(item.id),
    name: String(item.name || "未命名告警"),
    severity: item.config?.severity === "critical" || item.config?.severity === "info" ? item.config.severity : "warning",
    status: item.status === "acknowledged" || item.status === "silenced" ? item.status : "firing",
    firedAt: String(item.config?.firedAt || "—"),
    value: String(item.config?.value || "—"),
  }));
}

export function validateAlertMutation(
  response: { id?: string; status?: string } | null | undefined,
  targetId: string,
  targetStatus: AlertStatus,
): boolean {
  return response?.id === targetId && response.status === targetStatus;
}

export function metricsFromTrend(trend: TrendPoint[]): MetricSeries[] {
  return [
    { name: "请求量", unit: "req", values: trend.map((p) => p.requests) },
    { name: "延迟", unit: "ms", values: trend.map((p) => p.latencyMs) },
    { name: "错误", unit: "count", values: trend.map((p) => p.errors) },
  ];
}

/* ----------------------------------------------------------------------------
 * 组件
 * ------------------------------------------------------------------------- */
export function ObservabilityPage() {
  const [tab, setTab] = useState<ObsTab>("overview");
  const [range, setRange] = useState<TimeRange>("1h");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);
  const [traceQuery, setTraceQuery] = useState("");
  const [kpis, setKpis] = useState<KpiCard[]>([]);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<TraceRow | null>(null);
  const [alerts, setAlerts] = useState<AlertRow[]>([]);
  const [alertFilter, setAlertFilter] = useState<AlertSeverity | "all">("all");
  const [widgets] = useState<DashboardWidget[]>(MOCK_WIDGETS);
  const [tabSources, setTabSources] = useState<Partial<Record<ObsTab, "loading" | "live" | "error" | "demo">>>({ overview: "loading", dashboards: "demo" });
  const [tabErrors, setTabErrors] = useState<Partial<Record<ObsTab, string>>>({});
  const [alertMutation, setAlertMutation] = useState<{ id: string; status: AlertStatus } | null>(null);
  const [alertWriteMsg, setAlertWriteMsg] = useState<string | null>(null);

  // 自动刷新：每 30s 触发一次 tick
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => setRefreshTick((t) => t + 1), 30000);
    return () => clearInterval(id);
  }, [autoRefresh]);

  // 每个 Tab 独立加载；真实空数据不注入 MOCK，一个 Tab 失败不污染其他 Tab。
  useEffect(() => {
    if (tab === "dashboards") return;
    let cancelled = false;
    setTabSources((prev) => ({ ...prev, [tab]: "loading" }));
    setTabErrors((prev) => ({ ...prev, [tab]: undefined }));
    if (tab === "overview" || tab === "metrics") { setKpis([]); setTrend([]); }
    if (tab === "traces") { setTraces([]); setSelectedTrace(null); }
    if (tab === "alerts") setAlerts([]);
    (async () => {
      try {
        if (tab === "overview" || tab === "metrics") {
          const summary = await apiGet<ObsSummaryResponse>(`/v1/aip/observability/summary?range=${encodeURIComponent(range)}`);
          if (cancelled) return;
          setKpis(mapSummaryToKpis(summary));
          setTrend(mapSummaryToTrend(summary));
        } else if (tab === "traces") {
          const tracesRes = await apiGet<ObsTracesResponse>("/v1/aip/observability/traces?limit=20");
          if (cancelled) return;
          const nextTraces = mapTraceItems(tracesRes);
          setTraces(nextTraces);
          setSelectedTrace((prev) => nextTraces.find((t) => t.traceId === prev?.traceId) ?? nextTraces[0] ?? null);
        } else if (tab === "alerts") {
          const alertsRes = await apiGet<AlertApiRow[]>("/api/aip/alerts");
          if (cancelled) return;
          setAlerts(mapAlertItems(alertsRes));
        }
        if (cancelled) return;
        setTabSources((prev) => ({ ...prev, [tab]: "live" }));
      } catch (e) {
        if (cancelled) return;
        if (tab === "overview" || tab === "metrics") { setKpis([]); setTrend([]); }
        if (tab === "traces") { setTraces([]); setSelectedTrace(null); }
        if (tab === "alerts") setAlerts([]);
        setTabSources((prev) => ({ ...prev, [tab]: "error" }));
        setTabErrors((prev) => ({ ...prev, [tab]: e instanceof Error ? e.message : "API 不可用" }));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tab, range, refreshTick]);

  const tabs: { key: ObsTab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "traces", label: "Traces" },
    { key: "metrics", label: "Metrics" },
    { key: "alerts", label: "Alerts" },
    { key: "dashboards", label: "Dashboards" },
  ];

  const filteredTraces = useMemo(() => filterTraces(traces, traceQuery), [traces, traceQuery]);
  const filteredAlerts = useMemo(() => filterAlerts(alerts, alertFilter), [alerts, alertFilter]);
  const alertCounts = useMemo(() => countAlertStatus(alerts), [alerts]);
  const requestsSpark = useMemo(
    () => sparklinePath(trend.map((p) => p.requests)),
    [trend],
  );
  const latencySpark = useMemo(
    () => sparklinePath(trend.map((p) => p.latencyMs)),
    [trend],
  );

  function handleRefresh() {
    setRefreshTick((t) => t + 1);
  }

  function handleExport() {
    const data = tab === "overview" ? { kpis, trend }
      : tab === "traces" ? traces
        : tab === "metrics" ? metricsFromTrend(trend)
          : tab === "alerts" ? alerts
            : widgets;
    const blob = { tab, range, source: tabSources[tab] === "live" ? "live" : "demo", generatedAt: new Date().toISOString(), data };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(blob, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `observability-${tab}-${range}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function updateAlert(id: string, status: AlertStatus) {
    if (alertMutation) return;
    setAlertMutation({ id, status });
    setAlertWriteMsg(null);
    try {
      const updated = await apiPut<AlertApiRow>(`/api/aip/alerts/${encodeURIComponent(id)}`, { status });
      if (!validateAlertMutation(updated, id, status)) throw new Error("告警写回响应与目标不一致");
      let reread: AlertApiRow[];
      try {
        reread = await apiGet<AlertApiRow[]>("/api/aip/alerts");
      } catch (e) {
        setAlertWriteMsg(`写入已提交但重读核验失败：${String((e as Error).message || e)}`);
        return;
      }
      const next = mapAlertItems(reread);
      if (!next.some((item) => item.id === id && item.status === status)) {
        setAlertWriteMsg("写入已提交但重读核验失败：服务端状态不一致");
        return;
      }
      setAlerts(next);
      setAlertWriteMsg(status === "acknowledged" ? "告警已确认并完成重读核验" : "告警已静默并完成重读核验");
    } catch (e) {
      setAlertWriteMsg(`告警写入失败：${String((e as Error).message || e)}`);
    } finally {
      setAlertMutation(null);
    }
  }

  return (
    <PageChrome title="AIP 可观测性" lede="Overview · Traces · Metrics · Alerts · Dashboards">
      {tabSources[tab] === "error" && (
        <div className="obs-source-banner obs-source-banner--demo" role="alert" data-testid={`obs-source-error-${tab}`}>
          <span className="obs-source-badge obs-source-badge--demo">加载失败</span>
          <span className="obs-source-banner__text">{tab} 数据不可用：{tabErrors[tab]}</span>
        </div>
      )}
      {tabSources[tab] === "live" && (
        <div className="obs-source-banner obs-source-banner--live" role="status" data-testid="obs-source-live">
          <span className="obs-source-badge obs-source-badge--live">真实 API</span>
          <span className="obs-source-banner__text">{tab} · 进程采样数据；Trace 仅为采样路由统计，Token 为估算，趋势为采样推演</span>
        </div>
      )}
      {tab === "dashboards" && <div role="status">演示目录 · Dashboard Widget 持久化契约规划中</div>}

      {/* 顶部工具栏 */}
      <Toolbar
        range={range}
        onRangeChange={setRange}
        autoRefresh={autoRefresh}
        onToggleAuto={() => setAutoRefresh((v) => !v)}
        onRefresh={handleRefresh}
        onExport={handleExport}
        tick={refreshTick}
      />

      {/* Tab 栏 */}
      <div style={{ display: "flex", gap: 24, borderBottom: "1px solid var(--aos-border)", paddingLeft: 4 }}>
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            data-testid={`obs-tab-${t.key}`}
            style={{
              padding: "10px 0",
              fontSize: 13,
              fontWeight: tab === t.key ? 500 : 400,
              border: "none",
              borderBottom: tab === t.key ? "2px solid var(--aos-indigo-600)" : "2px solid transparent",
              background: "none",
              color: tab === t.key ? "var(--aos-indigo-600)" : "var(--aos-muted)",
              cursor: "pointer",
              marginBottom: "-1px",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab 内容 */}
      {tab === "overview" && (
        <OverviewPanel
          kpis={kpis}
          requestsSpark={requestsSpark}
          latencySpark={latencySpark}
        />
      )}
      {tab === "traces" && (
        <TracesPanel
          traces={filteredTraces}
          query={traceQuery}
          onQuery={setTraceQuery}
          selected={selectedTrace}
          onSelect={setSelectedTrace}
          spans={[]}
        />
      )}
      {tab === "metrics" && <MetricsPanel series={metricsFromTrend(trend)} />}
      {tab === "alerts" && (
        <AlertsPanel
          alerts={filteredAlerts}
          filter={alertFilter}
          onFilter={setAlertFilter}
          counts={alertCounts}
          onUpdate={updateAlert}
          mutation={alertMutation}
        />
      )}
      {tab === "alerts" && alertWriteMsg && <p role="status">{alertWriteMsg}</p>}
      {tab === "dashboards" && (
        <DashboardsPanel widgets={widgets} />
      )}
    </PageChrome>
  );
}

/* ----------------------------------------------------------------------------
 * 子组件：顶部工具栏
 * ------------------------------------------------------------------------- */
function Toolbar(props: {
  range: TimeRange;
  onRangeChange: (r: TimeRange) => void;
  autoRefresh: boolean;
  onToggleAuto: () => void;
  onRefresh: () => void;
  onExport: () => void;
  tick: number;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "10px 4px",
        borderBottom: "1px solid var(--aos-gray-100)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        {TIME_RANGES.map((r) => (
          <button
            key={r}
            type="button"
            onClick={() => props.onRangeChange(r)}
            data-testid={`range-${r}`}
            style={{
              padding: "4px 10px",
              fontSize: 12,
              borderRadius: 2,
              border: props.range === r ? "1px solid var(--aos-indigo-600)" : "1px solid var(--aos-border)",
              background: props.range === r ? "var(--aos-indigo-bg)" : "var(--aos-surface)",
              color: props.range === r ? "var(--aos-indigo-600)" : "var(--aos-muted)",
              cursor: "pointer",
              fontWeight: props.range === r ? 500 : 400,
            }}
          >
            {r}
          </button>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 11, color: "var(--aos-muted)" }} data-testid="refresh-tick">
          tick #{props.tick}
        </span>
        <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "var(--aos-muted)", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={props.autoRefresh}
            onChange={props.onToggleAuto}
            data-testid="auto-refresh-toggle"
          />
          自动刷新
        </label>
        <button
          type="button"
          onClick={props.onRefresh}
          data-testid="btn-refresh"
          style={btnSecondary}
        >
          刷新
        </button>
        <button
          type="button"
          onClick={props.onExport}
          data-testid="btn-export"
          style={btnPrimary}
        >
          导出
        </button>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------------------
 * Overview Panel
 * ------------------------------------------------------------------------- */
function OverviewPanel(props: {
  kpis: KpiCard[];
  requestsSpark: string;
  latencySpark: string;
}) {
  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
      {props.kpis.length === 0 && <p data-testid="observability-empty">当前时间范围暂无概览数据</p>}
      {/* KPI 卡片 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        {props.kpis.map((k) => {
          const tone = deltaTone(k.deltaPct);
          return (
            <div
              key={k.key}
              data-testid={`kpi-${k.key}`}
              style={{
                background: "var(--aos-surface)",
                border: "1px solid var(--aos-border)",
                borderRadius: 2,
                padding: 14,
              }}
            >
              <div style={{ fontSize: 12, color: "var(--aos-muted)" }}>{k.label}</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 6 }}>
                <span style={{ fontSize: 22, fontWeight: 600, color: "var(--aos-text)" }}>{k.value}</span>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 500,
                    color: tone === "up" ? "var(--aos-green-600)" : tone === "down" ? "var(--aos-red)" : "var(--aos-text-tertiary)",
                  }}
                >
                  {formatDelta(k.deltaPct)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* 趋势线 + 拓扑 */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
        <Panel title="实时趋势 · 请求量 / 延迟">
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <Sparkline svg={props.requestsSpark} color="var(--aos-indigo-600)" label="requests" />
            <Sparkline svg={props.latencySpark} color="var(--color-info)" label="latency" />
          </div>
        </Panel>
        <Panel title="服务拓扑">
          <ServiceTopology />
        </Panel>
      </div>
    </div>
  );
}

function Sparkline(props: { svg: string; color: string; label: string }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--aos-muted)", marginBottom: 4 }}>{props.label}</div>
      <svg viewBox="0 0 120 32" width="100%" height={32} aria-label={props.label}>
        <path d={props.svg} fill="none" stroke={props.color} strokeWidth={1.5} />
      </svg>
    </div>
  );
}

function ServiceTopology() {
  const nodes = [
    { id: "api", x: 50, y: 20, label: "API" },
    { id: "router", x: 20, y: 60, label: "LLM Router" },
    { id: "func", x: 80, y: 60, label: "Functions" },
    { id: "ontology", x: 50, y: 100, label: "Ontology" },
  ];
  const edges = [
    { from: "api", to: "router" },
    { from: "api", to: "func" },
    { from: "func", to: "ontology" },
    { from: "router", to: "ontology" },
  ];
  const findNode = (id: string) => nodes.find((n) => n.id === id)!;
  return (
    <svg viewBox="0 0 100 120" width="100%" height={120} aria-label="service topology">
      {edges.map((e, i) => {
        const a = findNode(e.from);
        const b = findNode(e.to);
        return (
          <line
            key={i}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="var(--aos-border-strong)"
            strokeWidth={0.6}
          />
        );
      })}
      {nodes.map((n) => (
        <g key={n.id}>
          <circle cx={n.x} cy={n.y} r={6} fill="var(--aos-indigo-600)" />
          <text x={n.x} y={n.y + 12} fontSize={5} fill="var(--aos-text-secondary)" textAnchor="middle">
            {n.label}
          </text>
        </g>
      ))}
    </svg>
  );
}

/* ----------------------------------------------------------------------------
 * Traces Panel
 * ------------------------------------------------------------------------- */
function TracesPanel(props: {
  traces: TraceRow[];
  query: string;
  onQuery: (q: string) => void;
  selected: TraceRow | null;
  onSelect: (t: TraceRow) => void;
  spans: TraceSpan[];
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, padding: 16 }}>
      <input
        type="text"
        value={props.query}
        onChange={(e) => props.onQuery(e.target.value)}
        placeholder="搜索 trace_id / span / 服务..."
        data-testid="trace-search"
        style={{
          padding: "8px 12px",
          fontSize: 13,
          border: "1px solid var(--aos-border)",
          borderRadius: 2,
          outline: "none",
        }}
      />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {/* 列表 */}
        <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr>
                {["Trace ID", "Root Span", "服务", "耗时", "状态"].map((h) => (
                  <th key={h} style={thStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {props.traces.length === 0 && <tr><td colSpan={5} style={tdStyle}>暂无采样路由统计</td></tr>}
              {props.traces.map((t) => (
                <tr
                  key={t.traceId}
                  onClick={() => props.onSelect(t)}
                  data-testid={`trace-row-${t.traceId}`}
                  style={{
                    cursor: "pointer",
                    background: props.selected?.traceId === t.traceId ? "var(--aos-indigo-bg)" : "var(--aos-surface)",
                  }}
                >
                  <td style={tdMonoStyle}>{t.traceId}</td>
                  <td style={tdStyle}>{t.rootSpan}</td>
                  <td style={tdStyle}>{t.service}</td>
                  <td style={tdStyle}>{formatDuration(t.durationMs)}</td>
                  <td style={tdStyle}>
                    <BpBadge variant={t.status === "ok" ? "success" : "danger"} size="sm">
                      {t.status === "ok" ? "OK" : "ERR"}
                    </BpBadge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* 瀑布图 */}
        <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8 }}>
            {props.selected ? `${props.selected.traceId} · ${formatDuration(props.selected.durationMs)}` : "选择一条 trace"}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <p style={{ fontSize: 12, color: "var(--aos-muted)" }}>Span 明细 API 未提供，瀑布图不可用。</p>
            {props.spans.map((s) => (
              <div key={s.id} style={{ display: "flex", alignItems: "center", paddingLeft: s.level * 12 }}>
                <span style={{ width: 120, fontSize: 11, color: s.kind === "ai" ? "var(--color-info)" : "var(--aos-text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {s.name}
                </span>
                <div style={{ flex: 1, height: 18, position: "relative" }}>
                  <div
                    style={{
                      position: "absolute",
                      left: `${s.startMs}%`,
                      width: `${s.durationMs}%`,
                      height: "100%",
                      borderRadius: 3,
                      background: spanColor(s.kind),
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function spanColor(kind: TraceSpan["kind"]): string {
  switch (kind) {
    case "ai": return "linear-gradient(90deg, var(--color-info), var(--color-info))";
    case "db": return "var(--aos-accent-border)";
    case "parent": return "var(--aos-border)";
    default: return "var(--aos-border-strong)";
  }
}

/* ----------------------------------------------------------------------------
 * Metrics Panel
 * ------------------------------------------------------------------------- */
function MetricsPanel(props: { series: MetricSeries[] }) {
  const [selected, setSelected] = useState(props.series[0]?.name ?? "");
  const active = props.series.find((s) => s.name === selected) ?? props.series[0];
  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 8 }}>
        {props.series.map((s) => (
          <button
            key={s.name}
            type="button"
            onClick={() => setSelected(s.name)}
            data-testid={`metric-${s.name}`}
            style={{
              padding: "6px 12px",
              fontSize: 12,
              borderRadius: 2,
              border: selected === s.name ? "1px solid var(--aos-indigo-600)" : "1px solid var(--aos-border)",
              background: selected === s.name ? "var(--aos-indigo-bg)" : "var(--aos-surface)",
              color: selected === s.name ? "var(--aos-indigo-600)" : "var(--aos-muted)",
              cursor: "pointer",
            }}
          >
            {s.name}
          </button>
        ))}
      </div>
      {active && active.values.length > 0 ? (
        <Panel title={`${active.name} · ${active.unit}`}>
          <BarChart values={active.values} />
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11, color: "var(--aos-muted)" }}>
            <span>min: {Math.min(...active.values)}</span>
            <span>max: {Math.max(...active.values)}</span>
            <span>avg: {Math.round(active.values.reduce((a, b) => a + b, 0) / active.values.length)}</span>
          </div>
        </Panel>
      ) : <p data-testid="metrics-empty">当前时间范围暂无采样指标</p>}
    </div>
  );
}

function BarChart(props: { values: number[] }) {
  const max = Math.max(...props.values, 1);
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 120 }}>
      {props.values.map((v, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            height: `${(v / max) * 100}%`,
            background: "linear-gradient(180deg, var(--aos-indigo-600), var(--aos-indigo-600))",
            borderRadius: 3,
          }}
        />
      ))}
    </div>
  );
}

/* ----------------------------------------------------------------------------
 * Alerts Panel
 * ------------------------------------------------------------------------- */
function AlertsPanel(props: {
  alerts: AlertRow[];
  filter: AlertSeverity | "all";
  onFilter: (s: AlertSeverity | "all") => void;
  counts: Record<AlertStatus, number>;
  onUpdate: (id: string, status: AlertStatus) => void;
  mutation: { id: string; status: AlertStatus } | null;
}) {
  const filters: (AlertSeverity | "all")[] = ["all", "critical", "warning", "info"];
  const labelOf = (f: AlertSeverity | "all") => (f === "all" ? "全部" : f === "critical" ? "严重" : f === "warning" ? "警告" : "信息");
  const variantOf = (s: AlertSeverity) => (s === "critical" ? "danger" : s === "warning" ? "warning" : "info");
  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      {/* 概览 */}
      <div style={{ display: "flex", gap: 12 }}>
        <Stat label="触发中" value={props.counts.firing} tone="danger" />
        <Stat label="已确认" value={props.counts.acknowledged} tone="warning" />
        <Stat label="已静默" value={props.counts.silenced} tone="default" />
      </div>

      {/* 筛选 */}
      <div style={{ display: "flex", gap: 4 }}>
        {filters.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => props.onFilter(f)}
            data-testid={`alert-filter-${f}`}
            style={{
              padding: "4px 10px",
              fontSize: 12,
              borderRadius: 2,
              border: props.filter === f ? "1px solid var(--aos-indigo-600)" : "1px solid var(--aos-border)",
              background: props.filter === f ? "var(--aos-indigo-bg)" : "var(--aos-surface)",
              color: props.filter === f ? "var(--aos-indigo-600)" : "var(--aos-muted)",
              cursor: "pointer",
            }}
          >
            {labelOf(f)}
          </button>
        ))}
      </div>

      {/* 列表 */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {props.alerts.length === 0 && <p data-testid="alerts-empty">暂无告警</p>}
        {props.alerts.map((a) => (
          <div
            key={a.id}
            data-testid={`alert-${a.id}`}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 12px",
              background: "var(--aos-surface)",
              border: "1px solid var(--aos-border)",
              borderRadius: 2,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <BpBadge variant={variantOf(a.severity)} size="sm">{labelOf(a.severity)}</BpBadge>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)" }}>{a.name}</div>
                <div style={{ fontSize: 11, color: "var(--aos-muted)" }}>
                  {a.firedAt} · 当前值 {a.value}
                </div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 4 }}>
              <button type="button" data-testid={`ack-${a.id}`} disabled={Boolean(props.mutation) || a.status === "acknowledged"} onClick={() => props.onUpdate(a.id, "acknowledged")} style={btnXS}>确认</button>
              <button type="button" data-testid={`silence-${a.id}`} disabled={Boolean(props.mutation) || a.status === "silenced"} onClick={() => props.onUpdate(a.id, "silenced")} style={btnXS}>静默</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Stat(props: { label: string; value: number; tone: "danger" | "warning" | "default" }) {
  const color = props.tone === "danger" ? "var(--aos-red)" : props.tone === "warning" ? "var(--aos-amber-600)" : "var(--aos-muted)";
  return (
    <div style={{ flex: 1, background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 12 }}>
      <div style={{ fontSize: 11, color: "var(--aos-muted)" }}>{props.label}</div>
      <div style={{ fontSize: 20, fontWeight: 600, color }}>{props.value}</div>
    </div>
  );
}

/* ----------------------------------------------------------------------------
 * Dashboards Panel
 * ------------------------------------------------------------------------- */
function DashboardsPanel(props: { widgets: DashboardWidget[] }) {
  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>自定义仪表盘</h3>
        <button type="button" disabled title="持久化契约规划中" data-testid="btn-add-widget" style={{ ...btnPrimary, cursor: "not-allowed", opacity: 0.55 }}>
          + 添加 Widget（规划中）
        </button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
        {props.widgets.map((w) => (
          <Panel key={w.id} title={w.title}>
            {w.type === "kpi" ? (
              <div style={{ fontSize: 28, fontWeight: 600 }}>{w.data[0]}</div>
            ) : w.type === "table" ? (
              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12 }}>
                {w.data.map((v, i) => (
                  <li key={i}>row {i + 1}: {v}</li>
                ))}
              </ul>
            ) : (
              <BarChart values={w.data} />
            )}
          </Panel>
        ))}
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------------------
 * 共享小组件 + style 常量
 * ------------------------------------------------------------------------- */
function Panel(props: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 12 }}>
      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8 }}>{props.title}</div>
      {props.children}
    </div>
  );
}

const btnPrimary: React.CSSProperties = {
  padding: "6px 12px",
  fontSize: 12,
  fontWeight: 500,
  color: "var(--text-on-brand)",
  background: "var(--aos-indigo-600)",
  border: "none",
  borderRadius: 2,
  cursor: "pointer",
};

const btnSecondary: React.CSSProperties = {
  padding: "6px 12px",
  fontSize: 12,
  color: "var(--aos-text)",
  background: "var(--aos-surface)",
  border: "1px solid var(--aos-border)",
  borderRadius: 2,
  cursor: "pointer",
};

const btnXS: React.CSSProperties = {
  padding: "3px 8px",
  fontSize: 11,
  color: "var(--aos-indigo-600)",
  background: "var(--aos-indigo-bg)",
  border: "none",
  borderRadius: 4,
  cursor: "pointer",
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 10px",
  background: "var(--aos-surface-hover)",
  borderBottom: "1px solid var(--aos-border)",
  fontWeight: 500,
  color: "var(--aos-muted)",
  fontSize: 11,
};

const tdStyle: React.CSSProperties = {
  padding: "8px 10px",
  borderBottom: "1px solid var(--aos-gray-100)",
  color: "var(--aos-text)",
  fontSize: 12,
};

const tdMonoStyle: React.CSSProperties = {
  ...tdStyle,
  fontFamily: "monospace",
};
