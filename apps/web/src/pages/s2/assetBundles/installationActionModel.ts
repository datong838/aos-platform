import type { AssetControlError } from "../../../api/assetControl/errors";
import type { IdempotentCommand } from "../../../api/assetControl/idempotency";
import type {
  ApproveInstallationRequest,
  InstallationResponse,
  InstallationState,
  RejectInstallationRequest,
  RollbackInstallationRequest,
} from "../../../api/assetControl/types";

export type InstallationActionName =
  | "submit"
  | "approve"
  | "reject"
  | "apply"
  | "verify"
  | "rollback";

export type InstallationActionPhase =
  | "idle"
  | "running"
  | "reconciling"
  | "succeeded"
  | "conflict"
  | "forbidden"
  | "not_visible_or_missing"
  | "unknown_outcome"
  | "error";

export type InstallationActionReconciliation =
  | "none"
  | "preflight"
  | "final_read"
  | "confirmed"
  | "unchanged"
  | "diverged"
  | "unavailable";

export interface InstallationActionPrincipal {
  readonly subject: string | null;
  readonly roles: readonly string[] | null;
}

export interface InstallationActionSource {
  readonly state: InstallationState;
  readonly currentRevision: number;
  readonly etagVersion: number;
}

export type InstallationActionBody =
  | Record<string, never>
  | ApproveInstallationRequest
  | RejectInstallationRequest
  | RollbackInstallationRequest;

export interface InstallationActionAttempt {
  readonly action: InstallationActionName;
  readonly installationId: string;
  readonly source: InstallationActionSource;
  readonly expectedState: InstallationState;
  readonly body: Readonly<InstallationActionBody>;
  readonly command: Readonly<IdempotentCommand>;
  readonly actorSubject: string;
}

export interface InstallationActionCommandState {
  readonly phase: InstallationActionPhase;
  readonly action: InstallationActionName | null;
  readonly data: InstallationResponse | null;
  readonly error: AssetControlError | null;
  readonly reconcileError: AssetControlError | null;
  readonly attempt: Readonly<InstallationActionAttempt> | null;
  readonly reconciliation: InstallationActionReconciliation;
  readonly requiresRefresh: boolean;
  readonly canRecoverUnknown: boolean;
  readonly mutationConfirmed: boolean;
}

export type InstallationActionBlockReason =
  | "allowed"
  | "no_installation"
  | "principal_unknown"
  | "role_denied"
  | "maker_checker"
  | "invalid_state";

export interface InstallationActionEligibility {
  readonly allowed: boolean;
  readonly reason: InstallationActionBlockReason;
}

export const INSTALLATION_ACTIONS: readonly InstallationActionName[] = [
  "submit",
  "approve",
  "reject",
  "apply",
  "verify",
  "rollback",
];

export const INSTALLATION_ACTION_TRANSITIONS: Readonly<
  Record<InstallationActionName, { from: InstallationState; to: InstallationState }>
> = {
  submit: { from: "draft", to: "submitted" },
  approve: { from: "submitted", to: "approved" },
  reject: { from: "submitted", to: "rejected" },
  apply: { from: "approved", to: "applied" },
  verify: { from: "applied", to: "active" },
  rollback: { from: "active", to: "rolled_back" },
};

const ACTION_ROLES: Readonly<Record<InstallationActionName, ReadonlySet<string>>> = {
  submit: new Set(["admin", "developer", "asset-installer"]),
  approve: new Set(["admin", "asset-install-approver"]),
  reject: new Set(["admin", "asset-install-approver"]),
  apply: new Set(["admin", "asset-installer"]),
  verify: new Set(["admin", "asset-installer"]),
  rollback: new Set(["admin", "asset-installer"]),
};

export function initialInstallationActionState(): InstallationActionCommandState {
  return {
    phase: "idle",
    action: null,
    data: null,
    error: null,
    reconcileError: null,
    attempt: null,
    reconciliation: "none",
    requiresRefresh: false,
    canRecoverUnknown: false,
    mutationConfirmed: false,
  };
}

export function installationActionEligibility(
  installation: InstallationResponse | null,
  principal: InstallationActionPrincipal,
  action: InstallationActionName,
): InstallationActionEligibility {
  if (installation === null) return blocked("no_installation");
  const subject = principal.subject?.trim();
  if (!subject || principal.roles === null) return blocked("principal_unknown");
  const roles = new Set(principal.roles.map((role) => role.trim().toLowerCase()));
  if (![...ACTION_ROLES[action]].some((role) => roles.has(role))) {
    return blocked("role_denied");
  }
  if (installation.state !== INSTALLATION_ACTION_TRANSITIONS[action].from) {
    return blocked("invalid_state");
  }
  if (
    (action === "approve" || action === "reject") &&
    subject === installation.current.requestedBy
  ) {
    return blocked("maker_checker");
  }
  return { allowed: true, reason: "allowed" };
}

export function normalizeInstallationActionReason(reason: string): string {
  const normalized = reason.trim();
  if (
    normalized.length < 1 ||
    normalized.length > 2_000 ||
    /[\u0000-\u001f\u007f-\u009f]/u.test(normalized)
  ) {
    throw new TypeError("reason must be a normalized string with 1-2000 characters");
  }
  return normalized;
}

export function createInstallationActionAttempt(options: {
  action: InstallationActionName;
  installation: InstallationResponse;
  body: InstallationActionBody;
  command: Readonly<IdempotentCommand>;
  actorSubject: string;
}): Readonly<InstallationActionAttempt> {
  const transition = INSTALLATION_ACTION_TRANSITIONS[options.action];
  return Object.freeze({
    action: options.action,
    installationId: options.installation.installationId,
    source: Object.freeze({
      state: options.installation.state,
      currentRevision: options.installation.currentRevision,
      etagVersion: options.installation.etagVersion,
    }),
    expectedState: transition.to,
    body: Object.freeze({ ...options.body }),
    command: options.command,
    actorSubject: options.actorSubject,
  });
}

export function exactActionSuccessWasObserved(
  attempt: InstallationActionAttempt,
  current: InstallationResponse,
): boolean {
  if (
    current.installationId !== attempt.installationId ||
    current.state !== attempt.expectedState ||
    current.currentRevision !== attempt.source.currentRevision + 1 ||
    current.current.parentRevision !== attempt.source.currentRevision ||
    current.current.revision !== current.currentRevision ||
    current.etagVersion <= attempt.source.etagVersion
  ) {
    return false;
  }
  const event = current.events.find(
    (candidate) =>
      candidate.fromRevision === attempt.source.currentRevision &&
      candidate.toRevision === current.currentRevision,
  );
  if (
    !event ||
    event.fromState !== attempt.source.state ||
    event.toState !== attempt.expectedState ||
    event.actor !== attempt.actorSubject
  ) {
    return false;
  }
  if (attempt.action === "reject" || attempt.action === "rollback") {
    if (event.reason !== (attempt.body as RejectInstallationRequest).reason) {
      return false;
    }
  }
  if (attempt.action === "approve") {
    const body = attempt.body as ApproveInstallationRequest;
    return (
      current.decision?.decision === "approved" &&
      current.current.decisionId === current.decision.decisionId &&
      current.decision.actor === attempt.actorSubject &&
      current.decision.lockHash === body.lockHash &&
      current.decision.permissionDiffHash === body.permissionDiffHash &&
      current.decision.migrationPlanHash === body.migrationPlanHash &&
      current.decision.contributionDiffHash === body.contributionDiffHash
    );
  }
  if (attempt.action === "reject") {
    return (
      current.decision?.decision === "rejected" &&
      current.current.decisionId === current.decision.decisionId &&
      current.decision.actor === attempt.actorSubject &&
      current.decision.reason === (attempt.body as RejectInstallationRequest).reason &&
      event.evidence === null
    );
  }
  const evidenceType =
    attempt.action === "apply"
      ? "dry_apply"
      : attempt.action === "verify"
        ? "verification"
        : attempt.action === "rollback"
          ? "rollback"
          : undefined;
  if (evidenceType !== undefined) {
    return event.evidence?.type === evidenceType && event.evidence.status === "valid";
  }
  return event.reason === null && event.evidence === null;
}

export function phaseForInstallationActionError(
  error: AssetControlError,
): InstallationActionPhase {
  if (error.outcomeUnknown) return "unknown_outcome";
  if (error.isConflict) return "conflict";
  if (error.kind === "forbidden") return "forbidden";
  if (error.kind === "not_visible_or_missing") return "not_visible_or_missing";
  return "error";
}

function blocked(reason: InstallationActionBlockReason): InstallationActionEligibility {
  return { allowed: false, reason };
}
