export const WORKSHOP_ACCEPTANCE_MODULES = [
  { moduleId: "ecommerce.task-cockpit", route: "/workshop/task-cockpit", label: "日常任务总控大屏", tabModel: false },
  { moduleId: "ecommerce.content-campaign", route: "/workshop/content-campaign", label: "内容与活动工作台", tabModel: false },
  { moduleId: "ecommerce.operations", route: "/workshop/operations", label: "统一运营驾驶舱", tabModel: false },
  { moduleId: "ecommerce.creator-growth", route: "/workshop/creator-outreach", label: "达人邀约与签约驾驶舱", tabModel: false },
  { moduleId: "ecommerce.media-studio", route: "/workshop/media-studio", label: "多媒体任务全过程闭环工作台", tabModel: true },
  { moduleId: "ecommerce.analyst", route: "/workshop/analyst", label: "经营参谋·增长指挥中心", tabModel: true },
  { moduleId: "ecommerce.price-governance", route: "/workshop/pricing-governance", label: "价格治理驾驶舱", tabModel: true },
  { moduleId: "ecommerce.customer", route: "/workshop/customer", label: "客户关系工作台", tabModel: true },
] as const;

export const WORKSHOP_ACCEPTANCE_VIEWPORTS = [1280, 1440, 1920] as const;
export const WORKSHOP_ACCEPTANCE_STATES = [
  "loading", "empty", "forbidden", "stale", "partial", "failed", "unknown",
  "blocked", "not-installed", "ready",
] as const;

export const WORKSHOP_ACCEPTANCE_KEYBOARD_PATHS = [
  "skip-link-to-main",
  "installed-navigation-current",
  "focus-mode-enter-return",
  "retry-focus",
  "tab-arrow-home-end",
  "dialog-drawer-escape-return",
] as const;

export type WorkshopAcceptanceModuleId = typeof WORKSHOP_ACCEPTANCE_MODULES[number]["moduleId"];
export type WorkshopAcceptanceViewport = typeof WORKSHOP_ACCEPTANCE_VIEWPORTS[number];
export type WorkshopAcceptanceState = typeof WORKSHOP_ACCEPTANCE_STATES[number];
export type WorkshopAcceptanceDisposition = "passed" | "blocked" | "not_applicable";
export type WorkshopAcceptanceEvidenceSource = "production-http" | "local-fixture" | "contract";

type ExactEvidenceRef = { revision: number; contentHash: string };

export type WorkshopAcceptanceEvidence = {
  moduleId: WorkshopAcceptanceModuleId;
  route: string;
  viewport: WorkshopAcceptanceViewport;
  state: WorkshopAcceptanceState;
  disposition: WorkshopAcceptanceDisposition;
  source: WorkshopAcceptanceEvidenceSource;
  tenant: { orgId: string; projectId: string };
  productionBuildSha: string | null;
  moduleRef: ExactEvidenceRef | null;
  installationRef: ExactEvidenceRef | null;
  domEvidenceRef: string | null;
  keyboardEvidenceRef: string | null;
  networkEvidenceRef: string | null;
  consoleEvidenceRef: string | null;
  screenshotRef: string | null;
  reason: string | null;
  contractRef: string | null;
};

export type WorkshopAcceptanceCell = WorkshopAcceptanceEvidence & { key: string };

const SHA256 = /^sha256:[0-9a-f]{64}$/;
const COMMIT_SHA = /^[0-9a-f]{40}$/;

function cellKey(moduleId: WorkshopAcceptanceModuleId, viewport: WorkshopAcceptanceViewport, state: WorkshopAcceptanceState) {
  return `${moduleId}:${viewport}:${state}`;
}

function block(evidence: WorkshopAcceptanceEvidence, reason: string): WorkshopAcceptanceEvidence {
  return { ...evidence, disposition: "blocked", reason };
}

export function evaluateWorkshopAcceptanceEvidence(
  evidence: WorkshopAcceptanceEvidence,
): WorkshopAcceptanceEvidence {
  const module = WORKSHOP_ACCEPTANCE_MODULES.find((item) => item.moduleId === evidence.moduleId);
  if (!module || module.route !== evidence.route) return block(evidence, "MODULE_ROUTE_EXACT_BINDING_REQUIRED");
  if (evidence.tenant.orgId !== "org-org" || evidence.tenant.projectId !== "dev-project") {
    return block(evidence, "POSITIVE_TENANT_SCOPE_REQUIRED");
  }
  if (evidence.disposition === "not_applicable") {
    if (!evidence.reason?.trim() || !evidence.contractRef?.trim()) {
      return block(evidence, "NOT_APPLICABLE_REASON_AND_CONTRACT_REQUIRED");
    }
    return evidence;
  }
  if (evidence.disposition === "blocked") {
    return { ...evidence, reason: evidence.reason?.trim() || "EVIDENCE_NOT_RECORDED" };
  }
  if (evidence.state === "ready" && evidence.source !== "production-http") {
    return block(evidence, "READY_REQUIRES_PRODUCTION_HTTP");
  }
  if (!evidence.productionBuildSha || !COMMIT_SHA.test(evidence.productionBuildSha)) {
    return block(evidence, "PRODUCTION_BUILD_SHA_REQUIRED");
  }
  if (!evidence.moduleRef || evidence.moduleRef.revision < 1 || !SHA256.test(evidence.moduleRef.contentHash)) {
    return block(evidence, "MODULE_EXACT_REF_REQUIRED");
  }
  if (!evidence.installationRef || evidence.installationRef.revision < 1 || !SHA256.test(evidence.installationRef.contentHash)) {
    return block(evidence, "ACTIVE_INSTALLATION_EXACT_REF_REQUIRED");
  }
  if (!evidence.domEvidenceRef || !evidence.keyboardEvidenceRef || !evidence.networkEvidenceRef
      || !evidence.consoleEvidenceRef || !evidence.screenshotRef || !evidence.contractRef) {
    return block(evidence, "COMPLETE_EVIDENCE_PACK_REQUIRED");
  }
  return { ...evidence, reason: null };
}

export function buildWorkshopAcceptanceMatrix(
  evidence: readonly WorkshopAcceptanceEvidence[],
): {
  cells: WorkshopAcceptanceCell[];
  summary: { passed: number; blocked: number; notApplicable: number };
} {
  const evidenceByKey = new Map<string, WorkshopAcceptanceEvidence>();
  for (const item of evidence) {
    const key = cellKey(item.moduleId, item.viewport, item.state);
    if (evidenceByKey.has(key)) throw new TypeError(`duplicate Workshop acceptance evidence: ${key}`);
    evidenceByKey.set(key, item);
  }
  const cells = WORKSHOP_ACCEPTANCE_MODULES.flatMap((module) =>
    WORKSHOP_ACCEPTANCE_VIEWPORTS.flatMap((viewport) =>
      WORKSHOP_ACCEPTANCE_STATES.map((state): WorkshopAcceptanceCell => {
        const key = cellKey(module.moduleId, viewport, state);
        const candidate = evidenceByKey.get(key) ?? {
          moduleId: module.moduleId,
          route: module.route,
          viewport,
          state,
          disposition: "blocked" as const,
          source: "contract" as const,
          tenant: { orgId: "org-org", projectId: "dev-project" },
          productionBuildSha: null,
          moduleRef: null,
          installationRef: null,
          domEvidenceRef: null,
          keyboardEvidenceRef: null,
          networkEvidenceRef: null,
          consoleEvidenceRef: null,
          screenshotRef: null,
          reason: "EVIDENCE_NOT_RECORDED",
          contractRef: "ADR-76#unique-matrix",
        };
        return { ...evaluateWorkshopAcceptanceEvidence(candidate), key };
      }),
    ),
  );
  return {
    cells,
    summary: {
      passed: cells.filter((item) => item.disposition === "passed").length,
      blocked: cells.filter((item) => item.disposition === "blocked").length,
      notApplicable: cells.filter((item) => item.disposition === "not_applicable").length,
    },
  };
}
