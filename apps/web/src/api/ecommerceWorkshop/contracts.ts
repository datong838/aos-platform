export const ECOMMERCE_WORKSHOP_SCHEMA_VERSION = "aos.ecommerce-workshop/v1" as const;

export type WorkshopReadiness = "available" | "degraded" | "disabled" | "blocked" | "unknown";
export type WorkshopDependencyState = WorkshopReadiness;
export type WorkshopDependencyType = "object" | "capability" | "aip_feature" | "data_scope" | "permission" | "registry" | "installation";

export type WorkshopTenant = { orgId: string; projectId: string };
export type WorkshopInstallationRef = {
  installationId: string;
  revision: number;
  compositionId: string;
  lockRevision: number;
  lockHash: string;
  overlayRevision: string;
};
export type WorkshopModuleRef = {
  publisher: string;
  bundleId: string;
  version: string;
  bundleContentHash: string;
  moduleArtifactRef: string;
  moduleArtifactHash: string;
};
export type WorkshopDependencyRef = {
  resourceType: string;
  resourceId: string;
  revision: string | null;
  contentHash: string | null;
  authority: string;
};
export type WorkshopReadinessBlocker = {
  dependencyType: WorkshopDependencyType;
  dependencyId: string;
  state: WorkshopDependencyState;
  reasonCode: string;
  recoverable: boolean;
  requiredAction: string;
  ref: WorkshopDependencyRef | null;
};
export type WorkshopPermissions = {
  roles: string[];
  markings: string[];
  dataScopes: string[];
  actionTypes: string[];
};
export type EcommerceWorkshopModule = {
  moduleId: string;
  displayName: string;
  menuLabel: string;
  route: string;
  slot: "workshop.primary.ecommerce";
  order: number;
  installationRef: WorkshopInstallationRef;
  moduleRef: WorkshopModuleRef;
  readiness: WorkshopReadiness;
  blockers: WorkshopReadinessBlocker[];
  permissions: WorkshopPermissions;
  requiredObjects: string[];
  requiredCapabilities: string[];
  requiredAipFeatures: string[];
  viewRefs: string[];
  evalPackRefs: string[];
  productionContractRefs: string[];
  responsibilityTemplateRefs: string[];
  impactCalculatorRefs: string[];
  legacyAssetRefs: string[];
  legacyRoutes: string[];
  minimumRuntimeVersion: string;
  lastReceiptRef: WorkshopDependencyRef | null;
};
export type EcommerceWorkshopModuleListResponse = {
  schemaVersion: typeof ECOMMERCE_WORKSHOP_SCHEMA_VERSION;
  tenant: WorkshopTenant;
  evaluatedAt: string;
  dataCutoff: string | null;
  items: EcommerceWorkshopModule[];
  count: number;
};
export type EcommerceWorkshopModuleReadinessResponse = {
  schemaVersion: typeof ECOMMERCE_WORKSHOP_SCHEMA_VERSION;
  tenant: WorkshopTenant;
  evaluatedAt: string;
  dataCutoff: string | null;
  item: EcommerceWorkshopModule;
};

export type EcommerceWorkshopApiErrorBody = {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  traceId: string;
};
