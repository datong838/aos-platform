import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPut } from "../../api/client";
import { aipModelRuntime, type ModelRuntimeCostOverview, type RuntimeCapacityPoolSummary } from "../../api/aipModelRuntime";
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

export type QuotaUsage = {
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

export type ProjectLimit = {
  rpmLimit: number;
  tpmLimit: number;
  scopeKey?: string;
};

export type CapacitySourceMode = "loading" | "live" | "error";

type TabId = "usage" | "rate-limits" | "reserved";

export type ApiUsageItem = {
  day?: string;
  totalRequests?: number;
  totalTokens?: number;
  cost?: number;
  peakRpm?: number;
};

export type ApiLimitItem = {
  scope?: string;
  scopeKey?: string;
  rpmLimit?: number;
  tpmLimit?: number;
};

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

function dayKey(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function parseDay(s: string): Date | null {
  if (!s) return null;
  const d = new Date(`${s.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Aggregate daily usage items into today / week / month buckets. */
export function mapUsageItemsToBuckets(items: ApiUsageItem[], now = new Date()): UsageBucket[] {
  const todayStr = dayKey(now);
  const weekStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - 6));
  const monthStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - 29));

  const acc = {
    today: { requests: 0, tokens: 0, cost: 0 },
    week: { requests: 0, tokens: 0, cost: 0 },
    month: { requests: 0, tokens: 0, cost: 0 },
  };

  for (const it of items) {
    const d = parseDay(String(it.day || ""));
    if (!d) continue;
    const key = dayKey(d);
    const req = Number(it.totalRequests || 0);
    const tok = Number(it.totalTokens || 0);
    const cost = Number(it.cost || 0);
    if (key === todayStr) {
      acc.today.requests += req;
      acc.today.tokens += tok;
      acc.today.cost += cost;
    }
    if (d >= weekStart) {
      acc.week.requests += req;
      acc.week.tokens += tok;
      acc.week.cost += cost;
    }
    if (d >= monthStart) {
      acc.month.requests += req;
      acc.month.tokens += tok;
      acc.month.cost += cost;
    }
  }

  return [
    { period: "today", label: "今日", totalRequests: acc.today.requests, totalTokens: acc.today.tokens, totalCostUsd: Math.round(acc.today.cost * 100) / 100 },
    { period: "week", label: "本周", totalRequests: acc.week.requests, totalTokens: acc.week.tokens, totalCostUsd: Math.round(acc.week.cost * 100) / 100 },
    { period: "month", label: "本月", totalRequests: acc.month.requests, totalTokens: acc.month.tokens, totalCostUsd: Math.round(acc.month.cost * 100) / 100 },
  ];
}

/** Map API user-limit rows to UI UserLimit. */
export function mapApiLimitToUserLimit(row: ApiLimitItem): UserLimit {
  return {
    user: String(row.scopeKey || row.scope || "unknown"),
    team: "—",
    rpmLimit: Number(row.rpmLimit ?? 60),
    tpmLimit: Number(row.tpmLimit ?? 60000),
    dailyBudgetUsd: 0,
    usedTodayUsd: 0,
  };
}

/** Build a single project TPM quota bar for live mode. */
export function projectQuotaFromLimit(
  limit: ProjectLimit | null,
  usedTokens: number,
): QuotaUsage[] {
  if (!limit) return [];
  return [
    {
      model: "项目默认 TPM",
      provider: "AIP",
      used: usedTokens,
      quota: Math.max(limit.tpmLimit, 1),
      unit: "tpm",
    },
  ];
}

export function isCapacityLiveSuccess(usageOk: boolean): CapacitySourceMode {
  return usageOk ? "live" : "error";
}

export function validateLimitSnapshot(
  response: ApiLimitItem | null | undefined,
  scope: "project" | "user",
  scopeKey: string,
  draft: { rpmLimit: number; tpmLimit: number },
): boolean {
  return response?.scope === scope
    && response.scopeKey === scopeKey
    && Number(response.rpmLimit) === draft.rpmLimit
    && Number(response.tpmLimit) === draft.tpmLimit;
}

export function rateLimitsFromRuntimePools(pools: RuntimeCapacityPoolSummary[]): RateLimit[] {
  return pools.map((pool) => ({
    model: pool.modelRef.assetId,
    provider: pool.providerRef.assetId,
    tokensPerMin: `每次租约 ${formatTokenCount(pool.maxTokenUnits)} 个模型用量单位`,
    requestsPerMin: `当前并发 ${pool.activeReservations}/${pool.maxConcurrency}`,
  }));
}

export function authoritativeCostLabel(cost: ModelRuntimeCostOverview | null): string {
  if (!cost || cost.usage.state === "unobserved") return "未观测";
  const totals = Object.entries(cost.usage.costTotals);
  if (!totals.length) return cost.usage.state === "unknown" ? "未知" : "尚无实际模型调用记录";
  return totals.map(([currency, amount]) => `${currency} ${amount.toFixed(2)}`).join(" · ");
}

// ── Component ──────────────────────────────────────────────────

export function CapacityPage() {
  const [tab, setTab] = useState<TabId>("usage");
  const [usagePeriod, setUsagePeriod] = useState<"today" | "week" | "month">("today");
  const [providerFilter, setProviderFilter] = useState("all");
  const [teamFilter, setTeamFilter] = useState("all");
  const [sourceMode, setSourceMode] = useState<CapacitySourceMode>("loading");
  const [usageBuckets, setUsageBuckets] = useState<UsageBucket[]>(() => mapUsageItemsToBuckets([]));
  const [quotaUsage, setQuotaUsage] = useState<QuotaUsage[]>([]);
  const [userLimits, setUserLimits] = useState<UserLimit[]>([]);
  const [projectLimit, setProjectLimit] = useState<ProjectLimit | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editor, setEditor] = useState<"project" | "user" | null>(null);
  const [projectDraft, setProjectDraft] = useState({ rpmLimit: 60, tpmLimit: 60000 });
  const [userDraft, setUserDraft] = useState({ userId: "", rpmLimit: 60, tpmLimit: 60000 });
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [runtimeCost, setRuntimeCost] = useState<ModelRuntimeCostOverview | null>(null);
  const [runtimeLimits, setRuntimeLimits] = useState<RateLimit[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [usageRes, projectRes, usersRes, runtime, cost] = await Promise.all([
          apiGet<{ items?: ApiUsageItem[]; summary?: { totalTokens?: number } }>("/v1/aip/capacity/usage?limit=30"),
          apiGet<ApiLimitItem>("/v1/aip/capacity/project-limits"),
          apiGet<{ items?: ApiLimitItem[] } | ApiLimitItem>("/v1/aip/capacity/user-limits").catch(() => ({ items: [] as ApiLimitItem[] })),
          aipModelRuntime.overview(),
          aipModelRuntime.costOverview(),
        ]);
        if (cancelled) return;
        const buckets = mapUsageItemsToBuckets(usageRes.items || []);
        const pl: ProjectLimit = {
          rpmLimit: Number(projectRes.rpmLimit ?? 60),
          tpmLimit: Number(projectRes.tpmLimit ?? 60000),
          scopeKey: projectRes.scopeKey,
        };
        const userItems = Array.isArray((usersRes as { items?: ApiLimitItem[] }).items)
          ? (usersRes as { items: ApiLimitItem[] }).items
          : [];
        const todayTokens = buckets.find((b) => b.period === "today")?.totalTokens ?? 0;
        setUsageBuckets(buckets);
        setProjectLimit(pl);
        setProjectDraft({ rpmLimit: pl.rpmLimit, tpmLimit: pl.tpmLimit });
        setQuotaUsage(projectQuotaFromLimit(pl, Math.min(todayTokens, pl.tpmLimit)));
        setUserLimits(userItems.map(mapApiLimitToUserLimit));
        setRuntimeLimits(rateLimitsFromRuntimePools(runtime.capacityPools));
        setRuntimeCost(cost);
        if (userItems[0]) setUserDraft({ userId: String(userItems[0].scopeKey || ""), rpmLimit: Number(userItems[0].rpmLimit ?? 60), tpmLimit: Number(userItems[0].tpmLimit ?? 60000) });
        setSourceMode("live");
        setLoadError(null);
      } catch (e) {
        if (cancelled) return;
        setUsageBuckets(mapUsageItemsToBuckets([]));
        setQuotaUsage([]);
        setUserLimits([]);
        setProjectLimit(null);
        setRuntimeLimits([]);
        setRuntimeCost(null);
        setSourceMode("error");
        setLoadError(String((e as Error).message || e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const currentBucket = useMemo(
    () => usageBuckets.find((b) => b.period === usagePeriod) || usageBuckets[0],
    [usagePeriod, usageBuckets],
  );
  const filteredLimits = useMemo(
    () => filterRateLimits(runtimeLimits, providerFilter),
    [providerFilter, runtimeLimits],
  );
  const filteredUsers = useMemo(
    () => filterUserLimits(userLimits, teamFilter),
    [teamFilter, userLimits],
  );
  const allProviders = useMemo(
    () => Array.from(new Set(runtimeLimits.map((r) => r.provider))).sort(),
    [runtimeLimits],
  );
  const allTeams = useMemo(
    () => Array.from(new Set(userLimits.map((u) => u.team))).sort(),
    [userLimits],
  );

  function cancelEditor() {
    if (editor === "project" && projectLimit) setProjectDraft({ rpmLimit: projectLimit.rpmLimit, tpmLimit: projectLimit.tpmLimit });
    if (editor === "user") {
      const snapshot = userLimits.find((u) => u.user === userDraft.userId);
      setUserDraft(snapshot ? { userId: snapshot.user, rpmLimit: snapshot.rpmLimit, tpmLimit: snapshot.tpmLimit } : { userId: "", rpmLimit: 60, tpmLimit: 60000 });
    }
    setEditor(null);
    setSaveMsg(null);
  }

  async function saveLimit(scope: "project" | "user") {
    if (saving) return;
    const targetKey = scope === "project" ? String(projectLimit?.scopeKey || "default") : userDraft.userId.trim();
    const draft = scope === "project" ? { ...projectDraft } : { rpmLimit: userDraft.rpmLimit, tpmLimit: userDraft.tpmLimit };
    if (!targetKey) return;
    const path = scope === "project"
      ? "/v1/aip/capacity/project-limits"
      : `/v1/aip/capacity/user-limits?userId=${encodeURIComponent(targetKey)}`;
    setSaving(true);
    setSaveMsg(null);
    try {
      const written = await apiPut<ApiLimitItem>(path, draft);
      if (!validateLimitSnapshot(written, scope, targetKey, draft)) throw new Error("写回响应 scope/目标/限额错配");
      let reread: ApiLimitItem;
      try {
        reread = await apiGet<ApiLimitItem>(path);
      } catch (e) {
        setSaveMsg(`写入已提交但重读核验失败：${String((e as Error).message || e)}`);
        return;
      }
      if (!validateLimitSnapshot(reread, scope, targetKey, draft)) {
        setSaveMsg("写入已提交但重读核验失败：服务端限额不一致");
        return;
      }
      if (scope === "project") {
        setProjectLimit({ ...draft, scopeKey: targetKey });
      } else {
        setUserLimits((prev) => {
          const next = mapApiLimitToUserLimit(reread);
          return prev.some((u) => u.user === targetKey) ? prev.map((u) => u.user === targetKey ? next : u) : [...prev, next];
        });
      }
      setSaveMsg("限额已保存并完成重读核验");
      setEditor(null);
    } catch (e) {
      setSaveMsg(`限额写入失败：${String((e as Error).message || e)}`);
    } finally {
      setSaving(false);
    }
  }

  const todayBucket = usageBuckets.find((b) => b.period === "today");
  const warnQuotaCount = quotaUsage.filter((q) => usageTone(usagePercent(q.used, q.quota)) !== "ok").length;

  return (
    <PageChrome title="容量管理" lede="查看用量、项目与用户限速及预留容量；数据来自容量权威接口，读取失败时不回落到本地演示数据">
      <div style={{ maxWidth: "1100px", margin: "0 auto" }}>
        {sourceMode === "error" && (
          <div className="w2-a6a7-demo-banner" role="alert">
            <span className="w2-a6a7-demo-badge">加载失败</span>
            <span className="w2-a6a7-demo-text">
              容量 API 不可用；未注入本地 MOCK{loadError ? ` · ${loadError}` : ""}
            </span>
          </div>
        )}
        {sourceMode === "live" && (
          <div className="w2-a6a7-live-banner" role="status">
            <span className="w2-a6a7-live-badge">实时数据</span>
            <span className="w2-a6a7-demo-text">兼容限额来自容量接口；精确价格、预算、用量凭证与容量池来自模型运行权威</span>
          </div>
        )}

        <div
          data-testid="capacity-ops-stats"
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, margin: "0 0 16px" }}
        >
          {[
            { label: "数据源", value: sourceMode === "live" ? "实时" : sourceMode === "error" ? "读取失败" : "读取中" },
            { label: "今日请求", value: (todayBucket?.totalRequests ?? 0).toLocaleString() },
            { label: "今日模型用量", value: formatTokenCount(todayBucket?.totalTokens ?? 0) },
            { label: "用户限额条", value: String(userLimits.length) },
            { label: "配额告警", value: String(warnQuotaCount) },
            { label: "权威成本", value: authoritativeCostLabel(runtimeCost) },
            { label: "当前视图", value: tab === "usage" ? "用量" : tab === "rate-limits" ? "限速" : "预留" },
          ].map((s) => (
            <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
              <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
              <div style={{ fontSize: 20, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{s.value}</div>
            </div>
          ))}
        </div>

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
        <div style={{ background: "var(--aos-accent-light)", border: "1px solid var(--aos-accent-border)", borderRadius: 2, padding: 16, marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--aos-accent)" strokeWidth="1.5" style={{ flexShrink: 0, marginTop: 2 }}>
              <circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" strokeLinecap="round" />
            </svg>
            <p style={{ fontSize: 13, color: "var(--aos-blue-title)", margin: 0, lineHeight: 1.6 }}>
              当前仅展示租户内已发布的兼容限额与精确容量池；未发布的预留比例不会按静态演示值推断。
              {projectLimit && sourceMode === "live" && (
                <> 当前项目限额：RPM {projectLimit.rpmLimit} · TPM {formatTokenCount(projectLimit.tpmLimit)}。</>
              )}
            </p>
          </div>
        </div>

        {/* === Usage Dashboard Tab === */}
        {tab === "usage" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Period selector */}
            <div style={{ display: "flex", gap: 6, background: "var(--aos-surface-hover)", padding: 4, borderRadius: 2, width: "fit-content" }}>
              {(["today", "week", "month"] as const).map((p) => {
                const b = usageBuckets.find((x) => x.period === p)!;
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setUsagePeriod(p)}
                    style={{
                      padding: "6px 14px", fontSize: 12, fontWeight: 500, borderRadius: 2, border: "none",
                      background: usagePeriod === p ? "var(--aos-surface)" : "transparent", color: usagePeriod === p ? "var(--aos-indigo-600)" : "var(--aos-text-secondary)",
                      cursor: "pointer", boxShadow: usagePeriod === p ? "var(--shadow-sm)" : "none",
                    }}
                  >
                    {b?.label || p}
                  </button>
                );
              })}
            </div>

            {/* Metrics cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
              <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 20 }}>
                <div style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4 }}>总请求数</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--aos-indigo-600)" }}>{(currentBucket?.totalRequests ?? 0).toLocaleString()}</div>
                <div style={{ fontSize: 11, color: "var(--aos-faint)", marginTop: 4 }}>{currentBucket?.label}累计</div>
              </div>
              <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 20 }}>
                <div style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4 }}>模型用量</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--aos-purple-600)" }}>{formatTokenCount(currentBucket?.totalTokens ?? 0)}</div>
                <div style={{ fontSize: 11, color: "var(--aos-faint)", marginTop: 4 }}>{(currentBucket?.totalTokens ?? 0).toLocaleString()} 个模型用量单位</div>
              </div>
              <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 20 }}>
                <div style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4 }}>成本汇总</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--aos-amber-600)" }}>{authoritativeCostLabel(runtimeCost)}</div>
                <div style={{ fontSize: 11, color: "var(--aos-faint)", marginTop: 4 }}>用量凭证为权威；未观测不等于 0</div>
              </div>
            </div>

            {/* Quota progress bars */}
            <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--aos-border)" }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>模型配额使用</h3>
                <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4, margin: "4px 0 0" }}>
                  {sourceMode === "live" ? "项目每分钟用量限额与今日用量" : "各模型当前分钟级用量与配额"}
                </p>
              </div>
              <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
                {quotaUsage.map((q) => {
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
                {quotaUsage.length === 0 && (
                  <p style={{ fontSize: 12, color: "var(--aos-faint)", margin: 0 }}>暂无配额数据</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* === Rate Limits Tab === */}
        {tab === "rate-limits" && (
          <>
            {/* 速率限制卡片 */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
              <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 20 }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ width: 40, height: 40, borderRadius: 2, background: "var(--aos-surface-hover)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--aos-text-secondary)" strokeWidth="1.5"><path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" strokeLinecap="round" strokeLinejoin="round" /></svg>
                    </div>
                    <div>
                      <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>项目速率限制</h3>
                      <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4, margin: "4px 0 0", lineHeight: 1.5 }}>
                        {projectLimit
                          ? `RPM ${projectLimit.rpmLimit} · TPM ${formatTokenCount(projectLimit.tpmLimit)}`
                          : "管理所有项目范围的 LLM 使用限制，包括 AIP Agents、AIP Logic、Pipeline Builder 等应用。"}
                      </p>
                    </div>
                  </div>
                </div>
                <div style={{ marginTop: 16 }}>
                  <button type="button" data-testid="manage-project-limit" disabled={sourceMode !== "live"} onClick={() => { setEditor("project"); setSaveMsg(null); }} style={{ display: "inline-flex", alignItems: "center", fontSize: 13, fontWeight: 500, color: "var(--aos-indigo-600)", border: 0, background: "transparent", cursor: sourceMode === "live" ? "pointer" : "not-allowed" }}>
                    管理
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ marginLeft: 4 }}><path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" /></svg>
                  </button>
                </div>
              </div>

              <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 20 }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ width: 40, height: 40, borderRadius: 2, background: "var(--aos-surface-hover)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--aos-text-secondary)" strokeWidth="1.5"><circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 4-6 8-6s8 2 8 6" strokeLinecap="round" /></svg>
                    </div>
                    <div>
                      <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>用户速率限制</h3>
                      <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4, margin: "4px 0 0", lineHeight: 1.5 }}>
                        {sourceMode === "live"
                          ? `已加载 ${userLimits.length} 条用户限额`
                          : "管理所有用户范围的 LLM 使用限制，包括 AIP/IDE、AIP Analyst、Claude Code 等应用。"}
                      </p>
                    </div>
                  </div>
                </div>
                <div style={{ marginTop: 16 }}>
                  <button type="button" data-testid="manage-user-limit" disabled={sourceMode !== "live"} onClick={() => { setEditor("user"); setSaveMsg(null); }} style={{ display: "inline-flex", alignItems: "center", fontSize: 13, fontWeight: 500, color: "var(--aos-indigo-600)", border: 0, background: "transparent", cursor: sourceMode === "live" ? "pointer" : "not-allowed" }}>
                    管理
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ marginLeft: 4 }}><path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" /></svg>
                  </button>
                </div>
              </div>
            </div>

            {editor && (
              <div data-testid={`capacity-editor-${editor}`} style={{ border: "1px solid var(--aos-border)", background: "var(--aos-surface)", padding: 16, marginBottom: 20 }}>
                <h3 style={{ marginTop: 0 }}>{editor === "project" ? "编辑项目速率限制" : "编辑用户速率限制"}</h3>
                {editor === "user" && <label>用户 ID <input aria-label="capacity-user-id" value={userDraft.userId} onChange={(e) => setUserDraft((d) => ({ ...d, userId: e.target.value }))} /></label>}
                <label style={{ marginLeft: editor === "user" ? 12 : 0 }}>RPM <input aria-label="capacity-rpm" type="number" min={1} value={editor === "project" ? projectDraft.rpmLimit : userDraft.rpmLimit} onChange={(e) => editor === "project" ? setProjectDraft((d) => ({ ...d, rpmLimit: Number(e.target.value) })) : setUserDraft((d) => ({ ...d, rpmLimit: Number(e.target.value) }))} /></label>
                <label style={{ marginLeft: 12 }}>TPM <input aria-label="capacity-tpm" type="number" min={1} value={editor === "project" ? projectDraft.tpmLimit : userDraft.tpmLimit} onChange={(e) => editor === "project" ? setProjectDraft((d) => ({ ...d, tpmLimit: Number(e.target.value) })) : setUserDraft((d) => ({ ...d, tpmLimit: Number(e.target.value) }))} /></label>
                <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
                  <button type="button" onClick={cancelEditor} disabled={saving}>取消</button>
                  <button type="button" data-testid="save-capacity-limit" onClick={() => void saveLimit(editor)} disabled={saving || (editor === "user" && !userDraft.userId.trim())}>{saving ? "保存中…" : "保存并重读"}</button>
                </div>
              </div>
            )}
            {saveMsg && <p role="status">{saveMsg}</p>}

            {/* 登记限制表 */}
            <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, overflow: "hidden", marginBottom: 24 }}>
              <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--aos-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>登记限制</h3>
                  <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4, margin: "4px 0 0" }}>
                    精确容量池只读投影；字段是租约用量单位和并发占用，不冒充每分钟请求或用量限额
                  </p>
                </div>
                <select
                  value={providerFilter}
                  onChange={(e) => setProviderFilter(e.target.value)}
                  aria-label="limit-provider-filter"
                  style={{ padding: "6px 12px", fontSize: 12, border: "1px solid var(--aos-border)", borderRadius: 2, background: "var(--aos-surface)" }}
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
                      <th style={{ textAlign: "left", padding: "12px 20px", background: "var(--bg-surface-alt)", borderBottom: "1px solid var(--aos-border)", fontWeight: 600, color: "var(--aos-text-secondary)", fontSize: 12 }}>租约用量单位</th>
                      <th style={{ textAlign: "left", padding: "12px 20px", background: "var(--bg-surface-alt)", borderBottom: "1px solid var(--aos-border)", fontWeight: 600, color: "var(--aos-text-secondary)", fontSize: 12 }}>并发占用</th>
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
            <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, overflow: "hidden" }}>
              <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--aos-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>用户限制</h3>
                  <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4, margin: "4px 0 0" }}>仅用户 RPM/TPM 可写；团队与日预算 API 未提供，保持只读</p>
                </div>
                <select
                  value={teamFilter}
                  onChange={(e) => setTeamFilter(e.target.value)}
                  aria-label="team-filter"
                  style={{ padding: "6px 12px", fontSize: 12, border: "1px solid var(--aos-border)", borderRadius: 2, background: "var(--aos-surface)" }}
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
                    {filteredUsers.length === 0 ? (
                      <tr>
                        <td colSpan={6} style={{ padding: "16px 20px", color: "var(--aos-faint)", fontSize: 12 }}>
                          {sourceMode === "live" ? "暂无用户限额（可在 API PUT /user-limits 写入）" : "无数据"}
                        </td>
                      </tr>
                    ) : filteredUsers.map((u) => {
                      const budgetPct = usagePercent(u.usedTodayUsd, u.dailyBudgetUsd);
                      const tone = usageTone(budgetPct);
                      return (
                        <tr key={u.user} style={{ borderBottom: "1px solid var(--aos-divider)" }}>
                          <td style={{ padding: "10px 20px", fontWeight: 500, color: "var(--aos-text)" }}>{u.user}</td>
                          <td style={{ padding: "10px 20px" }}>
                            <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 2, background: "var(--aos-surface-hover)", color: "var(--aos-text)" }}>{u.team}</span>
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
            <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 28 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 10, marginBottom: 16 }}>
                {[
                  { label: "交互保留比例", value: "20%" },
                  { label: "预留池状态", value: "未开通" },
                  { label: "项目 RPM", value: projectLimit ? String(projectLimit.rpmLimit) : "—" },
                  { label: "项目 TPM", value: projectLimit ? formatTokenCount(projectLimit.tpmLimit) : "—" },
                ].map((s) => (
                  <div key={s.label} style={{ padding: "10px 12px", border: "1px solid var(--aos-border)", borderRadius: 2 }}>
                    <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
                    <div style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{s.value}</div>
                  </div>
                ))}
              </div>
              <p style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: 0 }}>预留容量</p>
              <p style={{ fontSize: 12, color: "var(--aos-faint)", marginTop: 8, margin: "8px 0 0" }}>
                预留池控制面尚未开通；当前仅展示保留比例与项目限额快照，不伪造可用预留额度。
              </p>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Link to="/aip/model-catalog" style={{ padding: "6px 12px", borderRadius: 2, border: "1px solid var(--aos-border)", color: "var(--aos-text)", textDecoration: "none", fontSize: 12 }}>模型目录 →</Link>
              <Link to="/aip/model-router" style={{ padding: "6px 12px", borderRadius: 2, border: "1px solid var(--aos-border)", color: "var(--aos-text)", textDecoration: "none", fontSize: 12 }}>模型路由 →</Link>
              <Link to="/aip/model-providers" style={{ padding: "6px 12px", borderRadius: 2, border: "1px solid var(--aos-border)", color: "var(--aos-text)", textDecoration: "none", fontSize: 12 }}>模型供应商 →</Link>
            </div>
          </div>
        )}
      </div>
    </PageChrome>
  );
}
