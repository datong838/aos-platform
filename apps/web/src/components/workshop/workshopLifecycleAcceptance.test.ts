import { describe, expect, it } from "vitest";

import {
  evaluateWorkshopLifecycleEvidence,
  evaluateWorkshopRouteRetirement,
  type WorkshopInstallationRef,
  type WorkshopLifecycleEvidence,
  type WorkshopRouteRetirementEvidence,
} from "./workshopLifecycleAcceptance";

const hash = (value: string) => `sha256:${value.repeat(64)}`;
const root: WorkshopInstallationRef = {
  installationId: "11111111-1111-4111-8111-111111111111",
  revision: 5,
  lockHash: hash("a"),
  overlayRevision: hash("b"),
};
const child: WorkshopInstallationRef = {
  installationId: "22222222-2222-4222-8222-222222222222",
  revision: 5,
  lockHash: hash("c"),
  overlayRevision: hash("d"),
};

function lifecycle(overrides: Partial<WorkshopLifecycleEvidence> = {}): WorkshopLifecycleEvidence {
  return {
    operation: "upgrade",
    source: "production-http",
    tenant: { orgId: "org-org", projectId: "dev-project" },
    before: { ...root, state: "active", predecessor: null },
    after: { ...child, state: "active", predecessor: root },
    effectiveLeafBefore: root,
    effectiveLeafAfter: child,
    historyBefore: { installations: 1, revisions: 6, events: 6 },
    historyAfter: { installations: 2, revisions: 12, events: 12 },
    commandReceiptRef: "receipt://upgrade",
    catalogEvidenceRef: "evidence://catalog-after.json",
    historyEvidenceRef: "evidence://history-after.json",
    ...overrides,
  };
}

function retirement(overrides: Partial<WorkshopRouteRetirementEvidence> = {}): WorkshopRouteRetirementEvidence {
  return {
    source: "production-http",
    tenant: { orgId: "org-org", projectId: "dev-project" },
    legacyRoute: "/workshop/orders",
    canonicalRoute: "/workshop/operations",
    moduleRef: child,
    installationRef: child,
    capabilityPermissionParity: true,
    canonicalBrowserGreen: true,
    zeroNewAuthoring: true,
    observationWindowApproved: true,
    savedLinksAndIntegrationsMigrated: true,
    rollbackDrillGreen: true,
    releaseOwnerReceiptRef: "receipt://route-retirement/orders",
    ...overrides,
  };
}

describe("W8-08 lifecycle acceptance contract", () => {
  it("accepts a new active root without overwriting an existing installation", () => {
    const evidence = lifecycle({
      operation: "install",
      before: null,
      after: { ...root, state: "active", predecessor: null },
      effectiveLeafBefore: null,
      effectiveLeafAfter: root,
      historyBefore: { installations: 0, revisions: 0, events: 0 },
      historyAfter: { installations: 1, revisions: 6, events: 6 },
    });
    expect(evaluateWorkshopLifecycleEvidence(evidence)).toEqual({ outcome: "passed", reason: null });
  });

  it("accepts an exact replacement and rejects a forked/non-exact leaf", () => {
    expect(evaluateWorkshopLifecycleEvidence(lifecycle())).toEqual({ outcome: "passed", reason: null });
    expect(evaluateWorkshopLifecycleEvidence(lifecycle({ effectiveLeafAfter: root }))).toEqual({
      outcome: "blocked",
      reason: "EXACT_REPLACEMENT_LEAF_REQUIRED",
    });
  });

  it("requires leaf-first rollback to restore the exact predecessor", () => {
    const evidence = lifecycle({
      operation: "rollback",
      before: { ...child, state: "active", predecessor: root },
      after: { ...child, revision: 6, state: "rolled_back", predecessor: root },
      effectiveLeafBefore: child,
      effectiveLeafAfter: root,
      historyBefore: { installations: 2, revisions: 12, events: 12 },
      historyAfter: { installations: 2, revisions: 13, events: 13 },
    });
    expect(evaluateWorkshopLifecycleEvidence(evidence).outcome).toBe("passed");
    expect(evaluateWorkshopLifecycleEvidence({ ...evidence, effectiveLeafAfter: null }).reason)
      .toBe("LEAF_FIRST_PREDECESSOR_RESTORE_REQUIRED");
  });

  it("treats uninstall as terminal and preserves append-only history", () => {
    const evidence = lifecycle({
      operation: "uninstall",
      before: { ...root, state: "active", predecessor: null },
      after: { ...root, revision: 6, state: "uninstalled", predecessor: null },
      effectiveLeafBefore: root,
      effectiveLeafAfter: null,
      historyBefore: { installations: 1, revisions: 6, events: 6 },
      historyAfter: { installations: 1, revisions: 7, events: 7 },
    });
    expect(evaluateWorkshopLifecycleEvidence(evidence).outcome).toBe("passed");
    expect(evaluateWorkshopLifecycleEvidence({
      ...evidence,
      historyAfter: { installations: 1, revisions: 6, events: 7 },
    }).reason).toBe("APPEND_ONLY_HISTORY_REQUIRED");
  });

  it("does not let fixture, wrong-tenant or incomplete evidence become lifecycle proof", () => {
    expect(evaluateWorkshopLifecycleEvidence(lifecycle({ source: "local-fixture" })).reason)
      .toBe("PRODUCTION_HTTP_EVIDENCE_REQUIRED");
    expect(evaluateWorkshopLifecycleEvidence(lifecycle({ tenant: { orgId: "dev-org", projectId: "dev-project" } })).reason)
      .toBe("POSITIVE_TENANT_SCOPE_REQUIRED");
    expect(evaluateWorkshopLifecycleEvidence(lifecycle({ commandReceiptRef: null })).reason)
      .toBe("COMPLETE_LIFECYCLE_EVIDENCE_PACK_REQUIRED");
  });
});

describe("W8-08 explicit route retirement contract", () => {
  it("retires only after all seven gates and a release-owner Receipt", () => {
    expect(evaluateWorkshopRouteRetirement(retirement())).toEqual({
      legacyRoute: "/workshop/orders",
      canonicalRoute: "/workshop/operations",
      disposition: "retired",
      reason: null,
      decisionRef: "receipt://route-retirement/orders",
    });
  });

  it.each([
    ["capabilityPermissionParity", false],
    ["canonicalBrowserGreen", false],
    ["zeroNewAuthoring", false],
    ["observationWindowApproved", false],
    ["savedLinksAndIntegrationsMigrated", false],
    ["rollbackDrillGreen", false],
    ["releaseOwnerReceiptRef", null],
  ] as const)("preserves redirect when %s is missing", (key, value) => {
    const result = evaluateWorkshopRouteRetirement(retirement({ [key]: value }));
    expect(result.disposition).toBe("preserve");
    expect(result.reason).toBe("RETIREMENT_SEVEN_GATES_REQUIRED");
  });

  it("never treats local fixture evidence as a production retirement decision", () => {
    expect(evaluateWorkshopRouteRetirement(retirement({ source: "local-fixture" }))).toMatchObject({
      disposition: "preserve",
      reason: "PRODUCTION_HTTP_EVIDENCE_REQUIRED",
      decisionRef: null,
    });
  });
});
