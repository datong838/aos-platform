import type {
  EcommerceWorkshopModule,
  EcommerceWorkshopModuleListResponse,
  WorkshopReadiness,
} from "../../api/ecommerceWorkshop";

const HASH_A = `sha256:${"a".repeat(64)}`;
const HASH_B = `sha256:${"b".repeat(64)}`;

export function workshopModuleFixture(
  overrides: Partial<EcommerceWorkshopModule> = {},
): EcommerceWorkshopModule {
  const moduleId = overrides.moduleId ?? "ecommerce.operations";
  return {
    moduleId,
    displayName: "统一运营驾驶舱",
    menuLabel: "统一运营驾驶舱",
    route: "/workshop/operations",
    slot: "workshop.primary.ecommerce",
    order: 30,
    installationRef: {
      installationId: "11111111-1111-4111-8111-111111111111",
      revision: 3,
      compositionId: "22222222-2222-4222-8222-222222222222",
      lockRevision: 7,
      lockHash: HASH_A,
      overlayRevision: "overlay-r3",
    },
    moduleRef: {
      publisher: "aos.ecommerce",
      bundleId: "solution.ecommerce.operations-base",
      version: "1.0.0",
      bundleContentHash: HASH_A,
      moduleArtifactRef: `bundle://catalog/solutions/ecommerce/content/workshops/${moduleId}.json`,
      moduleArtifactHash: HASH_B,
    },
    readiness: "available",
    blockers: [],
    permissions: {
      roles: ["operator"],
      markings: ["public"],
      dataScopes: ["orders:read"],
      actionTypes: [],
    },
    requiredObjects: ["Order"],
    requiredCapabilities: ["commerce.order.read"],
    requiredAipFeatures: [],
    viewRefs: [],
    evalPackRefs: [],
    productionContractRefs: [],
    responsibilityTemplateRefs: [],
    impactCalculatorRefs: [],
    legacyAssetRefs: ["W01"],
    legacyRoutes: ["/s2/orders", "/workshop/inventory", "/workshop/orders"],
    minimumRuntimeVersion: "1.0.0",
    lastReceiptRef: null,
    ...overrides,
  };
}

export function workshopCatalogFixture({
  orgId = "org-org",
  projectId = "dev-project",
  items = [workshopModuleFixture()],
}: {
  orgId?: string;
  projectId?: string;
  items?: EcommerceWorkshopModule[];
} = {}): EcommerceWorkshopModuleListResponse {
  return {
    schemaVersion: "aos.ecommerce-workshop/v1",
    tenant: { orgId, projectId },
    evaluatedAt: "2026-08-14T10:00:00.000Z",
    dataCutoff: "2026-08-14T09:59:00.000Z",
    items,
    count: items.length,
  };
}

export function moduleWithReadiness(
  readiness: WorkshopReadiness,
): EcommerceWorkshopModule {
  return workshopModuleFixture({
    readiness,
    blockers:
      readiness === "available"
        ? []
        : [
            {
              dependencyType: "capability",
              dependencyId: "commerce.order.read",
              state: readiness === "degraded" ? "degraded" : "unknown",
              reasonCode: "DEPENDENCY_NOT_GREEN",
              recoverable: true,
              requiredAction: "等待 capability authority 可验证后重新检查",
              ref: null,
            },
          ],
  });
}
