export const WORKSHOP_LIFECYCLE_OPERATIONS = [
  "install",
  "upgrade",
  "rollback",
  "uninstall",
] as const;

export type WorkshopLifecycleOperation = typeof WORKSHOP_LIFECYCLE_OPERATIONS[number];
export type WorkshopLifecycleSource = "production-http" | "local-fixture" | "contract";

export type WorkshopInstallationRef = {
  installationId: string;
  revision: number;
  lockHash: string;
  overlayRevision: string;
};

export type WorkshopLifecycleSnapshot = WorkshopInstallationRef & {
  state: "active" | "rolled_back" | "uninstalled";
  predecessor: WorkshopInstallationRef | null;
};

export type WorkshopLifecycleEvidence = {
  operation: WorkshopLifecycleOperation;
  source: WorkshopLifecycleSource;
  tenant: { orgId: string; projectId: string };
  before: WorkshopLifecycleSnapshot | null;
  after: WorkshopLifecycleSnapshot;
  effectiveLeafBefore: WorkshopInstallationRef | null;
  effectiveLeafAfter: WorkshopInstallationRef | null;
  historyBefore: { installations: number; revisions: number; events: number };
  historyAfter: { installations: number; revisions: number; events: number };
  commandReceiptRef: string | null;
  catalogEvidenceRef: string | null;
  historyEvidenceRef: string | null;
};

export type WorkshopLifecycleDecision = {
  outcome: "passed" | "blocked";
  reason: string | null;
};

export type WorkshopRouteRetirementEvidence = {
  source: WorkshopLifecycleSource;
  tenant: { orgId: string; projectId: string };
  legacyRoute: string;
  canonicalRoute: string;
  moduleRef: WorkshopInstallationRef;
  installationRef: WorkshopInstallationRef;
  capabilityPermissionParity: boolean;
  canonicalBrowserGreen: boolean;
  zeroNewAuthoring: boolean;
  observationWindowApproved: boolean;
  savedLinksAndIntegrationsMigrated: boolean;
  rollbackDrillGreen: boolean;
  releaseOwnerReceiptRef: string | null;
};

export type WorkshopRouteRetirementDecision = {
  legacyRoute: string;
  canonicalRoute: string;
  disposition: "retired" | "preserve";
  reason: string | null;
  decisionRef: string | null;
};

const SHA256 = /^sha256:[0-9a-f]{64}$/;
const INSTALLATION_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function sameRef(left: WorkshopInstallationRef | null, right: WorkshopInstallationRef | null): boolean {
  if (left === null || right === null) return left === right;
  return left.installationId === right.installationId
    && left.revision === right.revision
    && left.lockHash === right.lockHash
    && left.overlayRevision === right.overlayRevision;
}

function exactRef(value: WorkshopInstallationRef | null): boolean {
  return value !== null
    && INSTALLATION_ID.test(value.installationId)
    && Number.isInteger(value.revision)
    && value.revision > 0
    && SHA256.test(value.lockHash)
    && SHA256.test(value.overlayRevision);
}

function blocked(reason: string): WorkshopLifecycleDecision {
  return { outcome: "blocked", reason };
}

export function evaluateWorkshopLifecycleEvidence(
  evidence: WorkshopLifecycleEvidence,
): WorkshopLifecycleDecision {
  if (evidence.tenant.orgId !== "org-org" || evidence.tenant.projectId !== "dev-project") {
    return blocked("POSITIVE_TENANT_SCOPE_REQUIRED");
  }
  if (evidence.source !== "production-http") return blocked("PRODUCTION_HTTP_EVIDENCE_REQUIRED");
  if (!exactRef(evidence.after) || (evidence.before !== null && !exactRef(evidence.before))) {
    return blocked("EXACT_INSTALLATION_REFS_REQUIRED");
  }
  if (!evidence.commandReceiptRef || !evidence.catalogEvidenceRef || !evidence.historyEvidenceRef) {
    return blocked("COMPLETE_LIFECYCLE_EVIDENCE_PACK_REQUIRED");
  }
  if (
    evidence.historyAfter.installations < evidence.historyBefore.installations
    || evidence.historyAfter.revisions <= evidence.historyBefore.revisions
    || evidence.historyAfter.events <= evidence.historyBefore.events
  ) {
    return blocked("APPEND_ONLY_HISTORY_REQUIRED");
  }

  if (evidence.operation === "install") {
    if (evidence.before !== null || evidence.after.state !== "active" || evidence.after.predecessor !== null
        || !sameRef(evidence.effectiveLeafAfter, evidence.after)
        || evidence.historyAfter.installations !== evidence.historyBefore.installations + 1) {
      return blocked("INSTALL_NEW_ACTIVE_ROOT_REQUIRED");
    }
  } else if (evidence.operation === "upgrade") {
    if (evidence.before?.state !== "active" || evidence.after.state !== "active"
        || !sameRef(evidence.after.predecessor, evidence.before)
        || !sameRef(evidence.effectiveLeafBefore, evidence.before)
        || !sameRef(evidence.effectiveLeafAfter, evidence.after)
        || evidence.after.installationId === evidence.before.installationId
        || evidence.historyAfter.installations !== evidence.historyBefore.installations + 1) {
      return blocked("EXACT_REPLACEMENT_LEAF_REQUIRED");
    }
  } else if (evidence.operation === "rollback") {
    if (evidence.before?.state !== "active" || evidence.after.state !== "rolled_back"
        || evidence.before.installationId !== evidence.after.installationId
        || evidence.after.predecessor === null
        || !sameRef(evidence.effectiveLeafBefore, evidence.before)
        || !sameRef(evidence.effectiveLeafAfter, evidence.after.predecessor)
        || evidence.historyAfter.installations !== evidence.historyBefore.installations) {
      return blocked("LEAF_FIRST_PREDECESSOR_RESTORE_REQUIRED");
    }
  } else if (evidence.before?.state !== "active" || evidence.after.state !== "uninstalled"
      || evidence.before.installationId !== evidence.after.installationId
      || evidence.historyAfter.installations !== evidence.historyBefore.installations
      || (evidence.after.predecessor === null
        ? evidence.effectiveLeafAfter !== null
        : !sameRef(evidence.effectiveLeafAfter, evidence.after.predecessor))) {
    return blocked("TERMINAL_UNINSTALL_PROJECTION_REQUIRED");
  }
  return { outcome: "passed", reason: null };
}

export function evaluateWorkshopRouteRetirement(
  evidence: WorkshopRouteRetirementEvidence,
): WorkshopRouteRetirementDecision {
  const preserve = (reason: string): WorkshopRouteRetirementDecision => ({
    legacyRoute: evidence.legacyRoute,
    canonicalRoute: evidence.canonicalRoute,
    disposition: "preserve",
    reason,
    decisionRef: null,
  });
  if (evidence.tenant.orgId !== "org-org" || evidence.tenant.projectId !== "dev-project") {
    return preserve("POSITIVE_TENANT_SCOPE_REQUIRED");
  }
  if (evidence.source !== "production-http") return preserve("PRODUCTION_HTTP_EVIDENCE_REQUIRED");
  if (!evidence.legacyRoute.startsWith("/") || !evidence.canonicalRoute.startsWith("/")
      || evidence.legacyRoute === evidence.canonicalRoute) {
    return preserve("DISTINCT_CANONICAL_ROUTE_REQUIRED");
  }
  if (!exactRef(evidence.moduleRef) || !exactRef(evidence.installationRef)) {
    return preserve("EXACT_MODULE_AND_INSTALLATION_REFS_REQUIRED");
  }
  const gates = [
    evidence.capabilityPermissionParity,
    evidence.canonicalBrowserGreen,
    evidence.zeroNewAuthoring,
    evidence.observationWindowApproved,
    evidence.savedLinksAndIntegrationsMigrated,
    evidence.rollbackDrillGreen,
  ];
  if (gates.some((gate) => !gate) || !evidence.releaseOwnerReceiptRef?.trim()) {
    return preserve("RETIREMENT_SEVEN_GATES_REQUIRED");
  }
  return {
    legacyRoute: evidence.legacyRoute,
    canonicalRoute: evidence.canonicalRoute,
    disposition: "retired",
    reason: null,
    decisionRef: evidence.releaseOwnerReceiptRef,
  };
}
