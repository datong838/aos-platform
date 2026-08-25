import { describe, expect, it } from "vitest";

import { parseMediaStudioView } from "./parser";
import { payload as publishPayload } from "./mediaStudioPublishParser.test";

const gateIds = ["contract_green", "service_green", "database_restart_green", "tenant_rls_green", "browser_positive_green", "browser_negative_green", "security_green", "fault_injection_green", "provider_adapter_green", "publish_canary_green", "operational_ready"] as const;

function payload() {
  const base = publishPayload() as Record<string, any>;
  base.schemaVersion = "aos.ecommerce-workshop.media-studio-view/v6";
  base.cumulativeGateSet = {
    schemaVersion: "aos.ecommerce-workshop.media-cumulative-gates/v1",
    releaseRevision: "AOS-000267",
    evaluatedAt: "2026-08-26T02:30:00Z",
    gates: gateIds.map((gateId, index) => index < 8 ? {
      gateId, status: "ready", evidenceRef: { resourceType: "EvidencePack", resourceId: "workshop-w7-11", revision: "AOS-000267", contentHash: "d".repeat(64) }, reasonCode: "MEDIA_ENGINEERING_EVIDENCE_CURRENT", observedAt: "2026-08-26T02:30:00Z", externalEffectsObserved: false,
    } : {
      gateId, status: "blocked", evidenceRef: null, reasonCode: ["MEDIA_PRODUCTION_PROVIDER_ADAPTER_RECEIPT_REQUIRED", "MEDIA_PUBLISH_CANARY_RECEIPT_REQUIRED", "MEDIA_OPERATIONAL_READY_RECEIPT_REQUIRED"][index - 8], observedAt: null, externalEffectsObserved: false,
    }),
    overallStatus: "blocked",
    blockerCodes: ["MEDIA_OPERATIONAL_READY_RECEIPT_REQUIRED", "MEDIA_PRODUCTION_PROVIDER_ADAPTER_RECEIPT_REQUIRED", "MEDIA_PUBLISH_CANARY_RECEIPT_REQUIRED"],
    externalEffectsAllowed: false,
    releaseAllowed: false,
  };
  return base;
}

describe("Media Studio v6 cumulative gate parser", () => {
  it("保留十一栏并诚实阻断外部运营门", () => {
    const result = parseMediaStudioView(payload(), { orgId: "org-org", projectId: "dev-project" });
    expect(result.cumulativeGateSet?.gates).toHaveLength(11);
    expect(result.cumulativeGateSet?.gates.filter((item) => item.status === "ready")).toHaveLength(8);
    expect(result.cumulativeGateSet?.overallStatus).toBe("blocked");
    expect(result.cumulativeGateSet?.externalEffectsAllowed).toBe(false);
    expect(result.cumulativeGateSet?.releaseAllowed).toBe(false);
  });

  it("拒绝把真实租户证据投影给隔离 canary 租户", () => {
    expect(() => parseMediaStudioView(payload(), { orgId: "dev-org", projectId: "dev-project" })).toThrow(/tenant|租户/);
  });

  it("拒绝跨 revision evidence、缺栏和伪运营 GREEN", () => {
    const drifted = payload();
    drifted.cumulativeGateSet.gates[0].evidenceRef.revision = "AOS-000265";
    expect(() => parseMediaStudioView(drifted)).toThrow(/revision/);
    const missing = payload();
    missing.cumulativeGateSet.gates.pop();
    expect(() => parseMediaStudioView(missing)).toThrow(/cumulative contract/);
    const forged = payload();
    forged.cumulativeGateSet.gates[10] = { ...forged.cumulativeGateSet.gates[0], gateId: "operational_ready" };
    forged.cumulativeGateSet.blockerCodes = forged.cumulativeGateSet.blockerCodes.filter((item: string) => item !== "MEDIA_OPERATIONAL_READY_RECEIPT_REQUIRED");
    expect(() => parseMediaStudioView(forged)).toThrow(/external gate/);
  });
});
