import { INSTALLATION_DRAFT_FIXTURE } from "./installationFixtures";
import type {
  InstallationDecision,
  InstallationEvent,
  InstallationResponse,
  InstallationState,
} from "./types";

const INSTALLATION_ID = INSTALLATION_DRAFT_FIXTURE.installationId;
const HASH = INSTALLATION_DRAFT_FIXTURE.current.lockHash;
const DECISION_ID = "00000000-0000-4000-8000-000000000003";
const EVIDENCE_HASH = `sha256:${"b".repeat(64)}` as const;
const time = (revision: number) => `2026-08-03T08:0${revision - 1}:00+00:00`;

function current(state: InstallationState, revision: number) {
  return {
    ...INSTALLATION_DRAFT_FIXTURE.current,
    revision,
    parentRevision: revision === 1 ? null : revision - 1,
    state,
    decisionId: revision >= 3 ? DECISION_ID : null,
    createdAt: time(revision),
  };
}

function transition(
  revision: number,
  fromState: InstallationState,
  toState: InstallationState,
  actor: string,
  options: Pick<InstallationEvent, "reason" | "evidence"> = {
    reason: null,
    evidence: null,
  },
): InstallationEvent {
  return {
    sequence: revision,
    fromRevision: revision - 1,
    toRevision: revision,
    fromState,
    toState,
    actor,
    reason: options.reason,
    evidence: options.evidence,
    createdAt: time(revision),
  };
}

function decision(value: "approved" | "rejected"): InstallationDecision {
  return {
    decisionId: DECISION_ID,
    installationId: INSTALLATION_ID,
    submittedRevision: 2,
    decision: value,
    actor: "approver@example.test",
    lockHash: HASH,
    permissionDiffHash: HASH,
    migrationPlanHash: HASH,
    contributionDiffHash: HASH,
    reason: value === "rejected" ? "policy mismatch" : null,
    createdAt: time(3),
  };
}

const submittedEvent = transition(
  2,
  "draft",
  "submitted",
  INSTALLATION_DRAFT_FIXTURE.current.requestedBy,
);
const approvedEvent = transition(3, "submitted", "approved", "approver@example.test");

export const INSTALLATION_SUBMITTED_FIXTURE: InstallationResponse = {
  ...INSTALLATION_DRAFT_FIXTURE,
  state: "submitted",
  currentRevision: 2,
  etagVersion: 2,
  updatedAt: time(2),
  current: current("submitted", 2),
  events: [...INSTALLATION_DRAFT_FIXTURE.events, submittedEvent],
};

export const INSTALLATION_APPROVED_FIXTURE: InstallationResponse = {
  ...INSTALLATION_SUBMITTED_FIXTURE,
  state: "approved",
  currentRevision: 3,
  etagVersion: 3,
  updatedAt: time(3),
  current: current("approved", 3),
  decision: decision("approved"),
  events: [...INSTALLATION_SUBMITTED_FIXTURE.events, approvedEvent],
};

export const INSTALLATION_REJECTED_FIXTURE: InstallationResponse = {
  ...INSTALLATION_SUBMITTED_FIXTURE,
  state: "rejected",
  currentRevision: 3,
  etagVersion: 3,
  updatedAt: time(3),
  current: current("rejected", 3),
  decision: decision("rejected"),
  events: [
    ...INSTALLATION_SUBMITTED_FIXTURE.events,
    transition(3, "submitted", "rejected", "approver@example.test", {
      reason: "policy mismatch",
      evidence: null,
    }),
  ],
};

const dryApplyEvidence = {
  type: "dry_apply" as const,
  evidenceRef: "evidence://installations/dry-apply.json",
  evidenceHash: EVIDENCE_HASH,
  status: "valid" as const,
  observedAt: time(4),
};
const verificationEvidence = {
  type: "verification" as const,
  evidenceRef: "evidence://installations/verification.json",
  evidenceHash: EVIDENCE_HASH,
  status: "valid" as const,
  observedAt: time(5),
};
const rollbackEvidence = {
  type: "rollback" as const,
  evidenceRef: "evidence://installations/rollback.json",
  evidenceHash: EVIDENCE_HASH,
  status: "valid" as const,
  observedAt: time(6),
};

export const INSTALLATION_APPLIED_FIXTURE: InstallationResponse = {
  ...INSTALLATION_APPROVED_FIXTURE,
  state: "applied",
  currentRevision: 4,
  etagVersion: 4,
  updatedAt: time(4),
  current: current("applied", 4),
  events: [
    ...INSTALLATION_APPROVED_FIXTURE.events,
    transition(4, "approved", "applied", "installer@example.test", {
      reason: null,
      evidence: dryApplyEvidence,
    }),
  ],
};

export const INSTALLATION_ACTIVE_FIXTURE: InstallationResponse = {
  ...INSTALLATION_APPLIED_FIXTURE,
  state: "active",
  currentRevision: 5,
  activeRevision: 5,
  etagVersion: 5,
  updatedAt: time(5),
  current: current("active", 5),
  events: [
    ...INSTALLATION_APPLIED_FIXTURE.events,
    transition(5, "applied", "active", "installer@example.test", {
      reason: null,
      evidence: verificationEvidence,
    }),
  ],
};

export const INSTALLATION_ROLLED_BACK_FIXTURE: InstallationResponse = {
  ...INSTALLATION_ACTIVE_FIXTURE,
  state: "rolled_back",
  currentRevision: 6,
  activeRevision: null,
  previousActiveRevision: null,
  etagVersion: 6,
  updatedAt: time(6),
  current: current("rolled_back", 6),
  events: [
    ...INSTALLATION_ACTIVE_FIXTURE.events,
    transition(6, "active", "rolled_back", "installer@example.test", {
      reason: "operator rollback",
      evidence: rollbackEvidence,
    }),
  ],
};

export const INSTALLATION_ACTION_FIXTURES = [
  INSTALLATION_SUBMITTED_FIXTURE,
  INSTALLATION_APPROVED_FIXTURE,
  INSTALLATION_REJECTED_FIXTURE,
  INSTALLATION_APPLIED_FIXTURE,
  INSTALLATION_ACTIVE_FIXTURE,
  INSTALLATION_ROLLED_BACK_FIXTURE,
] as const;
