export const BUSINESS_INVESTIGATION_READ_FLAG = "ecommerce.investigation.read" as const;

export type BusinessInvestigationFeatureFlags = Readonly<
  Record<typeof BUSINESS_INVESTIGATION_READ_FLAG, boolean>
>;

export const CLOSED_BUSINESS_INVESTIGATION_FEATURE_FLAGS: BusinessInvestigationFeatureFlags =
  Object.freeze({ [BUSINESS_INVESTIGATION_READ_FLAG]: false });

export const OPEN_BUSINESS_INVESTIGATION_READ_FEATURE: BusinessInvestigationFeatureFlags =
  Object.freeze({ [BUSINESS_INVESTIGATION_READ_FLAG]: true });

export function resolveBusinessInvestigationFeatureFlags(
  serializedFlags: string | undefined = import.meta.env.VITE_AOS_FEATURE_FLAGS,
): BusinessInvestigationFeatureFlags {
  const enabled = new Set(
    (serializedFlags ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );
  return enabled.has(BUSINESS_INVESTIGATION_READ_FLAG)
    ? OPEN_BUSINESS_INVESTIGATION_READ_FEATURE
    : CLOSED_BUSINESS_INVESTIGATION_FEATURE_FLAGS;
}

export function isBusinessInvestigationReadEnabled(
  flags: BusinessInvestigationFeatureFlags,
): boolean {
  return flags[BUSINESS_INVESTIGATION_READ_FLAG] === true;
}
