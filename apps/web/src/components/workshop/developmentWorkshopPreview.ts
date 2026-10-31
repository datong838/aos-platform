import type { EcommerceWorkshopModule } from "../../api/ecommerceWorkshop";
import { isLoginGateSkipped } from "../../config/devAuthBypass";
import { getAccessToken, getTenant } from "../../api/tenant";
import { WORKSHOP_ACCEPTANCE_MODULES } from "./workshopAcceptance";

const PREVIEW_HASH = `sha256:${"0".repeat(64)}`;

export const DEVELOPMENT_WORKSHOP_PREVIEW_MODULES: readonly EcommerceWorkshopModule[] =
  WORKSHOP_ACCEPTANCE_MODULES.map((item, index) => ({
    moduleId: item.moduleId,
    displayName: item.label,
    menuLabel: item.label,
    route: item.route,
    slot: "workshop.primary.ecommerce",
    order: (index + 1) * 10,
    installationRef: {
      installationId: "development-preview-not-installed",
      revision: 0,
      compositionId: "development-preview-not-installed",
      lockRevision: 0,
      lockHash: PREVIEW_HASH,
      overlayRevision: "development-preview",
    },
    moduleRef: {
      publisher: "aos.ecommerce",
      bundleId: `development-preview.${item.moduleId}`,
      version: "0.0.0-preview",
      bundleContentHash: PREVIEW_HASH,
      moduleArtifactRef: `development-preview://${item.moduleId}`,
      moduleArtifactHash: PREVIEW_HASH,
    },
    readiness: "unknown",
    blockers: [{
      dependencyType: "installation",
      dependencyId: item.moduleId,
      state: "unknown",
      reasonCode: "DEVELOPMENT_PREVIEW_LOGIN_REQUIRED",
      recoverable: true,
      requiredAction: "登录后读取栖月汇当前有效安装与业务数据",
      ref: null,
    }],
    dependencyRefs: [],
    permissions: { roles: [], markings: [], dataScopes: [], actionTypes: [] },
    requiredObjects: [],
    requiredCapabilities: [],
    requiredAipFeatures: [],
    viewRefs: [],
    evalPackRefs: [],
    productionContractRefs: [],
    responsibilityTemplateRefs: [],
    impactCalculatorRefs: [],
    legacyAssetRefs: [],
    legacyRoutes: [],
    minimumRuntimeVersion: "development-preview",
    lastReceiptRef: null,
  }));

export function canUseDevelopmentWorkshopPreview(status: number | null): boolean {
  const tenant = getTenant();
  return status === 401
    && isLoginGateSkipped()
    && getAccessToken() === null
    && tenant.orgId === "org-org"
    && tenant.projectId === "dev-project";
}
