import type {
  InstallationListItem,
  InstallationListResponse,
  InstallationResponse,
} from "./types";

const INSTALLATION_ID = "00000000-0000-4000-8000-000000000002";
const COMPOSITION_ID = "00000000-0000-4000-8000-000000000001";
const DECISION_ID = "00000000-0000-4000-8000-000000000003";
const HASH = `sha256:${"a".repeat(64)}` as const;
const EVIDENCE_HASH = `sha256:${"b".repeat(64)}` as const;

export const INSTALLATION_LIST_ITEM_FIXTURE: InstallationListItem = {
  installationId: INSTALLATION_ID,
  displayName: "Commerce",
  state: "active",
  currentRevision: 5,
  activeRevision: 5,
  previousActiveRevision: null,
  etagVersion: 5,
  createdAt: "2026-08-03T08:00:00+00:00",
  updatedAt: "2026-08-03T08:04:00+00:00",
};

export const INSTALLATION_LIST_FIXTURE: InstallationListResponse = {
  items: [INSTALLATION_LIST_ITEM_FIXTURE],
  total: 1,
  limit: 50,
  offset: 0,
};

/**
 * Current revision plus canonical events; the API does not expose a synthetic
 * array of historical revision snapshots.
 */
export const INSTALLATION_DETAIL_FIXTURE: InstallationResponse = {
  ...INSTALLATION_LIST_ITEM_FIXTURE,
  current: {
    installationId: INSTALLATION_ID,
    revision: 5,
    parentRevision: 4,
    state: "active",
    compositionId: COMPOSITION_ID,
    lockRevision: 1,
    lockHash: HASH,
    permissionDiffHash: HASH,
    migrationPlanHash: HASH,
    contributionDiffHash: HASH,
    overlayRevision: "overlay-1",
    requestedBy: "maker@example.test",
    decisionId: DECISION_ID,
    createdAt: "2026-08-03T08:04:00+00:00",
  },
  decision: {
    decisionId: DECISION_ID,
    installationId: INSTALLATION_ID,
    submittedRevision: 2,
    decision: "approved",
    actor: "approver@example.test",
    lockHash: HASH,
    permissionDiffHash: HASH,
    migrationPlanHash: HASH,
    contributionDiffHash: HASH,
    reason: null,
    createdAt: "2026-08-03T08:02:00+00:00",
  },
  events: [
    {
      sequence: 1,
      fromRevision: null,
      toRevision: 1,
      fromState: null,
      toState: "draft",
      actor: "maker@example.test",
      reason: null,
      evidence: null,
      createdAt: "2026-08-03T08:00:00+00:00",
    },
    {
      sequence: 2,
      fromRevision: 1,
      toRevision: 2,
      fromState: "draft",
      toState: "submitted",
      actor: "maker@example.test",
      reason: null,
      evidence: null,
      createdAt: "2026-08-03T08:01:00+00:00",
    },
    {
      sequence: 3,
      fromRevision: 2,
      toRevision: 3,
      fromState: "submitted",
      toState: "approved",
      actor: "approver@example.test",
      reason: null,
      evidence: null,
      createdAt: "2026-08-03T08:02:00+00:00",
    },
    {
      sequence: 4,
      fromRevision: 3,
      toRevision: 4,
      fromState: "approved",
      toState: "applied",
      actor: "installer@example.test",
      reason: null,
      evidence: {
        type: "dry_apply",
        evidenceRef: "evidence://installations/dry-apply.json",
        evidenceHash: EVIDENCE_HASH,
        status: "valid",
        observedAt: "2026-08-03T08:03:00+00:00",
      },
      createdAt: "2026-08-03T08:03:00+00:00",
    },
    {
      sequence: 5,
      fromRevision: 4,
      toRevision: 5,
      fromState: "applied",
      toState: "active",
      actor: "installer@example.test",
      reason: null,
      evidence: {
        type: "verification",
        evidenceRef: "evidence://installations/verification.json",
        evidenceHash: EVIDENCE_HASH,
        status: "valid",
        observedAt: "2026-08-03T08:04:00+00:00",
      },
      createdAt: "2026-08-03T08:04:00+00:00",
    },
  ],
};
