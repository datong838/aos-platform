export const BUSINESS_INVESTIGATION_SHARED_SCHEMA_VERSION = "aos.business-investigation.shared/v1" as const;
export const DATA_REQUIREMENT_SCHEMA_VERSION = "aos.data-requirement/v1" as const;
export const DATA_FULFILLMENT_SCHEMA_VERSION = "aos.data-fulfillment-receipt/v1" as const;
export const PLATFORM_OBSERVATION_SCHEMA_VERSION = "aos.platform-observation/v1" as const;
export const SOURCE_MAPPING_SCHEMA_VERSION = "aos.source-mapping/v1" as const;
export const ADAPTIVE_PROFILE_SCHEMA_VERSION = "aos.adaptive-profile/v1" as const;
export const SEMANTIC_HYDRATION_SCHEMA_VERSION = "aos.semantic-hydration-receipt/v1" as const;

export type InvestigationTenant = { orgId: string; projectId: string };
export type InvestigationExactRef = {
  resourceType: string;
  resourceId: string;
  revision: number | string;
  contentHash: string;
  receiptId?: string;
};
export type InvestigationPlatform = "niushop" | "wechat_store" | "douyin_store";
export type InvestigationBlocker = {
  code: string;
  severity: "warning" | "blocking";
  dependency: string;
  requiredAction: string;
};
export type InvestigationCoverage = { required: number; fulfilled: number; unknown: number };
export type InvestigationFreshness = {
  status: "fresh" | "stale" | "unknown";
  dataCutoff: string | null;
  expiresAt: string | null;
};
export type InvestigationReadiness = {
  status: "ready" | "blocked" | "stale" | "unknown";
  sourceReadinessRef: InvestigationExactRef | null;
  coverage: InvestigationCoverage;
  freshness: InvestigationFreshness;
  blockers: InvestigationBlocker[];
};
export type InvestigationChannel = {
  channelId: string;
  platform: InvestigationPlatform;
  displayName: string;
  channelRef: InvestigationExactRef;
};
export type InvestigationBusinessEntity = {
  businessEntityId: string;
  entityType: string;
  displayName: string;
  channelRef: InvestigationExactRef;
};
export type BusinessInvestigationSharedEnvelope = {
  schemaVersion: typeof BUSINESS_INVESTIGATION_SHARED_SCHEMA_VERSION;
  tenant: InvestigationTenant;
  channel: InvestigationChannel;
  businessEntity: InvestigationBusinessEntity;
  caseRef: InvestigationExactRef;
  runRef: InvestigationExactRef;
  readiness: InvestigationReadiness;
  artifactRefs: InvestigationExactRef[];
};

export type DataRequirementStatus = "requested" | "accepted" | "planned" | "fulfilled" | "rejected" | "cancelled" | "unknown";
export type DataRequirementContract = {
  schemaVersion: typeof DATA_REQUIREMENT_SCHEMA_VERSION;
  tenant: InvestigationTenant;
  requirementId: string;
  caseRef: InvestigationExactRef;
  runRef: InvestigationExactRef;
  purpose: string;
  factTypes: string[];
  status: DataRequirementStatus;
  requestedAt: string;
  blockers: InvestigationBlocker[];
};

export type DataFulfillmentStatus = "fulfilled" | "partial" | "rejected" | "unknown";
export type DataFulfillmentReceiptContract = {
  schemaVersion: typeof DATA_FULFILLMENT_SCHEMA_VERSION;
  tenant: InvestigationTenant;
  fulfillmentId: string;
  requirementRef: InvestigationExactRef;
  status: DataFulfillmentStatus;
  artifactRefs: InvestigationExactRef[];
  fulfilledAt: string;
  blockers: InvestigationBlocker[];
};

export type ObservationLifecycle = "draft" | "ready" | "running" | "paused" | "blocked" | "unknown" | "reconciling" | "completed" | "cancelled";
export type PlatformObservationContract = {
  schemaVersion: typeof PLATFORM_OBSERVATION_SCHEMA_VERSION;
  tenant: InvestigationTenant;
  observationId: string;
  status: ObservationLifecycle;
  observedAt: string;
  sourceRef: InvestigationExactRef;
  evidenceRefs: InvestigationExactRef[];
  blockers: InvestigationBlocker[];
};

export type SourceMappingContract = {
  schemaVersion: typeof SOURCE_MAPPING_SCHEMA_VERSION;
  tenant: InvestigationTenant;
  mappingId: string;
  observationRef: InvestigationExactRef;
  sourceField: string;
  canonicalField: string;
  confidence: number;
  confirmedBy: string | null;
  blockers: InvestigationBlocker[];
};

export type AdaptiveProfileContract = {
  schemaVersion: typeof ADAPTIVE_PROFILE_SCHEMA_VERSION;
  tenant: InvestigationTenant;
  profileId: string;
  sourceRef: InvestigationExactRef;
  hypothesisRefs: InvestigationExactRef[];
  coverage: InvestigationCoverage;
  blockers: InvestigationBlocker[];
};

export type SemanticHydrationStatus = "succeeded" | "partial" | "blocked" | "unknown";
export type SemanticHydrationReceiptContract = {
  schemaVersion: typeof SEMANTIC_HYDRATION_SCHEMA_VERSION;
  tenant: InvestigationTenant;
  hydrationId: string;
  status: SemanticHydrationStatus;
  observationRef: InvestigationExactRef;
  mappingRef: InvestigationExactRef;
  outputRefs: InvestigationExactRef[];
  hydratedAt: string;
  blockers: InvestigationBlocker[];
};
