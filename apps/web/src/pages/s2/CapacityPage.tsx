import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";

// ── Types ──────────────────────────────────────────────────────

export type RateLimit = {
  model: string;
  provider: string;
  tokensPerMin: string;
  requestsPerMin: string;
};

export type UsageBucket = {
  period: "today" | "week" | "month";
  label: string;
  totalRequests: number;
  totalTokens: number;
  totalCostUsd: number;
};

type QuotaUsage = {
  model: string;
  provider: string;
  used: number;
  quota: number;
  unit: string;
};

export type UserLimit = {
  user: string;
  team: string;
  rpmLimit: number;
  tpmLimit: number;
  dailyBudgetUsd: number;
  usedTodayUsd: number;
};

type TabId = "usage" | "rate-limits" | "reserved";

// ── Mock data ──────────────────────────────────────────────────

const RATE_LIMITS: RateLimit[] = [
  { model: "GPT-5.4 Pro", provider: "OpenAI", tokensPerMin: "1.5M", requestsPerMin: "1K" },
  { model: "GPT-5.5", provider: "OpenAI", tokensPerMin: "7M", requestsPerMin: "3.5K" },
  { model: "GPT-5.4 mini", provider: "OpenAI", tokensPerMin: "7.5M", requestsPerMin: "3.8K" },
  { model: "Claude Opus 4.7", provider: "Anthropic", tokensPerMin: "8M", requestsPerMin: "900" },
  { model: "Claude Sonnet 4.6", provider: "Anthropic", tokensPerMin: "7M", requestsPerMin: "2.5K" },
  { model: "Claude Haiku 4.5", provider: "Anthropic", tokensPerMin: "6M", requestsPerMin: "2.5K" },
  { model: "Grok 4.3", provider: "xAI", tokensPerMin: "1M", requestsPerMin: "200" },
  { model: "Llama 4 Maverick 17B", provider: "Meta", tokensPerMin: "300K", requestsPerMin: "450" },
  { model: "text-embedding-ada-002", provider: "OpenAI", tokensPerMin: "4.2M", requestsPerMin: "4.2K" },
  { model: "Text Embedding 3 Large", provider: "OpenAI", tokensPerMin: "2M", requestsPerMin: "4K" },
];

const USAGE_BUCKETS: UsageBucket[] = [
  { period: "today", label: "今日", totalRequests: 12_480, totalTokens: 8_920_000, totalCostUsd: 142.55 },
  { period: "week", label: "本周", totalRequests: 87_350, totalTokens: 62_400_000, totalCostUsd: 987.20 },
  { period: "month", label: "本月", totalRequests: 342_900, totalTokens: 248_000_000, totalCostUsd: 3_920.75 },
];

const QUOTA_USAGE: QuotaUsage[] = [
  { model: "GPT-5.4 Pro", provider: "OpenAI", used: 1_240_000, quota: 1_500_000, unit: "tpm" },
  { model: "GPT-5.5", provider: "OpenAI", used: 4_200_000, quota: 7_000_000, unit: "tpm" },
  { model: "Claude Opus 4.7", provider: "Anthropic", used: 7_600_000, quota: 8_000_000, unit: "tpm" },
  { model: "Claude Sonnet 4.6", provider: "Anthropic", used: 2_100_000, quota: 7_000_000, unit: "tpm" },
  { model: "Grok 4.3", provider: "xAI", used: 980_000, quota: 1_000_000, unit: "tpm" },
  { model: "text-embedding-ada-002", provider: "OpenAI", used: 800_000, quota: 4_200_000, unit: "tpm" },
];

const USER_LIMITS: UserLimit[] = [
  { user: "alice@corp", team: "数据平台", rpmLimit: 60, tpmLimit: 200_000, dailyBudgetUsd: 50, usedTodayUsd: 12.4 },
  { user: "bob@corp", team: "数据平台", rpmLimit: 60, tpmLimit: 200_000, dailyBudgetUsd: 50, usedTodayUsd: 48.2 },
  { user: "carol@corp", team: "风控", rpmLimit: 30, tpmLimit: 100_000, dailyBudgetUsd: 20, usedTodayUsd: 5.1 },
  { user: "dave@corp", team: "风控", rpmLimit: 30, tpmLimit: 100_000, dailyBudgetUsd: 20, usedTodayUsd: 19.8 },
  { user: "eve@corp", team: "运营", rpmLimit: 120, tpmLimit: 500_000, dailyBudgetUsd: 100, usedTodayUsd: 67.3 },
];

// ── Pure functions (extracted for testing) ─────────────────────

export function formatTokenCount(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function formatUsd(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(2)}K`;
  return `$${n.toFixed(2)}`;
}

/** Returns percentage 0-100, capped at 100. */
export function usagePercent(used: number, quota: number): number {
  if (quota <= 0) return 0;
  return Math.min(100, Math.round((used / quota) * 100));
}

/** Classify usage into a tone for styling. */
export function usageTone(pct: number): "ok" | "warn" | "danger" {
  if (pct >= 90) return "danger";
  if (pct >= 70) return "warn";
  return "ok";
}

/** Compute aggregate stats from a list of usage buckets. */
export function sumUsage(buckets: UsageBucket[]): {
  requests: number;
  tokens: number;
  cost: number;
} {
  return buckets.reduce(
    (acc, b) => ({
      requests: acc.requests + b.totalRequests,
      tokens: acc.tokens + b.totalTokens,
      cost: acc.cost + b.totalCostUsd,
    }),
    { requests: 0, tokens: 0, cost: 0 },
  );
}

/** Filter rate limits by provider keyword. */
export function filterRateLimits(limits: RateLimit[], providerFilter: string): RateLimit[] {
  if (providerFilter === "all") return limits;
  return limits.filter((l) => l.provider === providerFilter);
}

/** Filter user limits by team. */
export function filterUserLimits(users: UserLimit[], teamFilter: string): UserLimit[] {
  if (teamFilter === "all") return users;
  return users.filter((u) => u.team === teamFilter);
}

// ── Component ──────────────────────────────────────────────────

export function CapacityPage() {
  const [tab, setTab] = useState<TabId>("usage");
  const [usagePeriod, setUsagePeriod] = useState<"today" | "week" | "month">("today");
  const [providerFilter, setProviderFilter] = useState("all");
  const [teamFilter, setTeamFilter] = useState("all");

  const currentBucket = useMemo(
    () => USAGE_BUCKETS.find((b) => b.period === usagePeriod) || USAGE_BUCKETS[0],
    [usagePeriod],
  );
  const filteredLimits = useMemo(
    () => filterRateLimits(RATE_LIMITS, providerFilter),
    [providerFilter],
  );
  const filteredUsers = useMemo(
    () => filterUserLimits(USER_LIMITS, teamFilter),
    [teamFilter],
  );
  const allProviders = useMemo(
    () => Array.from(new Set(RATE_LIMITS.map((r) => r.provider))).sort(),
    [],
  );
  const allTeams = useMemo(
    () => Array.from(new Set(USER_LIMITS.map((u) => u.team))).sort(),
    [],
  );

  return (
    <PageChrome title="容量管理" lede="管理 LLM 使用限制、速率限制和预留容量">
      <div style={{ maxWidth: "1100px", margin: "0 auto" }}>
        {/* Tab 导航 */}
        <div style={{ borderBottom: "1px solid var(--aos-border)", background: "var(--aos-surface)", marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 8 }}>
            {([
              { id: "usage", label: "用量仪表盘" },
              { id: "rate-limits", label: "速率限制" },
              { id: "reserved", label: "预留容量" },
            ] as const).map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                style={{
                  padding: "12px 16px",
                  fontSize: 13,
                  fontWeight: tab === t.id ? 500 : 400,
                  borderBottom: tab === t.id ? "2px solid var(--aos-indigo-600)" : "2px solid transparent",
                  color: tab === t.id ? "var(--aos-indigo-600)" : "var(--aos-text-secondary)",
                  background: "none",
                  border: "none",
                  borderTop: "none",
                  borderLeft: "none",
                  borderRight: "none",
                  cursor: "pointer",
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* 信息横幅 */}
        <div style={{ background: "var(--aos-accent-light)", border: "1px solid var(--aos-accent-border)", borderRadius: 8, padding: 16, marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--aos-accent)" strokeWidth="1.5" style={{ flexShrink: 0, marginTop: 2 }}>
              <circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" strokeLinecap="round" />
            </svg>
            <p style={{ fontSize: 13, color: "var(--aos-blue-title)", margin: 0, lineHeight: 1.6 }}>
              所有容量的 <span style={{ fontWeight: 600 }}>20%</span> 始终保留用于实时交互式 AIP 使用。如需额外容量，请联系 Palantir 支持。
            </p>
          </div>
        </div>

        {/* === Usage Dashboard Tab === */}
        {tab === "usage" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Period selector */}
            <div style={{ display: "flex", gap: 6, background: "var(--aos-surface-hover)", padding: 4, borderRadius: 8, width: "fit-content" }}>
              {(["today", "week", "month"] as const).map((p) => {
                const b = USAGE_BUCKETS.find((x) => x.period === p)!;
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setUsagePeriod(p)}
                    style={{
                      padding: "6px 14px", fontSize: 12, fontWeight: 500, borderRadius: 6, border: "none",
                      background: usagePeriod === p ? "var(--aos-surface)" : "transparent", color: usagePeriod === p ? "var(--aos-indigo-600)" : "var(--aos-text-secondary)",
                      cursor: "pointer", boxShadow: usagePeriod === p ? "var(--shadow-sm)" : "none",
                    }}
                  >
                    {b.label}
                  </button>
                );
              })}
            </div>

            {/* Metrics cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
              <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 8, padding: 20 }}>
                <div style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4 }}>总请求数</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--aos-indigo-600)" }}>{currentBucket.totalRequests.toLocaleString()}</div>
                <div style={{ fontSize: 11, color: "var(--aos-faint)", marginTop: 4 }}>{currentBucket.label}累计</div>
              </div>
              <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 8, padding: 20 }}>
                <div style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4 }}>Token 消耗</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--aos-purple-600)" }}>{formatTokenCount(currentBucket.totalTokens)}</div>
                <div style={{ fontSize: 11, color: "var(--aos-faint)", marginTop: 4 }}>{currentBucket.totalTokens.toLocaleString()} tokens</div>
              </div>
              <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 8, padding: 20 }}>
                <div style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4 }}>成本汇总</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--aos-amber-600)" }}>{formatUsd(currentBucket.totalCostUsd)}</div>
                <div style={{ fontSize: 11, color: "var(--aos-faint)", marginTop: 4 }}>{currentBucket.label} USD</div>
              </div>
            </div>

            {/* Quota progress bars */}
            <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 8, overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--aos-border)" }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>模型配额使用</h3>
                <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4, margin: "4px 0 0" }}>各模型当前分钟级 Token 用量 vs 配额</p>
              </div>
              <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
                {QUOTA_USAGE.map((q) => {
                  const pct = usagePercent(q.used, q.quota);
                  const tone = usageTone(pct);
                  const barColor = tone === "danger" ? "var(--aos-red)" : tone === "warn" ? "var(--aos-amber)" : "var(--aos-green)";
                  return (
                    <div key={q.model}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ width: 8, height: 8, borderRadius: "50%", background: q.provider === "OpenAI" ? "#10A37F" : q.provider === "Anthropic" ? "#D97706" : q.provider === "xAI" ? "#1D4ED8" : "#7C3AED" }} />
                          <span style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)" }}>{q.model}</span>
                          <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 3, background: "var(--aos-surface-hover)", color: "var(--aos-text-secondary)" }}>{q.provider}</span>
                        </div>
                        <span style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>
                          {formatTokenCount(q.used)} / {formatTokenCount(q.quota)} {q.unit} · <strong style={{ color: barColor }}>{pct}%</strong>
                        </span>
                      </div>
                      <div style={{ height: 8, background: "var(--aos-surface-hover)", borderRadius: 4, overflow: "hidden" }}>
                        <div style={{
                          height: "100%", width: `${pct}%`, background: barColor, borderRadius: 4,
                          transition: "width 0.3s",
                        }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* === Rate Limits Tab === */}
        {tab === "rate-limits" && (
          <>
            {/* 速率限制卡片 */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
              <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 8, padding: 20 }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ width: 40, height: 40, borderRadius: 8, background: "var(--aos-surface-hover)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--aos-text-secondary)" strokeWidth="1.5"><path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" strokeLinecap="round" strokeLinejoin="round" /></svg>
                    </div>
                    <div>
                      <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>项目速率限制</h3>
                      <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4, margin: "4px 0 0", lineHeight: 1.5 }}>管理所有项目范围的 LLM 使用限制，包括 AIP Agents、AIP Logic、Pipeline Builder 等应用。</p>
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 8, padding: 20 }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ width: 40, height: 40, borderRadius: 8, background: "var(--aos-surface-hover)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--aos-text-secondary)" strokeWidth="1.5"><circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 4-6 8-6s8 2 8 6" strokeLinecap="round" /></svg>
                    </div>
                    <div>
                      <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>用户速率限制</h3>
                      <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4, margin: "4px 0 0", lineHeight: 1.5 }}>管理所有用户范围的 LLM 使用限制，包括 AIP/IDE、AIP Analyst、Claude Code 等应用。</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 登记限制表 */}
            <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 8, overflow: "hidden", marginBottom: 24 }}>
              <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--aos-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>登记限制</h3>
                  <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4, margin: "4px 0 0" }}>为组织中启用的每个模型设置默认速率限制</p>
                </div>
                <select
                  value={providerFilter}
                  onChange={(e) => setProviderFilter(e.target.value)}
                  aria-label="limit-provider-filter"
                  style={{ padding: "6px 12px", fontSize: 12, border: "1px solid var(--aos-border)", borderRadius: 6, background: "var(--aos-surface)" }}
                >
                  <option value="all">所有供应商</option>
                  {allProviders.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", padding: "12px 20px", background: "var(--bg-surface-alt)", borderBottom: "1px solid var(--aos-border)", fontWeight: 600, color: "var(--aos-text-secondary)", fontSize: 12 }}>模型名称</th>
                      <th style={{ textAlign: "left", padding: "12px 20px", background: "var(--bg-surface-alt)", borderBottom: "1px solid var(--aos-border)", fontWeight: 600, color: "var(--aos-text-secondary)", fontSize: 12 }}>每分钟 Token 数</th>
                      <th style={{ textAlign: "left", padding: "12px 20px", background: "var(--bg-surface-alt)", borderBottom: "1px solid var(--aos-border)", fontWeight: 600, color: "var(--aos-text-secondary)", fontSize: 12 }}>每分钟请求数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredLimits.map((r) => (
                      <tr key={r.model} style={{ borderBottom: "1px solid var(--aos-divider)" }}>
                        <td style={{ padding: "12px 20px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <span style={{ width: 8, height: 8, borderRadius: "50%", background: r.provider === "OpenAI" ? "#10A37F" : r.provider === "Anthropic" ? "#D97706" : r.provider === "xAI" ? "#1D4ED8" : "#7C3AED" }} />
                            <span style={{ fontWeight: 500, color: "var(--aos-text)" }}>{r.model}</span>
                            <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 3, background: "var(--aos-surface-hover)", color: "var(--aos-text-secondary)" }}>{r.provider}</span>
                          </div>
                        </td>
                        <td style={{ padding: "12px 20px", color: "var(--aos-text)" }}>{r.tokensPerMin}</td>
                        <td style={{ padding: "12px 20px", color: "var(--aos-text)" }}>{r.requestsPerMin}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 用户限制表 */}
            <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 8, overflow: "hidden" }}>
              <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--aos-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>用户限制</h3>
                  <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4, margin: "4px 0 0" }}>每用户/每团队的速率限制和预算配置</p>
                </div>
                <select
                  value={teamFilter}
                  onChange={(e) => setTeamFilter(e.target.value)}
                  aria-label="team-filter"
                  style={{ padding: "6px 12px", fontSize: 12, border: "1px solid var(--aos-border)", borderRadius: 6, background: "var(--aos-surface)" }}
                >
                  <option value="all">所有团队</option>
                  {allTeams.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", padding: "10px 20px", background: "var(--bg-surface-alt)", borderBottom: "1px solid var(--aos-border)", fontWeight: 600, color: "var(--aos-text-secondary)", fontSize: 12 }}>用户</th>
                      <th style={{ textAlign: "left", padding: "10px 20px", background: "var(--bg-surface-alt)", borderBottom: "1px solid var(--aos-border)", fontWeight: 600, color: "var(--aos-text-secondary)", fontSize: 12 }}>团队</th>
                      <th style={{ textAlign: "left", padding: "10px 20px", background: "var(--bg-surface-alt)", borderBottom: "1px solid var(--aos-border)", fontWeight: 600, color: "var(--aos-text-secondary)", fontSize: 12 }}>RPM 限制</th>
                      <th style={{ textAlign: "left", padding: "10px 20px", background: "var(--bg-surface-alt)", borderBottom: "1px solid var(--aos-border)", fontWeight: 600, color: "var(--aos-text-secondary)", fontSize: 12 }}>TPM 限制</th>
                      <th style={{ textAlign: "left", padding: "10px 20px", background: "var(--bg-surface-alt)", borderBottom: "1px solid var(--aos-border)", fontWeight: 600, color: "var(--aos-text-secondary)", fontSize: 12 }}>日预算</th>
                      <th style={{ textAlign: "left", padding: "10px 20px", background: "var(--bg-surface-alt)", borderBottom: "1px solid var(--aos-border)", fontWeight: 600, color: "var(--aos-text-secondary)", fontSize: 12 }}>今日已用</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredUsers.map((u) => {
                      const budgetPct = usagePercent(u.usedTodayUsd, u.dailyBudgetUsd);
                      const tone = usageTone(budgetPct);
                      return (
                        <tr key={u.user} style={{ borderBottom: "1px solid var(--aos-divider)" }}>
                          <td style={{ padding: "10px 20px", fontWeight: 500, color: "var(--aos-text)" }}>{u.user}</td>
                          <td style={{ padding: "10px 20px" }}>
                            <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 10, background: "var(--aos-surface-hover)", color: "var(--aos-text)" }}>{u.team}</span>
                          </td>
                          <td style={{ padding: "10px 20px", color: "var(--aos-text)" }}>{u.rpmLimit}</td>
                          <td style={{ padding: "10px 20px", color: "var(--aos-text)" }}>{formatTokenCount(u.tpmLimit)}</td>
                          <td style={{ padding: "10px 20px", color: "var(--aos-text)" }}>${u.dailyBudgetUsd}</td>
                          <td style={{ padding: "10px 20px" }}>
                            <span style={{
                              fontWeight: 600,
                              color: tone === "danger" ? "var(--aos-red)" : tone === "warn" ? "var(--aos-amber)" : "var(--aos-green-600)",
                            }}>
                              ${u.usedTodayUsd.toFixed(2)}
                            </span>
                            <span style={{ fontSize: 11, color: "var(--aos-faint)", marginLeft: 4 }}>({budgetPct}%)</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* === Reserved Tab === */}
        {tab === "reserved" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 8, padding: 40, textAlign: "center" }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--aos-faint)" strokeWidth="1.5" style={{ margin: "0 auto 12px" }}>
                <rect x="3" y="4" width="18" height="6" rx="1" /><rect x="3" y="14" width="18" height="6" rx="1" />
              </svg>
              <p style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: 0 }}>预留容量</p>
              <p style={{ fontSize: 12, color: "var(--aos-faint)", marginTop: 8, margin: "8px 0 0" }}>
                预留容量功能即将上线。如需提前使用，请联系 Palantir 支持。
              </p>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Link to="/aip/model-catalog" style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid var(--aos-border)", color: "var(--aos-text)", textDecoration: "none", fontSize: 12 }}>模型目录 →</Link>
              <Link to="/aip/model-router" style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid var(--aos-border)", color: "var(--aos-text)", textDecoration: "none", fontSize: 12 }}>模型路由 →</Link>
              <Link to="/aip/model-providers" style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid var(--aos-border)", color: "var(--aos-text)", textDecoration: "none", fontSize: 12 }}>模型供应商 →</Link>
            </div>
          </div>
        )}
      </div>
    </PageChrome>
  );
}
