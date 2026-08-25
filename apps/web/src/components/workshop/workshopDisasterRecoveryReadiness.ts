export const DR_AUTHORITY_DOMAINS = [
  "registry_installation", "domain_revision_event", "task_run_handoff", "evidence_artifact_eval",
  "action_receipt_usage_lineage", "memory_wiki_exploration", "adapter_account_policy", "alert_reconcile",
] as const;
export const DR_RLS_CHECKS = ["no_scope_denied", "wrong_scope_denied", "finally_reset", "positive_negative_tenant_isolated"] as const;
export const DR_EXTERNAL_AXES = ["provider_outcome", "webhook_gap", "usage_settlement", "budget_frequency", "in_flight_lease"] as const;
export const DR_DRILLS = [
  "pitr", "corrupt_latest_fallback", "object_missing_hash_drift", "projection_resume", "key_unavailable_rotation",
  "rls_guc_leak", "old_app_bundle_incompatible", "provider_late_duplicate", "regional_dependency_failure", "failback",
] as const;

export type ExactDrRef = { resourceType: string; resourceId: string; revision: number; contentHash: string };
export type DrEvidence = {
  releaseRef?: ExactDrRef | null;
  bundleRef?: ExactDrRef | null;
  installationRef?: ExactDrRef | null;
  drPlanRef?: ExactDrRef | null;
  evaluatedAt?: string | null;
  authorityInventory?: Array<{ domain: typeof DR_AUTHORITY_DOMAINS[number]; count: number | null; inventoryRef: ExactDrRef | null; cutoffAt: string | null }> | null;
  backup?: {
    manifestRef: ExactDrRef | null; logPosition: string | null; schemaHash: string | null; appHash: string | null; bundleHash: string | null;
    keyRevisionRef: ExactDrRef | null; retentionPolicyRef: ExactDrRef | null; objectManifestRef: ExactDrRef | null;
    dependencyOrder: string[]; verifiedAt: string | null;
  } | null;
  objectives?: { approvedRpoSeconds: number | null; approvedRtoSeconds: number | null; measuredRpoSeconds: number | null; measuredRtoSeconds: number | null; approvalRef: ExactDrRef | null; measurementRef: ExactDrRef | null } | null;
  recovery?: { isolatedTargetRef: ExactDrRef | null; maker: string | null; checker: string | null; executor: string | null; recoveryDecisionRef: ExactDrRef | null; stageReceiptRefs: ExactDrRef[]; failbackReceiptRef: ExactDrRef | null } | null;
  rls?: Array<{ check: typeof DR_RLS_CHECKS[number]; passed: boolean; evidenceRef: ExactDrRef | null; cutoffAt: string | null }> | null;
  projection?: { checkpointRef: ExactDrRef | null; evidenceRef: ExactDrRef | null; authorityRevisionBefore: string | null; authorityRevisionAfter: string | null; missing: number | null; extra: number | null; revisionMismatch: number | null; conflict: number | null; unknown: number | null; resumed: boolean } | null;
  externalReconcile?: Array<{ axis: typeof DR_EXTERNAL_AXES[number]; status: "closed" | "open" | "unknown"; receiptRef: ExactDrRef | null }> | null;
  drills?: Array<{ drill: typeof DR_DRILLS[number]; status: "passed" | "failed" | "unknown"; evidencePackRef: ExactDrRef | null }> | null;
};

export type DrReadinessResult = {
  status: "ready" | "blocked";
  blockerCodes: string[];
  authorityDomainsVerified: number;
  backupState: "verified" | "unknown";
  rlsChecksPassed: number;
  projectionState: "rebuild_verified" | "unknown";
  externalAxesClosed: number;
  objectivesState: "measured_within_approved" | "unknown" | "missed";
  drillsPassed: number;
  commands: { inspectBackup: false; restore: false; rebuildProjection: false; changeRls: false; reconcileExternal: false; failover: false; failback: false };
};

const HASH = /^(?:sha256:)?[0-9a-f]{64}$/;
const REVISION = /^AOS-\d{6}$/;
const RESTORE_ORDER = ["identity", "tenant", "policy", "key", "registry", "immutable_authority", "integrity", "rls", "projection", "external_reconcile", "read_only_acceptance", "phased_mutation"];
const exact = (ref: ExactDrRef | null | undefined): ref is ExactDrRef => Boolean(ref && ref.resourceType && ref.resourceId && Number.isInteger(ref.revision) && ref.revision >= 1 && HASH.test(ref.contentHash));
const time = (value: string | null | undefined): value is string => Boolean(value && Number.isFinite(Date.parse(value)));
const nonNegative = (value: number | null | undefined): value is number => typeof value === "number" && Number.isFinite(value) && value >= 0;

export function evaluateWorkshopDisasterRecovery(evidence: DrEvidence): DrReadinessResult {
  const blockers = new Set<string>();
  if (![evidence.releaseRef, evidence.bundleRef, evidence.installationRef, evidence.drPlanRef].every(exact)) blockers.add("DR_RELEASE_ROOTS_REQUIRED");
  if (!time(evidence.evaluatedAt)) blockers.add("DR_CUTOFF_REQUIRED");

  let authorityDomainsVerified = 0;
  const inventory = evidence.authorityInventory;
  if (!inventory) blockers.add("DR_AUTHORITY_INVENTORY_REQUIRED");
  for (const domain of DR_AUTHORITY_DOMAINS) {
    const item = inventory?.find((candidate) => candidate.domain === domain);
    if (!item || !nonNegative(item.count) || !exact(item.inventoryRef) || !time(item.cutoffAt) || item.cutoffAt !== evidence.evaluatedAt) blockers.add(`DR_INVENTORY_${domain.toUpperCase()}_UNKNOWN`);
    else authorityDomainsVerified += 1;
  }

  let backupState: DrReadinessResult["backupState"] = "unknown";
  const backup = evidence.backup;
  if (!backup || !exact(backup.manifestRef) || !backup.logPosition || !HASH.test(backup.schemaHash ?? "") || !HASH.test(backup.appHash ?? "") || !HASH.test(backup.bundleHash ?? "") || !exact(backup.keyRevisionRef) || !exact(backup.retentionPolicyRef) || !exact(backup.objectManifestRef) || !time(backup.verifiedAt) || backup.verifiedAt !== evidence.evaluatedAt) {
    blockers.add("DR_BACKUP_MANIFEST_INCOMPLETE");
  } else if (backup.dependencyOrder.length !== RESTORE_ORDER.length || backup.dependencyOrder.some((item, index) => item !== RESTORE_ORDER[index])) {
    blockers.add("DR_RESTORE_ORDER_INVALID");
  } else backupState = "verified";

  let objectivesState: DrReadinessResult["objectivesState"] = "unknown";
  const objectives = evidence.objectives;
  if (!objectives || !nonNegative(objectives.approvedRpoSeconds) || !nonNegative(objectives.approvedRtoSeconds) || !nonNegative(objectives.measuredRpoSeconds) || !nonNegative(objectives.measuredRtoSeconds) || !exact(objectives.approvalRef) || !exact(objectives.measurementRef)) {
    blockers.add("DR_RPO_RTO_APPROVAL_AND_MEASUREMENT_REQUIRED");
  } else if (objectives.measuredRpoSeconds > objectives.approvedRpoSeconds || objectives.measuredRtoSeconds > objectives.approvedRtoSeconds) {
    objectivesState = "missed";
    blockers.add("DR_RPO_RTO_MISSED");
  } else objectivesState = "measured_within_approved";

  const recovery = evidence.recovery;
  if (!recovery || !exact(recovery.isolatedTargetRef) || !recovery.maker || !recovery.checker || !recovery.executor || new Set([recovery.maker, recovery.checker, recovery.executor]).size !== 3 || !exact(recovery.recoveryDecisionRef) || recovery.stageReceiptRefs.length !== RESTORE_ORDER.length || !recovery.stageReceiptRefs.every(exact) || !exact(recovery.failbackReceiptRef)) blockers.add("DR_ISOLATION_ROLE_RECEIPT_CHAIN_REQUIRED");

  let rlsChecksPassed = 0;
  const rls = evidence.rls;
  for (const check of DR_RLS_CHECKS) {
    const item = rls?.find((candidate) => candidate.check === check);
    if (!item || !item.passed || !exact(item.evidenceRef) || !time(item.cutoffAt) || item.cutoffAt !== evidence.evaluatedAt) blockers.add(`DR_RLS_${check.toUpperCase()}_REQUIRED`);
    else rlsChecksPassed += 1;
  }

  let projectionState: DrReadinessResult["projectionState"] = "unknown";
  const projection = evidence.projection;
  if (!projection || !exact(projection.checkpointRef) || !exact(projection.evidenceRef) || !REVISION.test(projection.authorityRevisionBefore ?? "") || !REVISION.test(projection.authorityRevisionAfter ?? "") || !nonNegative(projection.missing) || !nonNegative(projection.extra) || !nonNegative(projection.revisionMismatch) || !nonNegative(projection.conflict) || !nonNegative(projection.unknown) || !projection.resumed) {
    blockers.add("DR_PROJECTION_REBUILD_EVIDENCE_REQUIRED");
  } else if (projection.authorityRevisionBefore !== projection.authorityRevisionAfter) {
    blockers.add("DR_PROJECTION_MUTATED_AUTHORITY");
  } else if ([projection.missing, projection.extra, projection.revisionMismatch, projection.conflict, projection.unknown].some((value) => value !== 0)) {
    blockers.add("DR_PROJECTION_RECONCILIATION_OPEN");
  } else projectionState = "rebuild_verified";

  let externalAxesClosed = 0;
  for (const axis of DR_EXTERNAL_AXES) {
    const item = evidence.externalReconcile?.find((candidate) => candidate.axis === axis);
    if (!item || item.status !== "closed" || !exact(item.receiptRef)) blockers.add(`DR_EXTERNAL_${axis.toUpperCase()}_OPEN`);
    else externalAxesClosed += 1;
  }

  let drillsPassed = 0;
  for (const drill of DR_DRILLS) {
    const item = evidence.drills?.find((candidate) => candidate.drill === drill);
    if (!item || item.status !== "passed" || !exact(item.evidencePackRef)) blockers.add(`DR_DRILL_${drill.toUpperCase()}_REQUIRED`);
    else drillsPassed += 1;
  }

  return { status: blockers.size ? "blocked" : "ready", blockerCodes: [...blockers], authorityDomainsVerified, backupState, rlsChecksPassed, projectionState, externalAxesClosed, objectivesState, drillsPassed, commands: { inspectBackup: false, restore: false, rebuildProjection: false, changeRls: false, reconcileExternal: false, failover: false, failback: false } };
}
