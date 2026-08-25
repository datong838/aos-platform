import { describe, expect, it } from "vitest";
import { DR_AUTHORITY_DOMAINS, DR_DRILLS, DR_EXTERNAL_AXES, DR_RLS_CHECKS, evaluateWorkshopDisasterRecovery, type DrEvidence, type ExactDrRef } from "./workshopDisasterRecoveryReadiness";

const at = "2026-08-26T00:00:00Z";
const ref = (resourceType: string, resourceId: string): ExactDrRef => ({ resourceType, resourceId, revision: 1, contentHash: "a".repeat(64) });
const order = ["identity", "tenant", "policy", "key", "registry", "immutable_authority", "integrity", "rls", "projection", "external_reconcile", "read_only_acceptance", "phased_mutation"];
function complete(): DrEvidence {
  return {
    releaseRef: ref("ReleaseRevision", "release-1"), bundleRef: ref("BundleRevision", "bundle-1"), installationRef: ref("InstallationRevision", "install-1"), drPlanRef: ref("DisasterRecoveryPlanRevision", "dr-1"), evaluatedAt: at,
    authorityInventory: DR_AUTHORITY_DOMAINS.map((domain) => ({ domain, count: 1, inventoryRef: ref("AuthorityInventoryRevision", domain), cutoffAt: at })),
    backup: { manifestRef: ref("BackupManifestRevision", "backup-1"), logPosition: "lsn:1", schemaHash: "b".repeat(64), appHash: "c".repeat(64), bundleHash: "d".repeat(64), keyRevisionRef: ref("EncryptionKeyRevision", "key-1"), retentionPolicyRef: ref("RetentionPolicyRevision", "retention-1"), objectManifestRef: ref("ObjectManifestRevision", "objects-1"), dependencyOrder: order, verifiedAt: at },
    objectives: { approvedRpoSeconds: 300, approvedRtoSeconds: 900, measuredRpoSeconds: 120, measuredRtoSeconds: 600, approvalRef: ref("RecoveryObjectiveApproval", "approval-1"), measurementRef: ref("RecoveryMeasurement", "measure-1") },
    recovery: { isolatedTargetRef: ref("IsolatedRecoveryTarget", "target-1"), maker: "user:maker", checker: "user:checker", executor: "service:executor", recoveryDecisionRef: ref("RecoveryDecisionReceipt", "decision-1"), stageReceiptRefs: order.map((stage) => ref("RecoveryStageReceipt", stage)), failbackReceiptRef: ref("FailbackReceipt", "failback-1") },
    rls: DR_RLS_CHECKS.map((check) => ({ check, passed: true, evidenceRef: ref("RlsEvidencePack", check), cutoffAt: at })),
    projection: { checkpointRef: ref("ProjectionCheckpoint", "checkpoint-1"), evidenceRef: ref("ProjectionEvidencePack", "projection-1"), authorityRevisionBefore: "AOS-000279", authorityRevisionAfter: "AOS-000279", missing: 0, extra: 0, revisionMismatch: 0, conflict: 0, unknown: 0, resumed: true },
    externalReconcile: DR_EXTERNAL_AXES.map((axis) => ({ axis, status: "closed", receiptRef: ref("ExternalReconcileReceipt", axis) })),
    drills: DR_DRILLS.map((drill) => ({ drill, status: "passed", evidencePackRef: ref("DrillEvidencePack", drill) })),
  };
}

describe("evaluateWorkshopDisasterRecovery", () => {
  it("fails closed without evidence and never exposes data-operation commands", () => {
    const result = evaluateWorkshopDisasterRecovery({});
    expect(result.status).toBe("blocked"); expect(result.backupState).toBe("unknown"); expect(result.objectivesState).toBe("unknown");
    expect(result.blockerCodes).toContain("DR_RELEASE_ROOTS_REQUIRED"); expect(Object.values(result.commands).every((value) => value === false)).toBe(true);
  });
  it("requires backup hashes and the exact restore dependency order", () => {
    const evidence = complete(); evidence.backup!.schemaHash = null; evidence.backup!.dependencyOrder = [...order].reverse();
    const result = evaluateWorkshopDisasterRecovery(evidence); expect(result.blockerCodes).toContain("DR_BACKUP_MANIFEST_INCOMPLETE"); expect(result.backupState).toBe("unknown");
  });
  it("keeps RLS prerequisite checks independent and same-cutoff", () => {
    const evidence = complete(); evidence.rls![1] = { ...evidence.rls![1], passed: false };
    const result = evaluateWorkshopDisasterRecovery(evidence); expect(result.rlsChecksPassed).toBe(3); expect(result.blockerCodes).toContain("DR_RLS_WRONG_SCOPE_DENIED_REQUIRED");
  });
  it("rejects a disposable projection rebuild that mutates authority revision", () => {
    const evidence = complete(); evidence.projection!.authorityRevisionAfter = "AOS-000280";
    expect(evaluateWorkshopDisasterRecovery(evidence).blockerCodes).toContain("DR_PROJECTION_MUTATED_AUTHORITY");
  });
  it("keeps provider, Usage and in-flight Lease reconciliation independent", () => {
    const evidence = complete(); evidence.externalReconcile![2] = { axis: "usage_settlement", status: "unknown", receiptRef: null };
    const result = evaluateWorkshopDisasterRecovery(evidence); expect(result.externalAxesClosed).toBe(4); expect(result.blockerCodes).toContain("DR_EXTERNAL_USAGE_SETTLEMENT_OPEN");
  });
  it("requires approved measured objectives and separated recovery roles", () => {
    const evidence = complete(); evidence.objectives!.measuredRtoSeconds = 1200; evidence.recovery!.checker = evidence.recovery!.maker;
    const result = evaluateWorkshopDisasterRecovery(evidence); expect(result.objectivesState).toBe("missed"); expect(result.blockerCodes).toContain("DR_RPO_RTO_MISSED"); expect(result.blockerCodes).toContain("DR_ISOLATION_ROLE_RECEIPT_CHAIN_REQUIRED");
  });
  it("requires every drill EvidencePack", () => {
    const evidence = complete(); evidence.drills = evidence.drills!.slice(0, -1);
    const result = evaluateWorkshopDisasterRecovery(evidence); expect(result.drillsPassed).toBe(9); expect(result.blockerCodes).toContain("DR_DRILL_FAILBACK_REQUIRED");
  });
  it("returns ready only for the complete same-release evidence contract", () => {
    const result = evaluateWorkshopDisasterRecovery(complete()); expect(result.status).toBe("ready"); expect(result.blockerCodes).toEqual([]); expect(result.authorityDomainsVerified).toBe(8); expect(result.rlsChecksPassed).toBe(4); expect(result.externalAxesClosed).toBe(5); expect(result.drillsPassed).toBe(10);
  });
});
