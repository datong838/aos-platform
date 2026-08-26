export const CUMULATIVE_GATE_COLUMNS = [
  "contract_schema", "unit_parser", "store_rls_cas_append_only", "service_integration", "openapi", "alembic",
  "bundle_resolver_installation_eval", "web_typecheck_build", "browser_a11y", "security_supply_chain",
  "fault_restart_race_reconcile", "operational_slo_runbook_dr", "diff_generated_honesty", "receipts_exact_readback",
] as const;
export const RELEASE_MODULES = ["task-cockpit", "content-campaign", "creator-outreach", "media-studio", "analyst", "price-governance", "customer", "shared-context"] as const;
export type CumulativeGateColumn = typeof CUMULATIVE_GATE_COLUMNS[number];
export type ExactReleaseRef = { resourceType: string; resourceId: string; revision: number; contentHash: string };
export type ExceptionSignal = "skipped" | "n_a" | "xfail" | "warning" | "unavailable";
export type GateDisposition = { signal: ExceptionSignal; reason: string; owner: string; decisionRef: ExactReleaseRef | null };
export type GateEvidence = {
  column: CumulativeGateColumn; required: boolean; status: "passed" | "failed" | "blocked" | "failed_close" | "unknown";
  command: string | null; exitCode: number | null; scope: string[]; artifactRef: ExactReleaseRef | null; evidenceRef: ExactReleaseRef | null;
  gitCommit: string | null; releaseRevision: string | null; cutoffAt: string | null; dispositions: GateDisposition[];
  drifted: boolean; rerunAfterDrift: boolean;
};
export type CumulativeReleaseEvidence = {
  releaseRef?: ExactReleaseRef | null; bundleRef?: ExactReleaseRef | null; installationRef?: ExactReleaseRef | null;
  authorityRevision?: string | null; gitCommit?: string | null; gitClean?: boolean | null; cutoffAt?: string | null;
  buildHash?: string | null; openApiHash?: string | null; sdkHash?: string | null; alembicHead?: string | null;
  schemaHash?: string | null; bundleHash?: string | null; lockHash?: string | null;
  moduleRefs?: Array<{ moduleId: typeof RELEASE_MODULES[number]; ref: ExactReleaseRef | null }> | null;
  gates?: GateEvidence[] | null;
  tenantEvidence?: {
    positiveTenant: string | null; negativeTenant: string | null; positivePassed: boolean; negativePassed: boolean;
    positiveRef: ExactReleaseRef | null; negativeRef: ExactReleaseRef | null; cutoffAt: string | null;
  } | null;
  blockerCounts?: { p0: number | null; p1: number | null; critical: number | null; high: number | null; releaseUnknown: number | null } | null;
  receiptReadback?: { receiptRef: ExactReleaseRef | null; gitCommit: string | null; releaseRevision: string | null; cutoffAt: string | null; exact: boolean } | null;
};
export type CumulativeReleaseGateResult = {
  status: "ready" | "blocked"; blockerCodes: string[]; gatesPassed: number; modulesVerified: number;
  identityState: "exact" | "unknown"; tenantState: "isolated" | "unknown"; receiptState: "exact" | "unknown";
  commands: { runTests: false; generateOpenApi: false; applyMigration: false; installBundle: false; fixSecurity: false; mutateGenerated: false; release: false };
};

const HASH = /^(?:sha256:)?[0-9a-f]{64}$/;
const COMMIT = /^[0-9a-f]{40}$/;
const REVISION = /^AOS-\d{6}$/;
const exact = (ref: ExactReleaseRef | null | undefined): ref is ExactReleaseRef => Boolean(ref && ref.resourceType && ref.resourceId && Number.isInteger(ref.revision) && ref.revision > 0 && HASH.test(ref.contentHash));
const time = (value: string | null | undefined): value is string => Boolean(value && Number.isFinite(Date.parse(value)));
const nonNegative = (value: number | null | undefined): value is number => typeof value === "number" && Number.isInteger(value) && value >= 0;
const text = (value: string | null | undefined): value is string => Boolean(value?.trim());

export function evaluateWorkshopCumulativeReleaseGate(evidence: CumulativeReleaseEvidence): CumulativeReleaseGateResult {
  const blockers = new Set<string>();
  const identityExact = exact(evidence.releaseRef) && exact(evidence.bundleRef) && exact(evidence.installationRef)
    && REVISION.test(evidence.authorityRevision ?? "") && COMMIT.test(evidence.gitCommit ?? "") && evidence.gitClean === true && time(evidence.cutoffAt)
    && [evidence.buildHash, evidence.openApiHash, evidence.sdkHash, evidence.schemaHash, evidence.bundleHash, evidence.lockHash].every((value) => HASH.test(value ?? ""))
    && text(evidence.alembicHead);
  if (!identityExact) blockers.add("CUMULATIVE_RELEASE_IDENTITY_REQUIRED");

  let modulesVerified = 0;
  for (const moduleId of RELEASE_MODULES) {
    const matches = evidence.moduleRefs?.filter((item) => item.moduleId === moduleId) ?? [];
    if (matches.length !== 1 || !exact(matches[0].ref)) blockers.add(`CUMULATIVE_MODULE_${moduleId.replace(/-/g, "_").toUpperCase()}_REQUIRED`);
    else modulesVerified += 1;
  }

  let gatesPassed = 0;
  for (const column of CUMULATIVE_GATE_COLUMNS) {
    const matches = evidence.gates?.filter((gate) => gate.column === column) ?? [];
    if (matches.length !== 1) { blockers.add(`CUMULATIVE_GATE_${column.toUpperCase()}_REQUIRED`); continue; }
    const gate = matches[0];
    const sameIdentity = COMMIT.test(gate.gitCommit ?? "") && gate.gitCommit === evidence.gitCommit && REVISION.test(gate.releaseRevision ?? "") && gate.releaseRevision === evidence.authorityRevision && time(gate.cutoffAt) && gate.cutoffAt === evidence.cutoffAt;
    const commandEvidence = text(gate.command) && gate.exitCode === 0 && gate.scope.length > 0 && gate.scope.every(text) && exact(gate.artifactRef) && exact(gate.evidenceRef);
    const dispositionComplete = gate.dispositions.every((item) => text(item.reason) && text(item.owner) && exact(item.decisionRef));
    if (!sameIdentity) blockers.add(`CUMULATIVE_GATE_${column.toUpperCase()}_IDENTITY_DRIFT`);
    if (!commandEvidence) blockers.add(`CUMULATIVE_GATE_${column.toUpperCase()}_EVIDENCE_INCOMPLETE`);
    if (!dispositionComplete) blockers.add(`CUMULATIVE_GATE_${column.toUpperCase()}_DISPOSITION_INCOMPLETE`);
    if (gate.drifted && !gate.rerunAfterDrift) blockers.add(`CUMULATIVE_GATE_${column.toUpperCase()}_RERUN_REQUIRED`);
    if (gate.required && gate.status !== "passed") blockers.add(`CUMULATIVE_GATE_${column.toUpperCase()}_POSITIVE_REQUIRED`);
    if (sameIdentity && commandEvidence && dispositionComplete && (!gate.drifted || gate.rerunAfterDrift) && (!gate.required || gate.status === "passed")) gatesPassed += 1;
  }

  let tenantState: CumulativeReleaseGateResult["tenantState"] = "unknown";
  const tenant = evidence.tenantEvidence;
  if (!tenant || tenant.positiveTenant !== "org-org/dev-project" || tenant.negativeTenant !== "dev-org/dev-project" || !tenant.positivePassed || !tenant.negativePassed || !exact(tenant.positiveRef) || !exact(tenant.negativeRef) || !time(tenant.cutoffAt) || tenant.cutoffAt !== evidence.cutoffAt) blockers.add("CUMULATIVE_TENANT_POSITIVE_NEGATIVE_REQUIRED");
  else tenantState = "isolated";

  const counts = evidence.blockerCounts;
  if (!counts || ![counts.p0, counts.p1, counts.critical, counts.high, counts.releaseUnknown].every(nonNegative)) blockers.add("CUMULATIVE_BLOCKER_COUNTS_REQUIRED");
  else if ([counts.p0, counts.p1, counts.critical, counts.high, counts.releaseUnknown].some((value) => value !== 0)) blockers.add("CUMULATIVE_RELEASE_BLOCKERS_OPEN");

  let receiptState: CumulativeReleaseGateResult["receiptState"] = "unknown";
  const readback = evidence.receiptReadback;
  if (!readback || !exact(readback.receiptRef) || !readback.exact || readback.gitCommit !== evidence.gitCommit || readback.releaseRevision !== evidence.authorityRevision || readback.cutoffAt !== evidence.cutoffAt) blockers.add("CUMULATIVE_RECEIPT_EXACT_READBACK_REQUIRED");
  else receiptState = "exact";

  return {
    status: blockers.size ? "blocked" : "ready", blockerCodes: [...blockers], gatesPassed, modulesVerified,
    identityState: identityExact ? "exact" : "unknown", tenantState, receiptState,
    commands: { runTests: false, generateOpenApi: false, applyMigration: false, installBundle: false, fixSecurity: false, mutateGenerated: false, release: false },
  };
}
