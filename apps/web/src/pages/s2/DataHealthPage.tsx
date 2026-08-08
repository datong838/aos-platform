import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../../api/client";
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
  target: string; // dataset or table name
  status: RuleStatus;
  lastCheckedAt: string;
  threshold: number; // 0..1
  actual: number; // 0..1
};

export type HealthIssue = {
  id: string;
  severity: Severity;
  table: string;
  column: string;
  message: string;
  detectedAt: string;
  ruleId?: string;
};

export type TrendPoint = {
  date: string; // ISO date
  score: number; // 0..100
};

export type HealthSummary = {
  overallScore: number; // 0..100
  completeness: number; // 0..1
  consistency: number; // 0..1
  timeliness: number; // 0..1
  totalRules: number;
  passingRules: number;
  openIssues: number;
  criticalIssues: number;
  rules: QualityRule[];
  issues: HealthIssue[];
  trend: TrendPoint[];
};

// ── Pure functions ─────────────────────────────────────────────

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

export function formatTimestamp(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
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
    // Within same severity, sort by detectedAt descending
    return new Date(b.detectedAt).getTime() - new Date(a.detectedAt).getTime();
  });
}

export function calculatePassRate(rules: QualityRule[]): number {
  if (rules.length === 0) return 0;
  const passing = rules.filter((r) => r.status === "passing").length;
  return passing / rules.length;
}

export function checkRuleViolation(rule: QualityRule): boolean {
  return rule.actual < rule.threshold;
}

export function ruleEffectiveness(rules: QualityRule[]): {
  total: number;
  effective: number;
  ineffective: number;
} {
  const total = rules.length;
  let effective = 0;
  for (const r of rules) {
    if (r.status === "passing" && !checkRuleViolation(r)) effective++;
  }
  return { total, effective, ineffective: total - effective };
}

// ── Mock data ──────────────────────────────────────────────────

const DEMO_RULES: QualityRule[] = [
  { id: "r-001", name: "订单ID非空检查", type: "completeness", target: "栖月汇-订单", status: "passing", lastCheckedAt: new Date(Date.now() - 5 * 60000).toISOString(), threshold: 0.999, actual: 1.0 },
  { id: "r-002", name: "客户名唯一性", type: "uniqueness", target: "栖月汇-会员", status: "passing", lastCheckedAt: new Date(Date.now() - 12 * 60000).toISOString(), threshold: 0.99, actual: 0.998 },
  { id: "r-003", name: "金额正值校验", type: "validity", target: "栖月汇-订单", status: "failing", lastCheckedAt: new Date(Date.now() - 3 * 60000).toISOString(), threshold: 1.0, actual: 0.997 },
  { id: "r-004", name: "货币代码一致性", type: "consistency", target: "栖月汇-订单", status: "passing", lastCheckedAt: new Date(Date.now() - 30 * 60000).toISOString(), threshold: 0.95, actual: 1.0 },
  { id: "r-005", name: "同步时效率", type: "timeliness", target: "栖月汇-订单同步", status: "failing", lastCheckedAt: new Date(Date.now() - 60 * 60000).toISOString(), threshold: 0.9, actual: 0.82 },
  { id: "r-006", name: "地址字段完整性", type: "completeness", target: "栖月汇-会员地址", status: "paused", lastCheckedAt: new Date(Date.now() - 240 * 60000).toISOString(), threshold: 0.9, actual: 0.85 },
  { id: "r-007", name: "SKU编码格式", type: "validity", target: "栖月汇-SKU维度", status: "error", lastCheckedAt: new Date(Date.now() - 180 * 60000).toISOString(), threshold: 0.99, actual: 0.0 },
];

const DEMO_ISSUES: HealthIssue[] = [
  { id: "i-001", severity: "critical", table: "栖月汇-订单", column: "amount", message: "发现 3 笔负值金额记录", detectedAt: new Date(Date.now() - 3 * 60000).toISOString(), ruleId: "r-003" },
  { id: "i-002", severity: "critical", table: "栖月汇-订单同步", column: "synced_at", message: "同步延迟超过 2 小时", detectedAt: new Date(Date.now() - 8 * 60000).toISOString(), ruleId: "r-005" },
  { id: "i-003", severity: "warning", table: "栖月汇-会员地址", column: "zip_code", message: "空值率 15% 超过阈值 10%", detectedAt: new Date(Date.now() - 45 * 60000).toISOString(), ruleId: "r-006" },
  { id: "i-004", severity: "warning", table: "栖月汇-SKU维度", column: "sku_code", message: "规则引擎连接超时", detectedAt: new Date(Date.now() - 120 * 60000).toISOString(), ruleId: "r-007" },
  { id: "i-005", severity: "info", table: "栖月汇-订单", column: "currency", message: "新增货币代码 ZAR 未在白名单中", detectedAt: new Date(Date.now() - 200 * 60000).toISOString() },
];

const DEMO_TREND: TrendPoint[] = Array.from({ length: 14 }, (_, i) => {
  const d = new Date();
  d.setDate(d.getDate() - (13 - i));
  return {
    date: d.toISOString().slice(0, 10),
    score: Math.round(80 + Math.sin(i * 0.5) * 8 + Math.random() * 5),
  };
});

const DEMO_SUMMARY: HealthSummary = {
  overallScore: 87,
  completeness: 0.987,
  consistency: 0.999,
  timeliness: 0.82,
  totalRules: 7,
  passingRules: 3,
  openIssues: 5,
  criticalIssues: 2,
  rules: DEMO_RULES,
  issues: DEMO_ISSUES,
  trend: DEMO_TREND,
};

// ── Page Component ─────────────────────────────────────────────

export function DataHealthPage() {
  const { data, err, loading } = useJsonGet<HealthSummary>("/v1/data-health/summary");
  const hs = data ?? DEMO_SUMMARY;

  const [tab, setTab] = useState("overview");
  const [issueFilter, setIssueFilter] = useState<Severity | "all">("all");
  const [issueQuery, setIssueQuery] = useState("");
  const [ruleFilter, setRuleFilter] = useState<RuleStatus | "all">("all");
  const [ruleQuery, setRuleQuery] = useState("");
  const [msg, setMsg] = useState("");

  const filteredIssues = useMemo(
    () => sortIssuesBySeverity(filterIssues(hs.issues, issueFilter, issueQuery)),
    [hs.issues, issueFilter, issueQuery],
  );

  const filteredRules = useMemo(
    () => filterRules(hs.rules, ruleFilter, ruleQuery),
    [hs.rules, ruleFilter, ruleQuery],
  );

  const effectiveness = useMemo(() => ruleEffectiveness(hs.rules), [hs.rules]);

  const trendMax = useMemo(
    () => Math.max(...hs.trend.map((p) => p.score), 1),
    [hs.trend],
  );
  const trendMin = useMemo(
    () => Math.min(...hs.trend.map((p) => p.score), 0),
    [hs.trend],
  );

  async function handleRunChecks() {
    setMsg("");
    try {
      await apiPost("/v1/data-health/run-checks", {});
      setMsg("已触发全量质量检查");
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome title="数据健康" lede="数据质量仪表盘 · 监控规则状态、发现问题、跟踪趋势">
      <BpToolbar>
        <button type="button" className="btn-primary" onClick={() => void handleRunChecks()}>
          运行检查
        </button>
        <Link to="/data/health/rules/new" className="btn-nav">添加规则</Link>
        <Link to="/data/health/history" className="btn-nav">查看历史</Link>
      </BpToolbar>

      {loading && <p className="muted">加载中…</p>}
      {err && <p className="error">{err}</p>}
      {msg && <p className="aos-text">{msg}</p>}

      <BpMetricGrid
        items={[
          { label: "总体评分", value: `${hs.overallScore}/100`, tone: scoreToTone(hs.overallScore) },
          { label: "完整率", value: formatPercent(hs.completeness), tone: scoreToTone(hs.completeness * 100) },
          { label: "一致率", value: formatPercent(hs.consistency), tone: scoreToTone(hs.consistency * 100) },
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
          { id: "issues", label: "问题列表" },
          { id: "trend", label: "趋势" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "overview" && (
        <div>
          <BpTable
            columns={["严重级别", "表名", "列名", "问题描述", "发现时间"]}
            rows={filteredIssues.slice(0, 5).map((i) => [
              <span className={`bp-discover-badge bp-discover-badge-${SEVERITY_TONE[i.severity]}`}>
                {SEVERITY_LABEL[i.severity]}
              </span>,
              <span className="mono">{i.table}</span>,
              <span className="mono">{i.column}</span>,
              i.message,
              formatTimestamp(i.detectedAt),
            ])}
          />
          <BpBanner tone={hs.criticalIssues > 0 ? "warn" : "info"}>
            {hs.criticalIssues > 0
              ? `有 ${hs.criticalIssues} 个严重问题需要立即处理`
              : "无严重问题，数据质量良好"}
          </BpBanner>
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
              style={{ minWidth: 180 }}
            />
            <span className="muted" style={{ fontSize: "0.75rem" }}>
              有效规则 {effectiveness.effective}/{effectiveness.total}
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
          <BpTable
            columns={["严重级别", "表名", "列名", "问题描述", "发现时间"]}
            rows={filteredIssues.map((i) => [
              <span className={`bp-discover-badge bp-discover-badge-${SEVERITY_TONE[i.severity]}`}>
                {SEVERITY_LABEL[i.severity]}
              </span>,
              <span className="mono">{i.table}</span>,
              <span className="mono">{i.column}</span>,
              i.message,
              formatTimestamp(i.detectedAt),
            ])}
          />
        </div>
      )}

      {tab === "trend" && (
        <div>
          <h3 className="aos-text" style={{ fontSize: "0.85rem", marginBottom: "0.5rem" }}>
            健康评分趋势（最近 14 天）
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
                          ? "var(--aos-green)"
                          : scoreToTone(p.score) === "warn"
                            ? "var(--aos-amber)"
                            : "var(--aos-red)",
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
            最高 {trendMax} · 最低 {trendMin} · 平均{" "}
            {Math.round(hs.trend.reduce((a, b) => a + b.score, 0) / (hs.trend.length || 1))}
          </p>
        </div>
      )}

      <BpBanner tone="info">
        对齐 <code>health.html</code> · 概览/规则/问题/趋势四 Tab ·{" "}
        <Link to="/data/datasets">数据集</Link> ·{" "}
        <Link to="/data/lineage">数据沿袭</Link>
      </BpBanner>
    </S2Chrome>
  );
}
