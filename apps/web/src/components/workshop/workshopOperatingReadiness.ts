export const OPERATING_SLI_IDS = [
  "view_availability", "freshness_lag", "latency", "partial_ratio", "unknown_ratio",
  "unknown_backlog_age", "reconcile_age", "receipt_closure", "usage_quality", "effect_maturity",
] as const;

export const OPERATING_AXIS_IDS = ["action", "usage", "lineage", "effect", "handoff"] as const;
export const USAGE_BUCKET_IDS = ["measured", "estimated", "unknown", "adjustment", "refund", "dispute", "unattributed"] as const;
export const REQUIRED_DRILL_IDS = [
  "mass_unknown", "provider_timeout_rate_webhook", "action_backlog_kill", "usage_integrity",
  "stage_lease_capacity", "installation_drift", "rls_guc", "pii_share", "effect_late_data", "monitoring_silence",
] as const;

export type ExactOperatingRef = {
  resourceType: string;
  resourceId: string;
  revision: number;
  contentHash: string;
};

export type OperatingSli = {
  id: typeof OPERATING_SLI_IDS[number];
  sampleCount: number | null;
  unknownCount: number | null;
  sourceRef: ExactOperatingRef | null;
  cutoffAt: string | null;
};

export type OperatingSlo = {
  sliId: typeof OPERATING_SLI_IDS[number];
  owner: string | null;
  population: string | null;
  eligibility: string | null;
  eventClock: string | null;
  window: string | null;
  target: number | null;
  errorBudget: number | null;
  sourceRevisionRef: ExactOperatingRef | null;
  baselineEvidenceRef: ExactOperatingRef | null;
};

export type UnknownBacklogItem = {
  itemId: string;
  firstUnknownAt: string;
  observedAt: string;
  requestFingerprint: string;
  providerRef: ExactOperatingRef | null;
  accountRef: ExactOperatingRef | null;
  adapterRef: ExactOperatingRef | null;
  policyRef: ExactOperatingRef | null;
  leaseRef: ExactOperatingRef | null;
  riskExposure: string | null;
  lastCanonicalReconcileAt: string | null;
  restartedAt?: string | null;
};

export type UsageQualityLedger = {
  currency: string | null;
  cutoffAt: string | null;
  buckets: Partial<Record<typeof USAGE_BUCKET_IDS[number], number | null>>;
  sourceRefs: ExactOperatingRef[];
  integrityAlerts: Array<"missing" | "duplicate" | "hash_drift" | "currency_drift">;
};

export type OperatingEvidence = {
  releaseRef?: ExactOperatingRef | null;
  bundleRef?: ExactOperatingRef | null;
  installationRef?: ExactOperatingRef | null;
  evaluatedAt?: string | null;
  slis?: OperatingSli[];
  slos?: OperatingSlo[];
  unknownBacklog?: UnknownBacklogItem[] | null;
  usage?: UsageQualityLedger | null;
  alertPolicyRef?: ExactOperatingRef | null;
  alertLedgerRef?: ExactOperatingRef | null;
  axes?: Array<{ axisId: typeof OPERATING_AXIS_IDS[number]; status: "closed" | "open" | "unknown"; receiptRef: ExactOperatingRef | null }>;
  alertLifecycle?: Array<{ kind: "alert" | "ack" | "silence" | "escalation" | "resolution"; receiptRef: ExactOperatingRef; canonicalRereadRef?: ExactOperatingRef | null }>;
  runbookRef?: ExactOperatingRef | null;
  drills?: Array<{ drillId: typeof REQUIRED_DRILL_IDS[number]; evidencePackRef: ExactOperatingRef | null; status: "passed" | "failed" | "unknown" }>;
};

export type OperatingReadinessResult = {
  status: "ready" | "blocked";
  blockerCodes: string[];
  unknownBacklogCount: number | null;
  oldestUnknownAgeMs: number | null;
  closedAxes: number;
  usageState: "measured" | "unknown";
  runbookState: "drilled" | "defined" | "missing";
  commands: { alert: false; ack: false; silence: false; escalate: false; resolve: false; reconcile: false };
};

const HASH = /^(?:sha256:)?[0-9a-f]{64}$/;

function exact(ref: ExactOperatingRef | null | undefined): ref is ExactOperatingRef {
  return Boolean(ref && ref.resourceType && ref.resourceId && Number.isInteger(ref.revision) && ref.revision >= 1 && HASH.test(ref.contentHash));
}

function validTime(value: string | null | undefined): value is string {
  return Boolean(value && Number.isFinite(Date.parse(value)));
}

export function evaluateWorkshopOperatingReadiness(evidence: OperatingEvidence): OperatingReadinessResult {
  const blockers = new Set<string>();
  const roots = [evidence.releaseRef, evidence.bundleRef, evidence.installationRef];
  if (!roots.every(exact)) blockers.add("OPERATING_RELEASE_ROOTS_REQUIRED");
  if (!validTime(evidence.evaluatedAt)) blockers.add("OPERATING_CUTOFF_REQUIRED");

  const slis = evidence.slis ?? [];
  for (const id of OPERATING_SLI_IDS) {
    const sli = slis.find((item) => item.id === id);
    if (!sli || sli.sampleCount === null || sli.unknownCount === null || sli.sampleCount < 0 || sli.unknownCount < 0 || sli.unknownCount > sli.sampleCount || !exact(sli.sourceRef) || !validTime(sli.cutoffAt) || sli.cutoffAt !== evidence.evaluatedAt) {
      blockers.add(`SLI_${id.toUpperCase()}_UNKNOWN`);
    }
  }

  const slos = evidence.slos ?? [];
  for (const id of OPERATING_SLI_IDS) {
    const slo = slos.find((item) => item.sliId === id);
    if (!slo || !slo.owner || !slo.population || !slo.eligibility || !slo.eventClock || !slo.window || typeof slo.target !== "number" || slo.target < 0 || slo.target > 1 || typeof slo.errorBudget !== "number" || slo.errorBudget < 0 || slo.errorBudget > 1 || !exact(slo.sourceRevisionRef) || !exact(slo.baselineEvidenceRef)) {
      blockers.add(`SLO_${id.toUpperCase()}_TBD`);
    }
  }

  const backlog = evidence.unknownBacklog;
  let oldestUnknownAgeMs: number | null = null;
  if (!backlog) {
    blockers.add("UNKNOWN_BACKLOG_AUTHORITY_REQUIRED");
  } else {
    const evaluatedAt = validTime(evidence.evaluatedAt) ? Date.parse(evidence.evaluatedAt) : null;
    for (const item of backlog) {
      const first = Date.parse(item.firstUnknownAt);
      const observed = Date.parse(item.observedAt);
      const restarted = item.restartedAt ? Date.parse(item.restartedAt) : null;
      if (!item.itemId || !HASH.test(item.requestFingerprint) || !Number.isFinite(first) || !Number.isFinite(observed) || first > observed || (evaluatedAt !== null && observed > evaluatedAt) || !exact(item.providerRef) || !exact(item.accountRef) || !exact(item.adapterRef) || !exact(item.policyRef) || !exact(item.leaseRef) || !item.riskExposure) {
        blockers.add("UNKNOWN_BACKLOG_ITEM_INCOMPLETE");
      }
      if (restarted !== null && Number.isFinite(restarted) && restarted < first) blockers.add("UNKNOWN_AGE_RESET_DETECTED");
      if (evaluatedAt !== null && Number.isFinite(first)) oldestUnknownAgeMs = Math.max(oldestUnknownAgeMs ?? 0, evaluatedAt - first);
    }
  }

  const usage = evidence.usage;
  let usageState: OperatingReadinessResult["usageState"] = "unknown";
  if (!usage || !usage.currency || !validTime(usage.cutoffAt) || usage.cutoffAt !== evidence.evaluatedAt || !usage.sourceRefs.length || !usage.sourceRefs.every(exact)) {
    blockers.add("USAGE_AUTHORITY_REQUIRED");
  } else {
    const complete = USAGE_BUCKET_IDS.every((id) => {
      const value = usage.buckets[id];
      return typeof value === "number" && Number.isFinite(value) && value >= 0;
    });
    if (!complete) blockers.add("USAGE_QUALITY_BUCKET_UNKNOWN");
    else usageState = "measured";
    if (usage.integrityAlerts.length) blockers.add("USAGE_INTEGRITY_ALERT_OPEN");
  }

  const axes = evidence.axes ?? [];
  let closedAxes = 0;
  for (const id of OPERATING_AXIS_IDS) {
    const axis = axes.find((item) => item.axisId === id);
    if (!axis || axis.status !== "closed" || !exact(axis.receiptRef)) blockers.add(`AXIS_${id.toUpperCase()}_OPEN`);
    else closedAxes += 1;
  }

  const lifecycle = evidence.alertLifecycle ?? [];
  if (!exact(evidence.alertPolicyRef) || !exact(evidence.alertLedgerRef)) blockers.add("ALERT_POLICY_AND_LEDGER_REQUIRED");
  for (const item of lifecycle) {
    if (!exact(item.receiptRef)) blockers.add("ALERT_RECEIPT_INVALID");
    if (item.kind === "resolution" && !exact(item.canonicalRereadRef)) blockers.add("ALERT_RESOLUTION_REREAD_REQUIRED");
  }

  const drills = evidence.drills ?? [];
  let runbookState: OperatingReadinessResult["runbookState"] = exact(evidence.runbookRef) ? "defined" : "missing";
  if (!exact(evidence.runbookRef)) blockers.add("RUNBOOK_REQUIRED");
  for (const id of REQUIRED_DRILL_IDS) {
    const drill = drills.find((item) => item.drillId === id);
    if (!drill || drill.status !== "passed" || !exact(drill.evidencePackRef)) blockers.add(`DRILL_${id.toUpperCase()}_REQUIRED`);
  }
  if (exact(evidence.runbookRef) && REQUIRED_DRILL_IDS.every((id) => drills.some((item) => item.drillId === id && item.status === "passed" && exact(item.evidencePackRef)))) runbookState = "drilled";

  return {
    status: blockers.size ? "blocked" : "ready",
    blockerCodes: [...blockers],
    unknownBacklogCount: backlog ? backlog.length : null,
    oldestUnknownAgeMs,
    closedAxes,
    usageState,
    runbookState,
    commands: { alert: false, ack: false, silence: false, escalate: false, resolve: false, reconcile: false },
  };
}
