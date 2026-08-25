import { describe, expect, it } from "vitest";

import {
  WORKSHOP_ACCEPTANCE_MODULES,
  WORKSHOP_ACCEPTANCE_STATES,
  WORKSHOP_ACCEPTANCE_VIEWPORTS,
  buildWorkshopAcceptanceMatrix,
  evaluateWorkshopAcceptanceEvidence,
} from "./workshopAcceptance";

const hash = `sha256:${"a".repeat(64)}`;

describe("W8-07 workshop acceptance contract", () => {
  it("freezes eight exact modules, three viewports and ten state boundaries", () => {
    expect(WORKSHOP_ACCEPTANCE_MODULES).toHaveLength(8);
    expect(new Set(WORKSHOP_ACCEPTANCE_MODULES.map((item) => item.moduleId)).size).toBe(8);
    expect(new Set(WORKSHOP_ACCEPTANCE_MODULES.map((item) => item.route)).size).toBe(8);
    expect(WORKSHOP_ACCEPTANCE_VIEWPORTS).toEqual([1280, 1440, 1920]);
    expect(WORKSHOP_ACCEPTANCE_STATES).toEqual([
      "loading", "empty", "forbidden", "stale", "partial", "failed", "unknown",
      "blocked", "not-installed", "ready",
    ]);
    const matrix = buildWorkshopAcceptanceMatrix([]);
    expect(matrix.cells).toHaveLength(240);
    expect(matrix.summary).toEqual({ passed: 0, blocked: 240, notApplicable: 0 });
  });

  it("does not let local fixture evidence turn a ready cell green", () => {
    const module = WORKSHOP_ACCEPTANCE_MODULES[0]!;
    const result = evaluateWorkshopAcceptanceEvidence({
      moduleId: module.moduleId,
      route: module.route,
      viewport: 1280,
      state: "ready",
      disposition: "passed",
      source: "local-fixture",
      tenant: { orgId: "org-org", projectId: "dev-project" },
      productionBuildSha: "b".repeat(40),
      moduleRef: { revision: 1, contentHash: hash },
      installationRef: { revision: 1, contentHash: hash },
      domEvidenceRef: "dom.json",
      keyboardEvidenceRef: "keyboard.json",
      networkEvidenceRef: "network.json",
      consoleEvidenceRef: "console.json",
      screenshotRef: "ready.png",
      reason: null,
      contractRef: "ADR-76#ready",
    });
    expect(result.disposition).toBe("blocked");
    expect(result.reason).toBe("READY_REQUIRES_PRODUCTION_HTTP");
  });

  it("requires a stable reason and contract ref for not_applicable", () => {
    const module = WORKSHOP_ACCEPTANCE_MODULES[4]!;
    const result = evaluateWorkshopAcceptanceEvidence({
      moduleId: module.moduleId,
      route: module.route,
      viewport: 1920,
      state: "blocked",
      disposition: "not_applicable",
      source: "contract",
      tenant: { orgId: "org-org", projectId: "dev-project" },
      productionBuildSha: null,
      moduleRef: null,
      installationRef: null,
      domEvidenceRef: null,
      keyboardEvidenceRef: null,
      networkEvidenceRef: null,
      consoleEvidenceRef: null,
      screenshotRef: null,
      reason: null,
      contractRef: null,
    });
    expect(result.disposition).toBe("blocked");
    expect(result.reason).toBe("NOT_APPLICABLE_REASON_AND_CONTRACT_REQUIRED");
  });

  it("accepts ready only with production HTTP, exact refs and the complete evidence pack", () => {
    const module = WORKSHOP_ACCEPTANCE_MODULES[7]!;
    const result = evaluateWorkshopAcceptanceEvidence({
      moduleId: module.moduleId,
      route: module.route,
      viewport: 1440,
      state: "ready",
      disposition: "passed",
      source: "production-http",
      tenant: { orgId: "org-org", projectId: "dev-project" },
      productionBuildSha: "c".repeat(40),
      moduleRef: { revision: 3, contentHash: hash },
      installationRef: { revision: 9, contentHash: hash },
      domEvidenceRef: "dom.json",
      keyboardEvidenceRef: "keyboard.json",
      networkEvidenceRef: "network.json",
      consoleEvidenceRef: "console.json",
      screenshotRef: "ready.png",
      reason: null,
      contractRef: "ADR-76#ready",
    });
    expect(result.disposition).toBe("passed");
    expect(result.reason).toBeNull();
  });
});
