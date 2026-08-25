import { describe, expect, it } from "vitest";

import {
  OPERATING_AXIS_IDS, OPERATING_SLI_IDS, REQUIRED_DRILL_IDS, USAGE_BUCKET_IDS,
  evaluateWorkshopOperatingReadiness, type ExactOperatingRef, type OperatingEvidence,
} from "./workshopOperatingReadiness";

const at = "2026-08-26T00:00:00Z";
const ref = (resourceType: string, resourceId: string): ExactOperatingRef => ({ resourceType, resourceId, revision: 1, contentHash: "a".repeat(64) });

function complete(): OperatingEvidence {
  return {
    releaseRef: ref("ReleaseRevision", "release-1"), bundleRef: ref("BundleRevision", "bundle-1"), installationRef: ref("InstallationRevision", "installation-1"), evaluatedAt: at,
    slis: OPERATING_SLI_IDS.map((id) => ({ id, sampleCount: 10, unknownCount: id === "unknown_ratio" ? 1 : 0, sourceRef: ref("MetricRevision", id), cutoffAt: at })),
    slos: OPERATING_SLI_IDS.map((sliId) => ({ sliId, owner: "ops", population: "all eligible", eligibility: "same release", eventClock: "provider observed_at", window: "rolling", target: 0.99, errorBudget: 0.01, sourceRevisionRef: ref("SloRevision", sliId), baselineEvidenceRef: ref("EvidencePack", `baseline-${sliId}`) })),
    unknownBacklog: [{ itemId: "unknown-1", firstUnknownAt: "2026-08-25T23:00:00Z", observedAt: at, requestFingerprint: "b".repeat(64), providerRef: ref("Provider", "provider-1"), accountRef: ref("Account", "account-1"), adapterRef: ref("AdapterRevision", "adapter-1"), policyRef: ref("PolicyRevision", "policy-1"), leaseRef: ref("LeaseReceipt", "lease-1"), riskExposure: "R2", lastCanonicalReconcileAt: null }],
    usage: { currency: "CNY", cutoffAt: at, buckets: Object.fromEntries(USAGE_BUCKET_IDS.map((id) => [id, id === "unknown" ? 1 : 0])), sourceRefs: [ref("UsageReceipt", "usage-1")], integrityAlerts: [] },
    axes: OPERATING_AXIS_IDS.map((axisId) => ({ axisId, status: "closed", receiptRef: ref("ClosureReceipt", axisId) })),
    alertPolicyRef: ref("AlertPolicyRevision", "alert-policy-1"), alertLedgerRef: ref("AlertLedgerRevision", "alert-ledger-1"),
    alertLifecycle: [{ kind: "resolution", receiptRef: ref("AlertResolutionReceipt", "resolution-1"), canonicalRereadRef: ref("MetricRevision", "metric-after-resolution") }],
    runbookRef: ref("RunbookRevision", "runbook-1"), drills: REQUIRED_DRILL_IDS.map((drillId) => ({ drillId, status: "passed", evidencePackRef: ref("DrillEvidencePack", drillId) })),
  };
}

describe("evaluateWorkshopOperatingReadiness", () => {
  it("fails closed without authority and never invents zero backlog or usage", () => {
    const result = evaluateWorkshopOperatingReadiness({});
    expect(result.status).toBe("blocked");
    expect(result.unknownBacklogCount).toBeNull();
    expect(result.oldestUnknownAgeMs).toBeNull();
    expect(result.usageState).toBe("unknown");
    expect(result.blockerCodes).toContain("OPERATING_RELEASE_ROOTS_REQUIRED");
    expect(result.blockerCodes).toContain("UNKNOWN_BACKLOG_AUTHORITY_REQUIRED");
    expect(Object.values(result.commands).every((value) => value === false)).toBe(true);
  });

  it("requires measured baselines and approved targets instead of invented SLO numbers", () => {
    const evidence = complete();
    evidence.slos![0] = { ...evidence.slos![0], target: null, baselineEvidenceRef: null };
    expect(evaluateWorkshopOperatingReadiness(evidence).blockerCodes).toContain("SLO_VIEW_AVAILABILITY_TBD");
  });

  it("keeps age anchored to the first ambiguity boundary", () => {
    const evidence = complete();
    evidence.unknownBacklog![0].restartedAt = "2026-08-25T22:00:00Z";
    const result = evaluateWorkshopOperatingReadiness(evidence);
    expect(result.blockerCodes).toContain("UNKNOWN_AGE_RESET_DETECTED");
    expect(result.oldestUnknownAgeMs).toBe(60 * 60 * 1000);
  });

  it("keeps Usage integrity and five closure axes independent", () => {
    const evidence = complete();
    evidence.usage!.integrityAlerts = ["currency_drift"];
    evidence.axes![3] = { axisId: "effect", status: "unknown", receiptRef: null };
    const result = evaluateWorkshopOperatingReadiness(evidence);
    expect(result.blockerCodes).toContain("USAGE_INTEGRITY_ALERT_OPEN");
    expect(result.blockerCodes).toContain("AXIS_EFFECT_OPEN");
    expect(result.closedAxes).toBe(4);
  });

  it("does not treat Ack or a Resolution without canonical reread as recovery", () => {
    const evidence = complete();
    evidence.alertLifecycle = [{ kind: "ack", receiptRef: ref("AlertAckReceipt", "ack-1") }, { kind: "resolution", receiptRef: ref("AlertResolutionReceipt", "resolution-1"), canonicalRereadRef: null }];
    expect(evaluateWorkshopOperatingReadiness(evidence).blockerCodes).toContain("ALERT_RESOLUTION_REREAD_REQUIRED");
  });

  it("requires every drill EvidencePack before operational ready", () => {
    const evidence = complete();
    evidence.drills = evidence.drills!.slice(0, -1);
    const result = evaluateWorkshopOperatingReadiness(evidence);
    expect(result.status).toBe("blocked");
    expect(result.runbookState).toBe("defined");
    expect(result.blockerCodes).toContain("DRILL_MONITORING_SILENCE_REQUIRED");
  });

  it("returns ready only for a same-release complete evidence set", () => {
    const result = evaluateWorkshopOperatingReadiness(complete());
    expect(result.status).toBe("ready");
    expect(result.blockerCodes).toEqual([]);
    expect(result.unknownBacklogCount).toBe(1);
    expect(result.closedAxes).toBe(5);
    expect(result.usageState).toBe("measured");
    expect(result.runbookState).toBe("drilled");
  });
});
