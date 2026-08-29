export const BUSINESS_INVESTIGATION_READ_FLAG = "ecommerce.investigation.read" as const;
export const BUSINESS_INVESTIGATION_COMMAND_FLAG = "ecommerce.investigation.commands" as const;

export type BusinessInvestigationFeatureFlags = Readonly<
  Record<typeof BUSINESS_INVESTIGATION_READ_FLAG | typeof BUSINESS_INVESTIGATION_COMMAND_FLAG, boolean>
>;

export const CLOSED_BUSINESS_INVESTIGATION_FEATURE_FLAGS: BusinessInvestigationFeatureFlags =
  Object.freeze({ [BUSINESS_INVESTIGATION_READ_FLAG]: false, [BUSINESS_INVESTIGATION_COMMAND_FLAG]: false });

export const OPEN_BUSINESS_INVESTIGATION_READ_FEATURE: BusinessInvestigationFeatureFlags =
  Object.freeze({ [BUSINESS_INVESTIGATION_READ_FLAG]: true, [BUSINESS_INVESTIGATION_COMMAND_FLAG]: false });

export const OPEN_BUSINESS_INVESTIGATION_COMMAND_FEATURE: BusinessInvestigationFeatureFlags =
  Object.freeze({ [BUSINESS_INVESTIGATION_READ_FLAG]: true, [BUSINESS_INVESTIGATION_COMMAND_FLAG]: true });

export function resolveBusinessInvestigationFeatureFlags(
  serializedFlags: string | undefined = import.meta.env.VITE_AOS_FEATURE_FLAGS,
  development = import.meta.env.MODE === "development",
): BusinessInvestigationFeatureFlags {
  const effectiveFlags = serializedFlags === undefined && development
    ? BUSINESS_INVESTIGATION_READ_FLAG
    : (serializedFlags ?? "");
  const enabled = new Set(
    effectiveFlags
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );
  if (!enabled.has(BUSINESS_INVESTIGATION_READ_FLAG)) return CLOSED_BUSINESS_INVESTIGATION_FEATURE_FLAGS;
  return enabled.has(BUSINESS_INVESTIGATION_COMMAND_FLAG)
    ? OPEN_BUSINESS_INVESTIGATION_COMMAND_FEATURE
    : OPEN_BUSINESS_INVESTIGATION_READ_FEATURE;
}

export function isBusinessInvestigationCommandEnabled(
  flags: BusinessInvestigationFeatureFlags,
): boolean {
  return flags[BUSINESS_INVESTIGATION_READ_FLAG] === true && flags[BUSINESS_INVESTIGATION_COMMAND_FLAG] === true;
}

export function isBusinessInvestigationReadEnabled(
  flags: BusinessInvestigationFeatureFlags,
): boolean {
  return flags[BUSINESS_INVESTIGATION_READ_FLAG] === true;
}
