import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "../../api/client";
import {
  BpBanner,
  BpMetricGrid,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./blueprintUi";
import { S2Chrome, useJsonGet } from "./shared";

// ── Types ──────────────────────────────────────────────────────

export type Severity = "critical" | "warning" | "info";

export type RuleStatus = "passing" | "failing" | "paused" | "error";

export type QualityRule = {
  id: string;
  name: string;
  type: "completeness" | "uniqueness" | "validity" | "consistency" | "timeliness";
  target: string;
  status: RuleStatus;
  lastCheckedAt: string;
  threshold: number;
  actual: number;
};

export type HealthIssue = {
  id: string;
  severity: Severity;
  table: string;
  column: string;
  message: string;
  detectedAt: string;
  ruleId?: string;
  pipelineId?: string;
};

export type TrendPoint = {
  date: string;
  score: number;
};

export type HealthSummary = {
  overallScore: number;
  completeness: number;
  consistency: number | null;
  timeliness: number;
  totalRules: number;
  passingRules: number;
  openIssues: number;
  criticalIssues: number;
  rules: QualityRule[];
  issues: HealthIssue[];
  trend: TrendPoint[];
};

// ── Constants ──────────────────────────────────────────────────

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "严重",
  warning: "警告",
  info: "提示",
};

export const SEVERITY_TONE: Record<Severity, "bad" | "warn" | "muted"> = {
  critical: "bad",
  warning: "warn",
  info: "muted",
};

export const RULE_TYPE_LABEL: Record<QualityRule["type"], string> = {
  completeness: "完整性",
  uniqueness: "唯一性",
  validity: "有效性",
  consistency: "一致性",
  timeliness: "时效性",
};

export const RULE_STATUS_LABEL: Record<RuleStatus, string> = {
  passing: "通过",
  failing: "失败",
  paused: "已暂停",
  error: "错误",
};

export const RULE_STATUS_TONE: Record<RuleStatus, "ok" | "warn" | "bad" | "muted"> = {
  passing: "ok",
  failing: "bad",
  paused: "muted",
  error: "bad",
};

// ── Pure functions ─────────────────────────────────────────────

export function formatTimestamp(iso: string | number | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(typeof iso === "number" ? iso * 1000 : iso);
  if (isNaN(d.getTime())) return "—";
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

export function formatPercent(rate: number): string {
  if (rate <= 0) return "0%";
  if (rate >= 1) return "100%";
  if (rate < 0.001) return "<0.1%";
  return `${(rate * 100).toFixed(1)}%`;
}

export function scoreToTone(score: number): "ok" | "warn" | "bad" {
  if (score >= 90) return "ok";
  if (score >= 70) return "warn";
  return "bad";
}

export function filterIssues(
  issues: HealthIssue[],
  severity: Severity | "all",
  query: string,
): HealthIssue[] {
  const q = query.trim().toLowerCase();
  return issues.filter((i) => {
    if (severity !== "all" && i.severity !== severity) return false;
    if (!q) return true;
    return (
      i.table.toLowerCase().includes(q) ||
      i.column.toLowerCase().includes(q) ||
      i.message.toLowerCase().includes(q)
    );
  });
}

export function filterRules(
  rules: QualityRule[],
  status: RuleStatus | "all",
  query: string,
): QualityRule[] {
  const q = query.trim().toLowerCase();
  return rules.filter((r) => {
    if (status !== "all" && r.status !== status) return false;
    if (!q) return true;
    return (
      r.name.toLowerCase().includes(q) ||
      r.target.toLowerCase().includes(q) ||
      RULE_TYPE_LABEL[r.type].includes(q)
    );
  });
}

export function sortIssuesBySeverity(issues: HealthIssue[]): HealthIssue[] {
  const order: Record<Severity, number> = { critical: 0, warning: 1, info: 2 };
  return [...issues].sort((a, b) => {
    const diff = order[a.severity] - order[b.severity];
    if (diff !== 0) return diff;
    return new Date(b.detectedAt).getTime() - new Date(a.detectedAt).getTime();
  });
}

// ── Page Component ─────────────────────────────────────────────

export function DataHealthPage() {
  const { data, err, loading, setData, setErr } = useJsonGet<HealthSummary>("/v1/data-health/summary");
  const hs = data;

  const [tab, setTab] = useState("overview");
  const [issueFilter, setIssueFilter] = useState<Severity | "all">("all");
  const [issueQuery, setIssueQuery] = useState("");
  const [ruleFilter, setRuleFilter] = useState<RuleStatus | "all">("all");
  const [ruleQuery, setRuleQuery] = useState("");
  const [msg, setMsg] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const filteredIssues = useMemo(
    () => hs ? sortIssuesBySeverity(filterIssues(hs.issues, issueFilter, issueQuery)) : [],
    [hs, issueFilter, issueQuery],
  );

  const filteredRules = useMemo(
    () => hs ? filterRules(hs.rules, ruleFilter, ruleQuery) : [],
    [hs, ruleFilter, ruleQuery],
  );

  const trendMax = useMemo(
    () => hs && hs.trend.length ? Math.max(...hs.trend.map((p) => p.score)) : 0,
    [hs],
  );
  const trendMin = useMemo(
    () => hs && hs.trend.length ? Math.min(...hs.trend.map((p) => p.score)) : 0,
    [hs],
  );

  async function handleRefreshChecks() {
    setMsg("");
    setRefreshing(true);
    try {
      const next = await apiGet<HealthSummary>("/v1/data-health/summary");
      setData(next);
      setErr(null);
      setMsg("检查结果已刷新");
    } catch (e) {
      const message = String((e as Error).message || e);
      setErr(message);
      setMsg(`刷新失败：${message}`);
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <S2Chrome title="数据健康" lede="数据质量仪表盘 · 栖月汇微商城 12 管道监控">
      <BpToolbar>
        <button type="button" className="btn-primary" disabled={refreshing} onClick={() => void handleRefreshChecks()}>
          {refreshing ? "正在刷新…" : "刷新检查结果"}
        </button>
        <Link to="/data/lineage" className="btn-nav">数据沿袭</Link>
      </BpToolbar>

      {loading && <p className="muted">加载中…</p>}
      {err && <p className="error">{err}</p>}
      {msg && <p className="aos-text">{msg}</p>}
      {!loading && !err && !hs && (
        <p className="muted">暂无健康数据，请先执行管道。</p>
      )}

      {hs && (
        <>
          <BpMetricGrid
            items={[
              { label: "总体评分", value: `${hs.overallScore}/100`, tone: scoreToTone(hs.overallScore) },
              { label: "可用率", value: formatPercent(hs.completeness), tone: scoreToTone(hs.completeness * 100) },
              { label: "一致率", value: hs.consistency == null ? "未知" : formatPercent(hs.consistency), tone: hs.consistency == null ? "muted" : scoreToTone(hs.consistency * 100) },
              { label: "时效率", value: formatPercent(hs.timeliness), tone: scoreToTone(hs.timeliness * 100) },
            ]}
          />

          <BpMetricGrid
            items={[
              { label: "规则总数", value: hs.totalRules, tone: "muted" },
              { label: "通过规则", value: hs.passingRules, tone: "ok" },
              { label: "开放问题", value: hs.openIssues, tone: hs.openIssues > 0 ? "warn" : "ok" },
              { label: "严重问题", value: hs.criticalIssues, tone: hs.criticalIssues > 0 ? "bad" : "ok" },
            ]}
          />

          <BpTabs
            tabs={[
              { id: "overview", label: "概览" },
              { id: "rules", label: "质量规则" },
              { id: "issues", label: `问题列表${hs.openIssues > 0 ? ` (${hs.openIssues})` : ""}` },
              { id: "trend", label: "趋势" },
            ]}
            active={tab}
            onChange={setTab}
          />

          {tab === "overview" && (
            <div>
              {hs.issues.length > 0 ? (
                <BpTable
                  columns={["严重级别", "业务数据", "业务字段", "问题描述", "发现时间"]}
                  rows={filteredIssues.slice(0, 10).map((i) => [
                    <span className={`bp-discover-badge bp-discover-badge-${SEVERITY_TONE[i.severity]}`}>
                      {SEVERITY_LABEL[i.severity]}
                    </span>,
                    <span>{i.table}</span>,
                    <span>{i.column}</span>,
                    <div>
                      {i.message}
                      <details><summary>技术审计信息</summary><code>{i.id}</code>{i.pipelineId ? <> · <code>{i.pipelineId}</code></> : null}{i.ruleId ? <> · <code>{i.ruleId}</code></> : null}</details>
                    </div>,
                    formatTimestamp(i.detectedAt),
                  ])}
                />
              ) : (
                <BpBanner tone="info">所有 12 管道数据完整性检查通过，无异常问题。</BpBanner>
              )}
              {hs.criticalIssues > 0 && (
                <BpBanner tone="warn">
                  有 {hs.criticalIssues} 个严重问题需要立即处理
                </BpBanner>
              )}
            </div>
          )}

          {tab === "rules" && (
            <div>
              <BpToolbar>
                <select
                  value={ruleFilter}
                  onChange={(e) => setRuleFilter(e.target.value as RuleStatus | "all")}
                >
                  <option value="all">全部状态</option>
                  <option value="passing">通过</option>
                  <option value="failing">失败</option>
                  <option value="paused">已暂停</option>
                  <option value="error">错误</option>
                </select>
                <input
                  type="search"
                  placeholder="搜索规则名/表名…"
                  value={ruleQuery}
                  onChange={(e) => setRuleQuery(e.target.value)}
                  style={{ minWidth: 200 }}
                />
                <span className="muted" style={{ fontSize: "0.75rem" }}>
                  {hs.passingRules}/{hs.totalRules} 通过
                </span>
              </BpToolbar>
              <BpTable
                columns={["规则名", "类型", "目标表", "状态", "阈值", "实际", "最近检查"]}
                rows={filteredRules.map((r) => [
                  r.name,
                  RULE_TYPE_LABEL[r.type],
                  <span className="mono">{r.target}</span>,
                  <span className={`bp-discover-badge bp-discover-badge-${RULE_STATUS_TONE[r.status]}`}>
                    {RULE_STATUS_LABEL[r.status]}
                  </span>,
                  formatPercent(r.threshold),
                  formatPercent(r.actual),
                  formatTimestamp(r.lastCheckedAt),
                ])}
              />
            </div>
          )}

          {tab === "issues" && (
            <div>
              <BpToolbar>
                <select
                  value={issueFilter}
                  onChange={(e) => setIssueFilter(e.target.value as Severity | "all")}
                >
                  <option value="all">全部级别</option>
                  <option value="critical">严重</option>
                  <option value="warning">警告</option>
                  <option value="info">提示</option>
                </select>
                <input
                  type="search"
                  placeholder="搜索表名/列名/描述…"
                  value={issueQuery}
                  onChange={(e) => setIssueQuery(e.target.value)}
                  style={{ minWidth: 200 }}
                />
                <span className="muted" style={{ fontSize: "0.75rem" }}>
                  {filteredIssues.length} 个问题
                </span>
              </BpToolbar>
              {filteredIssues.length > 0 ? (
                <BpTable
                  columns={["严重级别", "业务数据", "业务字段", "问题描述", "发现时间"]}
                  rows={filteredIssues.map((i) => [
                    <span className={`bp-discover-badge bp-discover-badge-${SEVERITY_TONE[i.severity]}`}>
                      {SEVERITY_LABEL[i.severity]}
                    </span>,
                    <span>{i.table}</span>,
                    <span>{i.column}</span>,
                    <div>
                      {i.message}
                      <details><summary>技术审计信息</summary><code>{i.id}</code>{i.pipelineId ? <> · <code>{i.pipelineId}</code></> : null}{i.ruleId ? <> · <code>{i.ruleId}</code></> : null}</details>
                    </div>,
                    formatTimestamp(i.detectedAt),
                  ])}
                />
              ) : (
                <BpBanner tone="info">无匹配的问题记录。</BpBanner>
              )}
            </div>
          )}

          {tab === "trend" && (
            <div>
              <h3 className="aos-text" style={{ fontSize: "0.85rem", marginBottom: "0.5rem" }}>
                健康评分趋势（有权威运行记录的日期）
              </h3>
              <div className="bp-table-wrap">
                <BpTable
                  columns={["日期", "评分", "趋势条"]}
                  rows={hs.trend.map((p) => [
                    p.date,
                    <span className={scoreToTone(p.score) === "ok" ? "ok-text" : scoreToTone(p.score) === "warn" ? "warn-text" : "bad-text"}>
                      {p.score}
                    </span>,
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <div
                        style={{
                          width: `${(p.score / 100) * 200}px`,
                          height: 12,
                          borderRadius: 2,
                          background:
                            scoreToTone(p.score) === "ok"
                              ? "var(--aos-green, #22c55e)"
                              : scoreToTone(p.score) === "warn"
                                ? "var(--aos-amber, #f59e0b)"
                                : "var(--aos-red, #ef4444)",
                        }}
                      />
                      <span className="muted" style={{ fontSize: "0.7rem" }}>
                        {trendMax === p.score ? "峰" : trendMin === p.score ? "谷" : ""}
                      </span>
                    </div>,
                  ])}
                />
              </div>
              <p className="muted" style={{ fontSize: "0.75rem", marginTop: "0.5rem" }}>
                当前返回 {hs.trend.length} 个记录日 · 最高 {trendMax} · 最低 {trendMin} · 平均{" "}
                {Math.round(hs.trend.reduce((a, b) => a + b.score, 0) / (hs.trend.length || 1))}
              </p>
            </div>
          )}
        </>
      )}

      <BpBanner tone="info">
        数据健康 · 栖月汇微商城 12 管道 ·{" "}
        <Link to="/data/datasets">数据集</Link> ·{" "}
        <Link to="/data/lineage">数据沿袭</Link>
      </BpBanner>
    </S2Chrome>
  );
}
