/** 栖月汇续期材料默认值（非签名）；提议须与 activation-candidate 精确一致方可提交。 */
export const QYH_COST_RENEWAL = {
  tenant: { orgId: "org-org", projectId: "dev-project" } as const,
  budgetId: "a0v-ecommerce-hard-stop-budget-v1",
  authorization: {
    providerModelId: "agnes-2.5-flash",
    currency: "CNY" as const,
    dailyLimitMinor: 10_000,
    monthlyLimitMinor: 100_000,
    effectiveUntil: "2027-03-31T04:00:00Z",
  },
  provider: {
    assetType: "ProviderInstanceRevision" as const,
    assetId: "a0v-agnes-text-readonly-dev",
    revision: 1,
    contentHash: "66941c4bb51757f5d95a6149580f7bbb3dbe86debb2035747fa96229efb06982",
  },
  risk: { perRequestRiskMinor: 10, totalRiskMinor: 100, maxRequests: 10 },
};
