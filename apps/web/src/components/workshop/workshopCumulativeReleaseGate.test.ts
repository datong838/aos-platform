import { describe, expect, it } from "vitest";
import { CUMULATIVE_GATE_COLUMNS, RELEASE_MODULES, evaluateWorkshopCumulativeReleaseGate, type CumulativeReleaseEvidence, type ExactReleaseRef } from "./workshopCumulativeReleaseGate";

const hash = "a".repeat(64);
const commit = "b".repeat(40);
const cutoff = "2026-08-26T08:00:00+08:00";
const ref = (resourceType = "EvidencePack", resourceId = "evidence"): ExactReleaseRef => ({ resourceType, resourceId, revision: 1, contentHash: hash });
const complete = (): CumulativeReleaseEvidence => ({
  releaseRef: ref("ReleaseCandidateRevision", "release-1"), bundleRef: ref("BundleRevision", "bundle-1"), installationRef: ref("InstallationRevision", "installation-1"),
  authorityRevision: "AOS-000280", gitCommit: commit, gitClean: true, cutoffAt: cutoff,
  buildHash: hash, openApiHash: hash, sdkHash: hash, alembicHead: "head-20260826", schemaHash: hash, bundleHash: hash, lockHash: hash,
  moduleRefs: RELEASE_MODULES.map((moduleId) => ({ moduleId, ref: ref("ModuleRevision", moduleId) })),
  gates: CUMULATIVE_GATE_COLUMNS.map((column) => ({ column, required: true, status: "passed", command: `verify:${column}`, exitCode: 0, scope: [column], artifactRef: ref("ArtifactRevision", column), evidenceRef: ref("EvidencePack", column), gitCommit: commit, releaseRevision: "AOS-000280", cutoffAt: cutoff, dispositions: [], drifted: false, rerunAfterDrift: false })),
  tenantEvidence: { positiveTenant: "org-org/dev-project", negativeTenant: "dev-org/dev-project", positivePassed: true, negativePassed: true, positiveRef: ref("EvidencePack", "positive"), negativeRef: ref("EvidencePack", "negative"), cutoffAt: cutoff },
  blockerCounts: { p0: 0, p1: 0, critical: 0, high: 0, releaseUnknown: 0 },
  receiptReadback: { receiptRef: ref("DeliveryReceipt", "receipt-1"), gitCommit: commit, releaseRevision: "AOS-000280", cutoffAt: cutoff, exact: true },
});

describe("evaluateWorkshopCumulativeReleaseGate", () => {
  it("fails closed without evidence and keeps every command disabled", () => {
    const result = evaluateWorkshopCumulativeReleaseGate({});
    expect(result.status).toBe("blocked"); expect(result.gatesPassed).toBe(0); expect(result.modulesVerified).toBe(0);
    expect(Object.values(result.commands).every((allowed) => allowed === false)).toBe(true);
  });
  it("accepts one exact same-release fourteen-column evidence contract", () => {
    const result = evaluateWorkshopCumulativeReleaseGate(complete());
    expect(result).toMatchObject({ status: "ready", gatesPassed: 14, modulesVerified: 8, identityState: "exact", tenantState: "isolated", receiptState: "exact", blockerCodes: [] });
  });
  it("rejects dirty tree and cross-commit aggregation", () => {
    const evidence = complete(); evidence.gitClean = false; evidence.gates![0].gitCommit = "c".repeat(40);
    const result = evaluateWorkshopCumulativeReleaseGate(evidence);
    expect(result.blockerCodes).toContain("CUMULATIVE_RELEASE_IDENTITY_REQUIRED"); expect(result.blockerCodes).toContain("CUMULATIVE_GATE_CONTRACT_SCHEMA_IDENTITY_DRIFT");
  });
  it("requires all fourteen unique columns", () => {
    const evidence = complete(); evidence.gates = evidence.gates!.slice(1); evidence.gates.push({ ...evidence.gates[0], column: "unit_parser" });
    const result = evaluateWorkshopCumulativeReleaseGate(evidence);
    expect(result.blockerCodes).toContain("CUMULATIVE_GATE_CONTRACT_SCHEMA_REQUIRED"); expect(result.blockerCodes).toContain("CUMULATIVE_GATE_UNIT_PARSER_REQUIRED");
  });
  it("does not treat failed-close as positive evidence", () => {
    const evidence = complete(); evidence.gates![4].status = "failed_close";
    expect(evaluateWorkshopCumulativeReleaseGate(evidence).blockerCodes).toContain("CUMULATIVE_GATE_OPENAPI_POSITIVE_REQUIRED");
  });
  it("requires complete exception dispositions", () => {
    const evidence = complete(); evidence.gates![9].dispositions = [{ signal: "warning", reason: "known warning", owner: "", decisionRef: null }];
    expect(evaluateWorkshopCumulativeReleaseGate(evidence).blockerCodes).toContain("CUMULATIVE_GATE_SECURITY_SUPPLY_CHAIN_DISPOSITION_INCOMPLETE");
  });
  it("invalidates a drifted column until rerun", () => {
    const evidence = complete(); evidence.gates![6].drifted = true;
    expect(evaluateWorkshopCumulativeReleaseGate(evidence).blockerCodes).toContain("CUMULATIVE_GATE_BUNDLE_RESOLVER_INSTALLATION_EVAL_RERUN_REQUIRED");
  });
  it("requires positive and negative tenant evidence at the exact cutoff", () => {
    const evidence = complete(); evidence.tenantEvidence!.negativeTenant = "org-org/dev-project"; evidence.tenantEvidence!.cutoffAt = "2026-08-25T08:00:00+08:00";
    expect(evaluateWorkshopCumulativeReleaseGate(evidence).blockerCodes).toContain("CUMULATIVE_TENANT_POSITIVE_NEGATIVE_REQUIRED");
  });
  it("blocks P0/P1/security and release unknown counts", () => {
    const evidence = complete(); evidence.blockerCounts = { p0: 1, p1: 0, critical: 0, high: 1, releaseUnknown: 2 };
    expect(evaluateWorkshopCumulativeReleaseGate(evidence).blockerCodes).toContain("CUMULATIVE_RELEASE_BLOCKERS_OPEN");
  });
  it("requires exact Delivery Receipt readback", () => {
    const evidence = complete(); evidence.receiptReadback!.releaseRevision = "AOS-000279"; evidence.receiptReadback!.exact = false;
    expect(evaluateWorkshopCumulativeReleaseGate(evidence).blockerCodes).toContain("CUMULATIVE_RECEIPT_EXACT_READBACK_REQUIRED");
  });
});
