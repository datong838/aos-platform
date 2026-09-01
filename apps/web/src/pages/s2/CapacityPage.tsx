import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../../api/client";
import { aipModelRuntime, type ModelRuntimeCostOverview, type RuntimeCapacityPoolSummary, type RuntimeQuotaAuthoritySummary, type RuntimeUsageAttributionDimension } from "../../api/aipModelRuntime";
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
  observed?: boolean;
  receiptCount?: number;
  measuredCount?: number;
  estimatedCount?: number;
  unknownCount?: number;
  providerCounts?: Record<string, number>;
  timeZone?: string;
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
  dailyBudgetUsd: number | null;
  usedTodayUsd: number | null;
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
    dailyBudgetUsd: null,
    usedTodayUsd: null,
  };
}

export function usageBucketsFromAuthority(cost: ModelRuntimeCostOverview): UsageBucket[] {
  const labels = { today: "今日", week: "近 7 天", month: "近 30 天" } as const;
  return (["today", "week", "month"] as const).map((period) => {
    const item = cost.usage.periods.find((candidate) => candidate.period === period);
    const totals = item?.quantityTotals ?? {};
    const tokenTotal = Object.entries(totals)
      .filter(([key]) => /^(input_token|output_token|cached_token):/.test(key))
      .reduce((sum, [, amount]) => sum + amount, 0);
    return {
      period,
      label: labels[period],
      totalRequests: 0,
      totalTokens: tokenTotal,
      totalCostUsd: totals["cost:USD"] ?? 0,
      observed: Boolean(item?.receiptCount),
      receiptCount: item?.receiptCount ?? 0,
      measuredCount: item?.measuredCount ?? 0,
      estimatedCount: item?.estimatedCount ?? 0,
      unknownCount: item?.unknownCount ?? 0,
      providerCounts: item?.providerCounts ?? {},
      timeZone: item?.timeZone,
    };
  });
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
    tokensPerMin: `每次租约 ${formatTokenCount(pool.tokenUnitPerReservation)} 个模型用量单位`,
    requestsPerMin: `当前并发 ${pool.activeReservations}/${pool.maxConcurrency}`,
  }));
}

export function authoritativeCostLabel(cost: ModelRuntimeCostOverview | null): string {
  if (!cost || cost.usage.state === "unobserved") return "未观测";
  const totals = Object.entries(cost.usage.costTotals);
  if (!totals.length) return cost.usage.state === "unknown" ? "未知" : "尚无实际模型调用记录";
  return totals.map(([currency, amount]) => `${currency} ${amount.toFixed(2)}`).join(" · ");
}

export function attributionDimensionLabel(dimension: RuntimeUsageAttributionDimension["dimension"]): string {
  return ({ tenant: "租户总览", task: "经营任务", agent: "数字同事", logic: "业务逻辑", model: "模型" } as const)[dimension];
}

export function nextQuotaRevisionBody(quota: RuntimeQuotaAuthoritySummary, rpmLimit: number, tpmLimit: number) {
  if (!quota.headRef || !quota.headVersion || !quota.owner || !quota.approvalRef || !quota.lifecycle
    || !quota.effectiveFrom || !quota.effectiveUntil || !quota.maxConcurrency || !quota.maxInputTokens
    || !quota.maxOutputTokens || !quota.hourlyRequestLimit || !quota.dailyRequestLimit
    || !quota.reservationLeaseSeconds || !quota.overflowBehavior
    || quota.allowPublicProviderFallback === null || quota.allowAutoScale === null) {
    throw new Error("当前配额版本缺少创建下一版本所需的精确字段");
  }
  return {
    policyId: quota.headRef.assetId,
    revision: quota.headRef.revision + 1,
    environment: "development",
    effectiveFrom: quota.effectiveFrom,
    effectiveUntil: quota.effectiveUntil,
    owner: quota.owner,
    approvalRef: quota.approvalRef,
    lifecycle: quota.lifecycle,
    rpmLimit,
    tpmLimit,
    maxConcurrency: quota.maxConcurrency,
    maxInputTokens: quota.maxInputTokens,
    maxOutputTokens: quota.maxOutputTokens,
    hourlyRequestLimit: quota.hourlyRequestLimit,
    dailyRequestLimit: quota.dailyRequestLimit,
    reservationLeaseSeconds: quota.reservationLeaseSeconds,
    overflowBehavior: quota.overflowBehavior,
    allowPublicProviderFallback: quota.allowPublicProviderFallback,
    allowAutoScale: quota.allowAutoScale,
  };
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
  const [runtimeCost, setRuntimeCost] = useState<ModelRuntimeCostOverview | null>(null);
  const [runtimeLimits, setRuntimeLimits] = useState<RateLimit[]>([]);
  const [runtimePools, setRuntimePools] = useState<RuntimeCapacityPoolSummary[]>([]);
  const [quotaRpmDraft, setQuotaRpmDraft] = useState("");
  const [quotaTpmDraft, setQuotaTpmDraft] = useState("");
  const [quotaSaveState, setQuotaSaveState] = useState<string | null>(null);
  const [quotaSaving, setQuotaSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [runtime, cost] = await Promise.all([
          aipModelRuntime.overview(),
          aipModelRuntime.costOverview(),
        ]);
        if (cancelled) return;
        const buckets = usageBucketsFromAuthority(cost);
        const quota = cost.quotas.find((item) => item.rpmLimit !== null && item.tpmLimit !== null);
        const pl: ProjectLimit | null = quota ? {
          rpmLimit: quota.rpmLimit!,
          tpmLimit: quota.tpmLimit!,
          scopeKey: quota.headRef?.assetId || quota.quotaPolicyRef.assetId,
        } : null;
        setUsageBuckets(buckets);
        setProjectLimit(pl);
        setQuotaUsage([]);
        setUserLimits([]);
        setRuntimeLimits(rateLimitsFromRuntimePools(runtime.capacityPools));
        setRuntimePools(runtime.capacityPools);
        setRuntimeCost(cost);
        setQuotaRpmDraft(quota?.rpmLimit ? String(quota.rpmLimit) : "");
        setQuotaTpmDraft(quota?.tpmLimit ? String(quota.tpmLimit) : "");
        setSourceMode("live");
        setLoadError(null);
      } catch (e) {
        if (cancelled) return;
        setUsageBuckets(mapUsageItemsToBuckets([]));
        setQuotaUsage([]);
        setUserLimits([]);
        setProjectLimit(null);
        setRuntimeLimits([]);
        setRuntimePools([]);
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
  const currentAttributions = useMemo(
    () => runtimeCost?.usage.periods.find((item) => item.period === usagePeriod)?.attributionDimensions ?? [],
    [runtimeCost, usagePeriod],
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

  const todayBucket = usageBuckets.find((b) => b.period === "today");
  const warnQuotaCount = quotaUsage.filter((q) => usageTone(usagePercent(q.used, q.quota)) !== "ok").length;
  const editableQuota = runtimeCost?.quotas.find((item) => item.headRef && item.headVersion) ?? null;

  async function saveQuotaRevision() {
    if (!editableQuota) return;
    const rpm = Number(quotaRpmDraft);
    const tpm = Number(quotaTpmDraft);
    if (!Number.isInteger(rpm) || rpm < 1 || !Number.isInteger(tpm) || tpm < 1) {
      setQuotaSaveState("RPM 与 TPM 必须是正整数");
      return;
    }
    setQuotaSaving(true);
    setQuotaSaveState(null);
    try {
      const body = nextQuotaRevisionBody(editableQuota, rpm, tpm);
      await apiPost("/v1/aip/model-governance-policies/quotas", body, {
        "Idempotency-Key": `capacity-quota-${editableQuota.headRef!.assetId}-${body.revision}-${rpm}-${tpm}`,
        "If-Match": String(editableQuota.headVersion),
      });
      const refreshed = await aipModelRuntime.costOverview();
      const reread = refreshed.quotas.find((item) => item.headRef?.assetId === editableQuota.headRef?.assetId);
      if (!reread || reread.headRef?.revision !== body.revision || reread.rpmLimit !== rpm || reread.tpmLimit !== tpm) {
        throw new Error("新版本已提交，但精确重读不一致");
      }
      setRuntimeCost(refreshed);
      setProjectLimit({ rpmLimit: rpm, tpmLimit: tpm, scopeKey: reread.headRef.assetId });
      setQuotaSaveState(`配额版本 ${body.revision} 已保存并精确重读；运行绑定仍保持 ${reread.quotaPolicyRef.assetId}@${reread.quotaPolicyRef.revision}`);
    } catch (error) {
      setQuotaSaveState(`保存失败：${(error as Error).message}`);
    } finally {
      setQuotaSaving(false);
    }
  }

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
            { label: "今日 Usage Receipt", value: todayBucket?.observed ? String(todayBucket.receiptCount) : "未观测" },
            { label: "今日模型用量", value: todayBucket?.observed ? formatTokenCount(todayBucket.totalTokens) : "缺少凭证" },
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
                  color: tab === t.id ? "var(--aos-indigo-600)" : "var(--aos-text-secondary)",
                  background: "none",
                  borderTop: "none",
                  borderLeft: "none",
                  borderRight: "none",
                  borderBottom: tab === t.id ? "2px solid var(--aos-indigo-600)" : "2px solid transparent",
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
            <p style={{ margin: "-8px 0 0", fontSize: 11, color: "var(--aos-faint)" }}>
              业务时区 {currentBucket?.timeZone || "待权威返回"} · 周/月为滚动 7/30 天
            </p>

            {/* Metrics cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
              <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 20 }}>
                <div style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4 }}>Usage Receipt</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--aos-indigo-600)" }}>{currentBucket?.observed ? currentBucket.receiptCount : "未观测"}</div>
                <div style={{ fontSize: 11, color: "var(--aos-faint)", marginTop: 4 }}>{currentBucket?.observed ? `实测 ${currentBucket.measuredCount} · 估算 ${currentBucket.estimatedCount} · 未知 ${currentBucket.unknownCount}` : "没有权威用量凭证，不解释为 0"}</div>
              </div>
              <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 20 }}>
                <div style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4 }}>模型用量</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--aos-purple-600)" }}>{currentBucket?.observed ? formatTokenCount(currentBucket.totalTokens) : "缺少凭证"}</div>
                <div style={{ fontSize: 11, color: "var(--aos-faint)", marginTop: 4 }}>{currentBucket?.observed ? `${currentBucket.totalTokens.toLocaleString()} 个 Token 用量单位` : "只汇总 input/output/cached token Receipt"}</div>
              </div>
              <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 20 }}>
                <div style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginBottom: 4 }}>成本汇总</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--aos-amber-600)" }}>{authoritativeCostLabel(runtimeCost)}</div>
                <div style={{ fontSize: 11, color: "var(--aos-faint)", marginTop: 4 }}>用量凭证为权威；未观测不等于 0</div>
              </div>
            </div>

            <section data-testid="usage-attribution-dimensions" style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
                <h3 style={{ margin: 0, fontSize: 14 }}>用量归因</h3>
                <span style={{ fontSize: 11, color: "var(--aos-faint)" }}>租户与任务来自权威范围/谱系；其余维度只认显式归因凭证</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5,minmax(0,1fr))", gap: 10 }}>
                {currentAttributions.map((dimension) => (
                  <article key={dimension.dimension} style={{ border: "1px solid var(--aos-border)", borderRadius: 2, padding: 12, minWidth: 0 }}>
                    <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{attributionDimensionLabel(dimension.dimension)}</div>
                    <div style={{ fontSize: 22, fontWeight: 700, marginTop: 3 }}>{dimension.attributedReceiptCount}</div>
                    <div style={{ fontSize: 11, color: dimension.missingReceiptCount ? "var(--aos-amber-600)" : "var(--aos-green-600)", marginTop: 3 }}>
                      {dimension.missingReceiptCount ? `${dimension.missingReceiptCount} 条暂无归因凭证` : "本周期凭证已覆盖"}
                    </div>
                    {dimension.entries.slice(0, 2).map((entry, index) => (
                      <details key={`${entry.subjectId}:${entry.subjectRevision}`} style={{ marginTop: 8, fontSize: 11 }}>
                        <summary style={{ cursor: "pointer", color: "var(--aos-text)" }}>
                          {dimension.dimension === "tenant" ? "栖月汇微商城" : `${attributionDimensionLabel(dimension.dimension)} ${index + 1}`} · {entry.receiptCount} 条
                        </summary>
                        <div style={{ color: "var(--aos-faint)", overflowWrap: "anywhere", marginTop: 4 }}>
                          权威引用 {entry.subjectId}@{entry.subjectRevision}
                        </div>
                      </details>
                    ))}
                    {!dimension.entries.length && <div style={{ fontSize: 11, color: "var(--aos-faint)", marginTop: 8 }}>暂无可展示记录</div>}
                  </article>
                ))}
              </div>
            </section>

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
                  <p style={{ fontSize: 12, color: "var(--aos-faint)", margin: 0 }}>缺少今日 Usage Receipt，暂不计算配额消耗比例。</p>
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
                {editableQuota && (
                  <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 8, alignItems: "end" }}>
                    <label style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>RPM
                      <input aria-label="quota-rpm" value={quotaRpmDraft} onChange={(event) => setQuotaRpmDraft(event.target.value)} inputMode="numeric" style={{ display: "block", width: "100%", boxSizing: "border-box", marginTop: 4, padding: "7px 8px", border: "1px solid var(--aos-border)" }} />
                    </label>
                    <label style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>TPM
                      <input aria-label="quota-tpm" value={quotaTpmDraft} onChange={(event) => setQuotaTpmDraft(event.target.value)} inputMode="numeric" style={{ display: "block", width: "100%", boxSizing: "border-box", marginTop: 4, padding: "7px 8px", border: "1px solid var(--aos-border)" }} />
                    </label>
                    <button type="button" data-testid="save-quota-revision" disabled={quotaSaving} onClick={saveQuotaRevision} style={{ padding: "8px 12px" }}>{quotaSaving ? "保存中" : "保存新版本"}</button>
                  </div>
                )}
                {quotaSaveState && <p role="status" style={{ margin: "10px 0 0", fontSize: 11, color: quotaSaveState.startsWith("保存失败") ? "var(--aos-red)" : "var(--aos-green-600)" }}>{quotaSaveState}</p>}
                <div style={{ marginTop: 12, display: "flex", gap: 14, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 11, color: "var(--aos-faint)" }}>当前 head {editableQuota?.headRef ? `${editableQuota.headRef.assetId}@${editableQuota.headRef.revision}` : "缺少精确版本"}</span>
                  <Link data-testid="manage-project-limit" to="/aip/model-router" style={{ display: "inline-flex", alignItems: "center", fontSize: 12, fontWeight: 500, color: "var(--aos-indigo-600)", textDecoration: "none" }}>查看运行绑定与路由 →</Link>
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
                  <Link data-testid="manage-user-limit" to="/aip/model-router" style={{ display: "inline-flex", alignItems: "center", fontSize: 13, fontWeight: 500, color: "var(--aos-indigo-600)", textDecoration: "none" }}>进入版本化运行策略 →</Link>
                </div>
              </div>
            </div>

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
                  <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4, margin: "4px 0 0" }}>兼容 RPM/TPM 只读；预算与消耗只在存在权威预算和 Usage Receipt 时展示</p>
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
                          {sourceMode === "live" ? "当前没有单独用户限额，统一继承项目默认限额。" : "用户限额读取失败。"}
                        </td>
                      </tr>
                    ) : filteredUsers.map((u) => {
                      const hasBudgetEvidence = u.usedTodayUsd !== null && u.dailyBudgetUsd !== null;
                      const budgetPct = hasBudgetEvidence ? usagePercent(u.usedTodayUsd!, u.dailyBudgetUsd!) : null;
                      const tone = budgetPct === null ? "warn" : usageTone(budgetPct);
                      return (
                        <tr key={u.user} style={{ borderBottom: "1px solid var(--aos-divider)" }}>
                          <td style={{ padding: "10px 20px", fontWeight: 500, color: "var(--aos-text)" }}>{u.user}</td>
                          <td style={{ padding: "10px 20px" }}>
                            <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 2, background: "var(--aos-surface-hover)", color: "var(--aos-text)" }}>{u.team}</span>
                          </td>
                          <td style={{ padding: "10px 20px", color: "var(--aos-text)" }}>{u.rpmLimit}</td>
                          <td style={{ padding: "10px 20px", color: "var(--aos-text)" }}>{formatTokenCount(u.tpmLimit)}</td>
                          <td style={{ padding: "10px 20px", color: "var(--aos-text)" }}>{u.dailyBudgetUsd === null ? "缺少预算权威" : formatUsd(u.dailyBudgetUsd)}</td>
                          <td style={{ padding: "10px 20px" }}>
                            <span style={{
                              fontWeight: 600,
                              color: tone === "danger" ? "var(--aos-red)" : tone === "warn" ? "var(--aos-amber)" : "var(--aos-green-600)",
                            }}>
                              {u.usedTodayUsd === null ? "缺少 Usage Receipt" : formatUsd(u.usedTodayUsd)}
                            </span>
                            {budgetPct !== null && <span style={{ fontSize: 11, color: "var(--aos-faint)", marginLeft: 4 }}>({budgetPct}%)</span>}
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
                  { label: "exact 容量池", value: String(runtimePools.length) },
                  { label: "活动容量池", value: String(runtimePools.filter((pool) => pool.lifecycle === "active").length) },
                  { label: "活动租约", value: String(runtimePools.reduce((sum, pool) => sum + pool.activeReservations, 0)) },
                  { label: "已预留用量", value: formatTokenCount(runtimePools.reduce((sum, pool) => sum + pool.reservedTokenUnits, 0)) },
                  { label: "项目 RPM", value: projectLimit ? String(projectLimit.rpmLimit) : "—" },
                  { label: "项目 TPM", value: projectLimit ? formatTokenCount(projectLimit.tpmLimit) : "—" },
                ].map((s) => (
                  <div key={s.label} style={{ padding: "10px 12px", border: "1px solid var(--aos-border)", borderRadius: 2 }}>
                    <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
                    <div style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{s.value}</div>
                  </div>
                ))}
              </div>
              <p style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: 0 }}>预留容量 · exact CapacityPool</p>
              <p style={{ fontSize: 12, color: "var(--aos-faint)", margin: "8px 0 16px" }}>池、模型、供应商和路由均按精确 revision/hash 读取；达到并发或用量上限时必须回到版本化路由策略选择排队或降级。</p>
              <div data-testid="runtime-capacity-pools" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))", gap: 12 }}>
                {runtimePools.map((pool) => {
                  const concurrencyPct = usagePercent(pool.activeReservations, pool.maxConcurrency);
                  const tokenPct = usagePercent(pool.reservedTokenUnits, pool.maxTokenUnits);
                  const saturated = concurrencyPct >= 100 || tokenPct >= 100;
                  return (
                    <article key={`${pool.poolId}@${pool.revision}`} style={{ border: `1px solid ${saturated ? "var(--aos-amber)" : "var(--aos-border)"}`, padding: 16, borderRadius: 2 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{pool.modelRef.assetId}</strong><span style={{ color: saturated ? "var(--aos-amber-600)" : "var(--aos-green-600)" }}>{saturated ? "容量已满" : pool.lifecycle === "active" ? "可分配" : "只读"}</span></div>
                      <p style={{ margin: "8px 0", color: "var(--aos-text-secondary)", fontSize: 12 }}>{pool.providerRef.assetId} · 租约 {pool.leaseSeconds} 秒 · 每次 {pool.tokenUnitPerReservation} 单位</p>
                      <p style={{ margin: "4px 0", fontSize: 12 }}>并发 {pool.activeReservations}/{pool.maxConcurrency}（{concurrencyPct}%）</p>
                      <p style={{ margin: "4px 0", fontSize: 12 }}>用量 {pool.reservedTokenUnits}/{pool.maxTokenUnits}（{tokenPct}%）</p>
                      <details><summary>精确引用与安全处置</summary><code>{pool.poolId}@{pool.revision}</code><p style={{ fontSize: 12 }}>route {pool.routeRef.assetId}@{pool.routeRef.revision}；容量已满时不自动扩大，进入版本化路由策略选择排队、降级或预算硬停。</p></details>
                    </article>
                  );
                })}
                {runtimePools.length === 0 && <div className="notice">当前租户没有已发布的 exact 容量池，因此不会取得模型容量租约；请在模型运行时登记并验证容量池后再执行。</div>}
              </div>
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
