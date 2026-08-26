import type { ExactReleaseRef } from "./workshopCumulativeReleaseGate";

export const OPERATIONAL_CAPABILITIES = [
  { id: "task_orchestration", label: "任务编排", risk: "high" },
  { id: "content_campaign", label: "内容营销", risk: "medium" },
  { id: "creator_outreach", label: "达人触达", risk: "high" },
  { id: "media_production", label: "媒体生产", risk: "high" },
  { id: "analytics_learning", label: "分析学习", risk: "medium" },
  { id: "price_governance", label: "价格治理", risk: "critical" },
  { id: "customer_engagement", label: "客户运营", risk: "critical" },
  { id: "shared_context", label: "共享上下文", risk: "high" },
] as const;
export type OperationalCapabilityId = typeof OPERATIONAL_CAPABILITIES[number]["id"];
export type OperationalRisk = "low" | "medium" | "high" | "critical";
export type CapabilityReadiness = {
  capabilityId: OperationalCapabilityId; risk: OperationalRisk; status: "ready" | "blocked" | "not_applicable";
  candidateRef: ExactReleaseRef | null; cutoffAt: string | null; owner: string; approver: string;
  applicableGateIds: string[]; evidenceRefs: ExactReleaseRef[]; positiveRef: ExactReleaseRef | null; negativeRef: ExactReleaseRef | null;
  blockers: string[]; nextAllowedAction: string;
  notApplicable?: { scope: string; reason: string; owner: string; approver: string; evidenceRef: ExactReleaseRef | null } | null;
};
export type OperationalReleaseEvidence = {
  evaluatedAt?: string | null;
  candidate?: {
    candidateRef: ExactReleaseRef | null; gitCommit: string | null; gitClean: boolean | null; authorityRevision: string | null;
    artifactHash: string | null; bundleRef: ExactReleaseRef | null; installationRef: ExactReleaseRef | null;
    openApiHash: string | null; alembicHead: string | null; configHash: string | null; cutoffAt: string | null; immutable: boolean;
  } | null;
  cumulativeGate?: { status: "ready" | "blocked"; evidenceRef: ExactReleaseRef | null; candidateRef: ExactReleaseRef | null; cutoffAt: string | null; exact: boolean } | null;
  capabilities?: CapabilityReadiness[] | null;
  blockerCounts?: { p0: number | null; p1: number | null; criticalVulnerabilities: number | null; highVulnerabilities: number | null; openIncidents: number | null; unknownExternalActions: number | null } | null;
  approval?: {
    approvalRef: ExactReleaseRef | null; candidateRef: ExactReleaseRef | null; decision: "go" | "no_go"; capabilityIds: OperationalCapabilityId[];
    maker: string; checker: string; approver: string; issuedAt: string | null; expiresAt: string | null; revokedAt: string | null;
    residualRiskAcceptanceRef: ExactReleaseRef | null;
  } | null;
  rollout?: {
    cohort: string; audience: string; windowStart: string | null; windowEnd: string | null; observationMinutes: number | null;
    stopConditions: string[]; killOwner: string; rollbackOwner: string; failForwardOwner: string; compensationOwner: string; onCallOwner: string;
    supportPlanRef: ExactReleaseRef | null; auditRetentionRef: ExactReleaseRef | null; postReleaseVerificationRef: ExactReleaseRef | null;
  } | null;
  decisionReceipt?: { receiptRef: ExactReleaseRef | null; candidateRef: ExactReleaseRef | null; decision: "go" | "no_go"; cutoffAt: string | null; exact: boolean } | null;
};
export type OperationalReleaseDecisionResult = {
  decision: "go" | "no_go"; blockerCodes: string[]; capabilitiesReady: number; capabilitiesBlocked: number; capabilitiesNotApplicable: number;
  candidateState: "exact" | "unknown"; cumulativeState: "ready" | "blocked"; approvalState: "valid" | "missing"; rolloutState: "complete" | "missing"; receiptState: "exact" | "missing";
  commands: { approveCandidate: false; openFeatureFlag: false; startRollout: false; stopRollout: false; rollback: false; failForward: false; release: false };
};

const HASH = /^(?:sha256:)?[0-9a-f]{64}$/;
const COMMIT = /^[0-9a-f]{40}$/;
const REVISION = /^AOS-\d{6}$/;
const exact = (ref: ExactReleaseRef | null | undefined): ref is ExactReleaseRef => Boolean(ref && ref.resourceType && ref.resourceId && Number.isInteger(ref.revision) && ref.revision > 0 && HASH.test(ref.contentHash));
const sameRef = (left: ExactReleaseRef | null | undefined, right: ExactReleaseRef | null | undefined) => exact(left) && exact(right) && left.resourceType === right.resourceType && left.resourceId === right.resourceId && left.revision === right.revision && left.contentHash === right.contentHash;
const text = (value: string | null | undefined): value is string => Boolean(value?.trim());
const time = (value: string | null | undefined): value is string => Boolean(value && Number.isFinite(Date.parse(value)));
const nonNegative = (value: number | null | undefined): value is number => typeof value === "number" && Number.isInteger(value) && value >= 0;
const uniqueTexts = (values: string[]) => values.length > 0 && values.every(text) && new Set(values).size === values.length;

export function evaluateWorkshopOperationalReleaseDecision(evidence: OperationalReleaseEvidence): OperationalReleaseDecisionResult {
  const blockers = new Set<string>();
  const candidate = evidence.candidate;
  const candidateExact = Boolean(candidate && exact(candidate.candidateRef) && exact(candidate.bundleRef) && exact(candidate.installationRef)
    && COMMIT.test(candidate.gitCommit ?? "") && candidate.gitClean === true && REVISION.test(candidate.authorityRevision ?? "")
    && [candidate.artifactHash, candidate.openApiHash, candidate.configHash].every((value) => HASH.test(value ?? ""))
    && text(candidate.alembicHead) && time(candidate.cutoffAt) && candidate.immutable);
  if (!candidateExact) blockers.add("OPERATIONAL_RELEASE_CANDIDATE_EXACT_REQUIRED");

  const cumulative = evidence.cumulativeGate;
  const cumulativeReady = Boolean(cumulative && cumulative.status === "ready" && cumulative.exact && exact(cumulative.evidenceRef)
    && sameRef(cumulative.candidateRef, candidate?.candidateRef) && cumulative.cutoffAt === candidate?.cutoffAt);
  if (!cumulativeReady) blockers.add("OPERATIONAL_W8_11_CUMULATIVE_GREEN_REQUIRED");

  let capabilitiesReady = 0; let capabilitiesBlocked = 0; let capabilitiesNotApplicable = 0;
  for (const expected of OPERATIONAL_CAPABILITIES) {
    const matches = evidence.capabilities?.filter((item) => item.capabilityId === expected.id) ?? [];
    if (matches.length !== 1) { blockers.add(`OPERATIONAL_CAPABILITY_${expected.id.toUpperCase()}_REQUIRED`); capabilitiesBlocked += 1; continue; }
    const item = matches[0]; const prefix = `OPERATIONAL_CAPABILITY_${expected.id.toUpperCase()}`;
    const identityExact = item.risk === expected.risk && sameRef(item.candidateRef, candidate?.candidateRef) && item.cutoffAt === candidate?.cutoffAt && text(item.owner) && text(item.approver);
    if (!identityExact) blockers.add(`${prefix}_IDENTITY_REQUIRED`);
    if (item.status === "ready") {
      const positive = uniqueTexts(item.applicableGateIds) && item.evidenceRefs.length >= item.applicableGateIds.length && item.evidenceRefs.every(exact)
        && exact(item.positiveRef) && exact(item.negativeRef) && item.blockers.length === 0 && text(item.nextAllowedAction);
      if (!positive || !identityExact) { blockers.add(`${prefix}_POSITIVE_EVIDENCE_REQUIRED`); capabilitiesBlocked += 1; }
      else capabilitiesReady += 1;
    } else if (item.status === "not_applicable") {
      const na = item.notApplicable;
      if (!identityExact || !na || !text(na.scope) || !text(na.reason) || !text(na.owner) || !text(na.approver) || !exact(na.evidenceRef)) { blockers.add(`${prefix}_NOT_APPLICABLE_EVIDENCE_REQUIRED`); capabilitiesBlocked += 1; }
      else capabilitiesNotApplicable += 1;
    } else {
      capabilitiesBlocked += 1;
      if (!uniqueTexts(item.blockers) || !text(item.nextAllowedAction)) blockers.add(`${prefix}_BLOCKER_DETAIL_REQUIRED`);
      blockers.add(`${prefix}_BLOCKED`);
    }
  }

  const counts = evidence.blockerCounts;
  const countValues = counts ? [counts.p0, counts.p1, counts.criticalVulnerabilities, counts.highVulnerabilities, counts.openIncidents, counts.unknownExternalActions] : [];
  if (!counts || !countValues.every(nonNegative)) blockers.add("OPERATIONAL_RELEASE_BLOCKER_COUNTS_REQUIRED");
  else if (countValues.some((value) => value !== 0)) blockers.add("OPERATIONAL_RELEASE_BLOCKERS_OPEN");

  const approval = evidence.approval;
  const capabilityIds = approval?.capabilityIds ?? [];
  const approvalValid = Boolean(approval && approval.decision === "go" && exact(approval.approvalRef) && sameRef(approval.candidateRef, candidate?.candidateRef)
    && capabilityIds.length === OPERATIONAL_CAPABILITIES.length && OPERATIONAL_CAPABILITIES.every((item) => capabilityIds.includes(item.id)) && new Set(capabilityIds).size === capabilityIds.length
    && text(approval.maker) && text(approval.checker) && text(approval.approver) && approval.maker !== approval.checker
    && time(approval.issuedAt) && time(approval.expiresAt) && time(evidence.evaluatedAt) && Date.parse(approval.issuedAt!) <= Date.parse(evidence.evaluatedAt!)
    && Date.parse(approval.expiresAt!) > Date.parse(evidence.evaluatedAt!) && approval.revokedAt === null && exact(approval.residualRiskAcceptanceRef));
  if (!approvalValid) blockers.add("OPERATIONAL_RELEASE_APPROVAL_REQUIRED");

  const rollout = evidence.rollout;
  const rolloutComplete = Boolean(rollout && text(rollout.cohort) && text(rollout.audience) && time(rollout.windowStart) && time(rollout.windowEnd)
    && Date.parse(rollout.windowEnd!) > Date.parse(rollout.windowStart!) && nonNegative(rollout.observationMinutes) && rollout.observationMinutes! > 0
    && uniqueTexts(rollout.stopConditions) && [rollout.killOwner, rollout.rollbackOwner, rollout.failForwardOwner, rollout.compensationOwner, rollout.onCallOwner].every(text)
    && exact(rollout.supportPlanRef) && exact(rollout.auditRetentionRef) && exact(rollout.postReleaseVerificationRef));
  if (!rolloutComplete) blockers.add("OPERATIONAL_RELEASE_ROLLOUT_ROLLBACK_REQUIRED");

  const receipt = evidence.decisionReceipt;
  const receiptExact = Boolean(receipt && receipt.decision === "go" && receipt.exact && exact(receipt.receiptRef) && sameRef(receipt.candidateRef, candidate?.candidateRef) && receipt.cutoffAt === candidate?.cutoffAt);
  if (!receiptExact) blockers.add("OPERATIONAL_RELEASE_DECISION_RECEIPT_REQUIRED");

  return {
    decision: blockers.size ? "no_go" : "go", blockerCodes: [...blockers], capabilitiesReady, capabilitiesBlocked, capabilitiesNotApplicable,
    candidateState: candidateExact ? "exact" : "unknown", cumulativeState: cumulativeReady ? "ready" : "blocked", approvalState: approvalValid ? "valid" : "missing",
    rolloutState: rolloutComplete ? "complete" : "missing", receiptState: receiptExact ? "exact" : "missing",
    commands: { approveCandidate: false, openFeatureFlag: false, startRollout: false, stopRollout: false, rollback: false, failForward: false, release: false },
  };
}
