import type {
  InstallationDecision,
  InstallationEvent,
  InstallationEventEvidence,
  InstallationListItem,
  InstallationListResponse,
  InstallationResponse,
  InstallationRevision,
  InstallationState,
} from "./types";

const INSTALLATION_STATES = new Set<InstallationState>([
  "draft",
  "submitted",
  "approved",
  "rejected",
  "applied",
  "active",
  "rolled_back",
]);
const TERMINAL_DECISION_STATES = new Set<InstallationState>([
  "approved",
  "rejected",
  "applied",
  "active",
  "rolled_back",
]);
const PRE_ACTIVE_STATES = new Set<InstallationState>([
  "draft",
  "submitted",
  "approved",
  "rejected",
  "applied",
]);
const TRANSITIONS = new Set([
  "draft:submitted",
  "submitted:approved",
  "submitted:rejected",
  "approved:applied",
  "applied:active",
  "active:rolled_back",
]);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const SHA256 = /^sha256:[0-9a-f]{64}$/;
const TIMEZONE_SUFFIX = /(?:Z|[+-][0-9]{2}:[0-9]{2})$/;
const LIST_ITEM_KEYS = [
  "installationId",
  "displayName",
  "state",
  "currentRevision",
  "activeRevision",
  "previousActiveRevision",
  "etagVersion",
  "createdAt",
  "updatedAt",
] as const;

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

function exactKeys(
  value: Record<string, unknown>,
  required: readonly string[],
  label: string,
): void {
  const allowed = new Set(required);
  const missing = required.filter((key) => !(key in value));
  const extra = Object.keys(value).filter((key) => !allowed.has(key));
  if (missing.length || extra.length) {
    throw new Error(
      `${label} keys mismatch; missing=${missing.join(",")}; extra=${extra.join(",")}`,
    );
  }
}

function normalizedString(value: unknown, label: string): asserts value is string {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value !== value.trim() ||
    value.includes("\0")
  ) {
    throw new Error(`${label} must be a non-empty normalized string`);
  }
}

function nullableNormalizedString(value: unknown, label: string): void {
  if (value !== null) normalizedString(value, label);
}

function positiveInteger(value: unknown, label: string): asserts value is number {
  if (!Number.isSafeInteger(value) || (value as number) < 1) {
    throw new Error(`${label} must be a positive safe integer`);
  }
}

function nonNegativeInteger(value: unknown, label: string): asserts value is number {
  if (!Number.isSafeInteger(value) || (value as number) < 0) {
    throw new Error(`${label} must be a non-negative safe integer`);
  }
}

function nullablePositiveInteger(value: unknown, label: string): void {
  if (value !== null) positiveInteger(value, label);
}

function uuid(value: unknown, label: string): asserts value is string {
  normalizedString(value, label);
  if (!UUID.test(value)) throw new Error(`${label} must be a canonical UUID`);
}

function nullableUuid(value: unknown, label: string): void {
  if (value !== null) uuid(value, label);
}

function sha256(value: unknown, label: string): asserts value is string {
  normalizedString(value, label);
  if (!SHA256.test(value)) throw new Error(`${label} must be a sha256 digest`);
}

function timestamp(value: unknown, label: string): asserts value is string {
  normalizedString(value, label);
  if (
    !value.includes("T") ||
    !TIMEZONE_SUFFIX.test(value) ||
    Number.isNaN(Date.parse(value))
  ) {
    throw new Error(`${label} must be an ISO timestamp with timezone`);
  }
}

function state(value: unknown, label: string): asserts value is InstallationState {
  if (!INSTALLATION_STATES.has(value as InstallationState)) {
    throw new Error(`${label} is invalid`);
  }
}

function validateListItem(value: unknown, label: string): InstallationListItem {
  const item = record(value, label);
  exactKeys(item, LIST_ITEM_KEYS, label);
  uuid(item.installationId, `${label}.installationId`);
  normalizedString(item.displayName, `${label}.displayName`);
  state(item.state, `${label}.state`);
  positiveInteger(item.currentRevision, `${label}.currentRevision`);
  nullablePositiveInteger(item.activeRevision, `${label}.activeRevision`);
  nullablePositiveInteger(
    item.previousActiveRevision,
    `${label}.previousActiveRevision`,
  );
  positiveInteger(item.etagVersion, `${label}.etagVersion`);
  timestamp(item.createdAt, `${label}.createdAt`);
  timestamp(item.updatedAt, `${label}.updatedAt`);

  if (Date.parse(item.updatedAt) < Date.parse(item.createdAt)) {
    throw new Error(`${label}.updatedAt must not precede createdAt`);
  }
  if (item.etagVersion !== item.currentRevision) {
    throw new Error(`${label}.etagVersion must equal currentRevision`);
  }
  const activeRevision = item.activeRevision as number | null;
  const previousActiveRevision = item.previousActiveRevision as number | null;
  for (const pointerName of ["activeRevision", "previousActiveRevision"] as const) {
    const pointer = item[pointerName];
    if (pointer !== null && (pointer as number) > item.currentRevision) {
      throw new Error(`${label}.${pointerName} exceeds currentRevision`);
    }
  }
  if (
    PRE_ACTIVE_STATES.has(item.state) &&
    (activeRevision !== null || previousActiveRevision !== null)
  ) {
    throw new Error(`${label} pre-active state cannot expose active pointers`);
  }
  if (item.state === "active") {
    if (activeRevision !== item.currentRevision) {
      throw new Error(`${label} activeRevision must equal currentRevision`);
    }
    if (
      previousActiveRevision !== null &&
      previousActiveRevision >= item.currentRevision
    ) {
      throw new Error(`${label}.previousActiveRevision must precede currentRevision`);
    }
  }
  if (
    item.state === "rolled_back" &&
    (activeRevision === item.currentRevision ||
      activeRevision !== previousActiveRevision)
  ) {
    throw new Error(`${label} rollback pointers are inconsistent`);
  }
  return value as InstallationListItem;
}

function validateRevision(value: unknown): InstallationRevision {
  const label = "Installation current revision";
  const item = record(value, label);
  exactKeys(
    item,
    [
      "installationId",
      "revision",
      "parentRevision",
      "state",
      "compositionId",
      "lockRevision",
      "lockHash",
      "permissionDiffHash",
      "migrationPlanHash",
      "contributionDiffHash",
      "overlayRevision",
      "requestedBy",
      "decisionId",
      "createdAt",
    ],
    label,
  );
  uuid(item.installationId, `${label}.installationId`);
  positiveInteger(item.revision, `${label}.revision`);
  nullablePositiveInteger(item.parentRevision, `${label}.parentRevision`);
  state(item.state, `${label}.state`);
  uuid(item.compositionId, `${label}.compositionId`);
  positiveInteger(item.lockRevision, `${label}.lockRevision`);
  for (const key of [
    "lockHash",
    "permissionDiffHash",
    "migrationPlanHash",
    "contributionDiffHash",
  ] as const) {
    sha256(item[key], `${label}.${key}`);
  }
  normalizedString(item.overlayRevision, `${label}.overlayRevision`);
  normalizedString(item.requestedBy, `${label}.requestedBy`);
  nullableUuid(item.decisionId, `${label}.decisionId`);
  timestamp(item.createdAt, `${label}.createdAt`);

  const expectedParent = item.revision === 1 ? null : item.revision - 1;
  if (item.parentRevision !== expectedParent) {
    throw new Error(`${label}.parentRevision must identify the previous revision`);
  }
  if (TERMINAL_DECISION_STATES.has(item.state) !== (item.decisionId !== null)) {
    throw new Error(`${label}.decisionId is inconsistent with state`);
  }
  return value as InstallationRevision;
}

function validateDecision(value: unknown): InstallationDecision | null {
  if (value === null) return null;
  const label = "Installation decision";
  const item = record(value, label);
  exactKeys(
    item,
    [
      "decisionId",
      "installationId",
      "submittedRevision",
      "decision",
      "actor",
      "lockHash",
      "permissionDiffHash",
      "migrationPlanHash",
      "contributionDiffHash",
      "reason",
      "createdAt",
    ],
    label,
  );
  uuid(item.decisionId, `${label}.decisionId`);
  uuid(item.installationId, `${label}.installationId`);
  positiveInteger(item.submittedRevision, `${label}.submittedRevision`);
  if (item.decision !== "approved" && item.decision !== "rejected") {
    throw new Error(`${label}.decision is invalid`);
  }
  normalizedString(item.actor, `${label}.actor`);
  for (const key of [
    "lockHash",
    "permissionDiffHash",
    "migrationPlanHash",
    "contributionDiffHash",
  ] as const) {
    sha256(item[key], `${label}.${key}`);
  }
  nullableNormalizedString(item.reason, `${label}.reason`);
  timestamp(item.createdAt, `${label}.createdAt`);
  if (item.decision === "rejected" && item.reason === null) {
    throw new Error(`${label}.reason is required for rejection`);
  }
  return value as InstallationDecision;
}

function validateEvidence(value: unknown): InstallationEventEvidence | null {
  if (value === null) return null;
  const label = "Installation event evidence";
  const item = record(value, label);
  exactKeys(
    item,
    ["type", "evidenceRef", "evidenceHash", "status", "observedAt"],
    label,
  );
  if (!new Set(["dry_apply", "verification", "rollback"]).has(item.type as string)) {
    throw new Error(`${label}.type is invalid`);
  }
  normalizedString(item.evidenceRef, `${label}.evidenceRef`);
  sha256(item.evidenceHash, `${label}.evidenceHash`);
  if (item.status !== "valid" && item.status !== "invalid") {
    throw new Error(`${label}.status is invalid`);
  }
  timestamp(item.observedAt, `${label}.observedAt`);
  return value as InstallationEventEvidence;
}

function validateEvent(value: unknown, index: number): InstallationEvent {
  const label = `Installation event[${index}]`;
  const item = record(value, label);
  exactKeys(
    item,
    [
      "sequence",
      "fromRevision",
      "toRevision",
      "fromState",
      "toState",
      "actor",
      "reason",
      "evidence",
      "createdAt",
    ],
    label,
  );
  positiveInteger(item.sequence, `${label}.sequence`);
  nullablePositiveInteger(item.fromRevision, `${label}.fromRevision`);
  positiveInteger(item.toRevision, `${label}.toRevision`);
  if (item.fromState !== null) state(item.fromState, `${label}.fromState`);
  state(item.toState, `${label}.toState`);
  normalizedString(item.actor, `${label}.actor`);
  nullableNormalizedString(item.reason, `${label}.reason`);
  validateEvidence(item.evidence);
  timestamp(item.createdAt, `${label}.createdAt`);
  if ((item.fromRevision === null) !== (item.fromState === null)) {
    throw new Error(`${label} fromRevision and fromState must share null state`);
  }
  return value as InstallationEvent;
}

/** Fail-closed parser for GET /v1/bundle-installations. */
export function parseInstallationList(value: unknown): InstallationListResponse {
  const item = record(value, "Installation list");
  exactKeys(item, ["items", "total", "limit", "offset"], "Installation list");
  if (!Array.isArray(item.items)) throw new Error("Installation list.items must be an array");
  nonNegativeInteger(item.total, "Installation list.total");
  positiveInteger(item.limit, "Installation list.limit");
  nonNegativeInteger(item.offset, "Installation list.offset");
  if (item.limit > 100) throw new Error("Installation list.limit must be <= 100");
  if (item.offset > 10_000) throw new Error("Installation list.offset must be <= 10000");
  if (item.items.length > item.limit) {
    throw new Error("Installation list contains more items than limit");
  }
  item.items.forEach((entry, index) => validateListItem(entry, `Installation list.items[${index}]`));
  return value as InstallationListResponse;
}

/** Fail-closed parser for the current installation record and its event history. */
export function parseInstallationDetail(value: unknown): InstallationResponse {
  const recordValue = record(value, "Installation detail");
  exactKeys(
    recordValue,
    [...LIST_ITEM_KEYS, "current", "decision", "events"],
    "Installation detail",
  );
  const summary = validateListItem(
    Object.fromEntries(LIST_ITEM_KEYS.map((key) => [key, recordValue[key]])),
    "Installation detail",
  );
  const current = validateRevision(recordValue.current);
  const decision = validateDecision(recordValue.decision);
  if (!Array.isArray(recordValue.events)) {
    throw new Error("Installation detail.events must be an array");
  }
  const events = recordValue.events.map(validateEvent);

  if (
    current.installationId !== summary.installationId ||
    current.revision !== summary.currentRevision ||
    current.state !== summary.state
  ) {
    throw new Error("Installation detail current revision is inconsistent");
  }
  if (current.decisionId === null ? decision !== null : decision?.decisionId !== current.decisionId) {
    throw new Error("Installation detail decision does not match current decisionId");
  }
  if (decision !== null) {
    if (
      decision.installationId !== summary.installationId ||
      decision.submittedRevision >= summary.currentRevision ||
      decision.actor === current.requestedBy
    ) {
      throw new Error("Installation detail decision identity is inconsistent");
    }
    for (const key of [
      "lockHash",
      "permissionDiffHash",
      "migrationPlanHash",
      "contributionDiffHash",
    ] as const) {
      if (decision[key] !== current[key]) {
        throw new Error(`Installation detail decision ${key} does not match current`);
      }
    }
    const expectedDecision = current.state === "rejected" ? "rejected" : "approved";
    if (decision.decision !== expectedDecision) {
      throw new Error("Installation detail decision is inconsistent with current state");
    }
  }
  if (events.length !== summary.currentRevision) {
    throw new Error("Installation detail event count must equal currentRevision");
  }
  const first = events[0];
  if (
    first === undefined ||
    first.sequence !== 1 ||
    first.fromRevision !== null ||
    first.fromState !== null ||
    first.toRevision !== 1 ||
    first.toState !== "draft"
  ) {
    throw new Error("Installation detail history must begin with draft revision 1");
  }
  for (let index = 1; index < events.length; index += 1) {
    const previous = events[index - 1];
    const event = events[index];
    if (
      event.sequence !== index + 1 ||
      event.fromRevision !== previous.toRevision ||
      event.fromState !== previous.toState ||
      event.toRevision !== previous.toRevision + 1 ||
      !TRANSITIONS.has(`${previous.toState}:${event.toState}`)
    ) {
      throw new Error("Installation detail event history is not continuous");
    }
  }
  const tail = events[events.length - 1];
  if (tail.toRevision !== summary.currentRevision || tail.toState !== current.state) {
    throw new Error("Installation detail event tail does not match current revision");
  }
  if (
    decision !== null &&
    events.filter(
      (event) =>
        event.toRevision === decision.submittedRevision &&
        event.toState === "submitted",
    ).length !== 1
  ) {
    throw new Error("Installation detail decision must reference submitted event");
  }
  return value as InstallationResponse;
}
