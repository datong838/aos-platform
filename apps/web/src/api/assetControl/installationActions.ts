import type {
  ApproveInstallationRequest,
  EmptyInstallationActionRequest,
  InstallationResponse,
  RejectInstallationRequest,
  RollbackInstallationRequest,
  Sha256,
  StoredCompositionLock,
  UninstallInstallationRequest,
} from "./types";

const SHA256 = /^sha256:[0-9a-f]{64}$/;
const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f-\u009f]/;
const MAX_REASON_LENGTH = 2_000;

function objectRecord(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

function exactKeys(
  record: Record<string, unknown>,
  expected: readonly string[],
  label: string,
): void {
  const keys = Object.keys(record).sort();
  const required = [...expected].sort();
  if (keys.length !== required.length || keys.some((key, index) => key !== required[index])) {
    throw new TypeError(`${label} must contain exactly: ${required.join(", ")}`);
  }
}

function sha256(value: unknown, label: string): Sha256 {
  if (typeof value !== "string" || !SHA256.test(value)) {
    throw new TypeError(`${label} must be a canonical sha256 digest`);
  }
  return value as Sha256;
}

function reason(value: unknown, label: string): string {
  if (
    typeof value !== "string" ||
    value.length < 1 ||
    value.length > MAX_REASON_LENGTH ||
    value !== value.trim() ||
    CONTROL_CHARACTERS.test(value)
  ) {
    throw new TypeError(`${label} must be a normalized non-empty string of at most ${MAX_REASON_LENGTH} characters`);
  }
  return value;
}

export function serializeEmptyInstallationAction(
  value: unknown = {},
): EmptyInstallationActionRequest {
  const record = objectRecord(value, "installation action request");
  exactKeys(record, [], "installation action request");
  return {};
}

export function serializeApproveInstallationRequest(
  value: unknown,
): ApproveInstallationRequest {
  const record = objectRecord(value, "approve installation request");
  exactKeys(
    record,
    ["lockHash", "permissionDiffHash", "migrationPlanHash", "contributionDiffHash"],
    "approve installation request",
  );
  return {
    lockHash: sha256(record.lockHash, "lockHash"),
    permissionDiffHash: sha256(record.permissionDiffHash, "permissionDiffHash"),
    migrationPlanHash: sha256(record.migrationPlanHash, "migrationPlanHash"),
    contributionDiffHash: sha256(record.contributionDiffHash, "contributionDiffHash"),
  };
}

export function serializeRejectInstallationRequest(
  value: unknown,
): RejectInstallationRequest {
  const record = objectRecord(value, "reject installation request");
  exactKeys(record, ["reason"], "reject installation request");
  return { reason: reason(record.reason, "reason") };
}

export function serializeRollbackInstallationRequest(
  value: unknown,
): RollbackInstallationRequest {
  const record = objectRecord(value, "rollback installation request");
  exactKeys(record, ["reason"], "rollback installation request");
  return { reason: reason(record.reason, "reason") };
}

export function serializeUninstallInstallationRequest(
  value: unknown,
): UninstallInstallationRequest {
  const record = objectRecord(value, "uninstall installation request");
  exactKeys(record, ["reason"], "uninstall installation request");
  return { reason: reason(record.reason, "reason") };
}

export function buildApproveInstallationRequest(
  installation: InstallationResponse,
  lock: StoredCompositionLock,
): ApproveInstallationRequest {
  const current = installation.current;
  if (installation.state !== "submitted" || current.state !== "submitted") {
    throw new TypeError("approval requires the current submitted installation revision");
  }
  if (
    current.compositionId !== lock.compositionId ||
    current.lockRevision !== lock.revision
  ) {
    throw new TypeError("installation and composition lock identity do not match");
  }

  const fields = [
    "lockHash",
    "permissionDiffHash",
    "migrationPlanHash",
    "contributionDiffHash",
  ] as const;
  for (const field of fields) {
    if (current[field] !== lock[field]) {
      throw new TypeError(`installation and composition lock ${field} do not match`);
    }
  }

  return serializeApproveInstallationRequest({
    lockHash: lock.lockHash,
    permissionDiffHash: lock.permissionDiffHash,
    migrationPlanHash: lock.migrationPlanHash,
    contributionDiffHash: lock.contributionDiffHash,
  });
}
