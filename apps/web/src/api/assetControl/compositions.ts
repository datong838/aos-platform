import type {
  CompositionRequest,
  CreateInstallationRequest,
  CurrentInstallationRef,
  StoredCompositionLock,
} from "./types";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const SHA256 = /^sha256:[0-9a-f]{64}$/;
const BUNDLE_ID = /^[a-z0-9]+(?:[.-][a-z0-9]+)*$/;
const CAPABILITY_ID = /^[a-z0-9]+(?:[._-][a-z0-9]+)*$/;
const TIMEZONE_SUFFIX = /(?:Z|[+-][0-9]{2}:[0-9]{2})$/;
const BUNDLE_KINDS = new Set([
  "DomainPack",
  "SolutionPack",
  "VerticalPack",
  "PlatformAdapterPack",
  "PluginPack",
]);

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

function exactKeys(
  value: Record<string, unknown>,
  required: readonly string[],
  optional: readonly string[],
  label: string,
): void {
  const allowed = new Set([...required, ...optional]);
  const missing = required.filter((key) => !(key in value));
  const extra = Object.keys(value).filter((key) => !allowed.has(key));
  if (missing.length || extra.length) {
    throw new Error(
      `${label} keys mismatch; missing=${missing.join(",")}; extra=${extra.join(",")}`,
    );
  }
}

function text(
  value: unknown,
  label: string,
  options: { max?: number; pattern?: RegExp } = {},
): asserts value is string {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value !== value.trim() ||
    value.includes("\0") ||
    (options.max !== undefined && value.length > options.max) ||
    (options.pattern !== undefined && !options.pattern.test(value))
  ) {
    throw new Error(`${label} is invalid`);
  }
}

function nullableText(value: unknown, label: string, max?: number): void {
  if (value !== null) text(value, label, { max });
}

function positiveInteger(value: unknown, label: string): asserts value is number {
  if (!Number.isSafeInteger(value) || (value as number) < 1) {
    throw new Error(`${label} must be a positive safe integer`);
  }
}

function uuid(value: unknown, label: string): asserts value is string {
  text(value, label, { pattern: UUID });
}

function sha256(
  value: unknown,
  label: string,
): asserts value is `sha256:${string}` {
  text(value, label, { pattern: SHA256 });
}

function timestamp(value: unknown, label: string): asserts value is string {
  text(value, label);
  if (
    !value.includes("T") ||
    !TIMEZONE_SUFFIX.test(value) ||
    Number.isNaN(Date.parse(value))
  ) {
    throw new Error(`${label} must be an ISO timestamp with timezone`);
  }
}

function stringArray(value: unknown, label: string, pattern?: RegExp): void {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
  value.forEach((entry, index) =>
    text(entry, `${label}[${index}]`, { pattern }),
  );
}

function requestedBundle(value: unknown, label: string): void {
  const item = record(value, label);
  exactKeys(item, ["publisher", "id", "version"], [], label);
  text(item.publisher, `${label}.publisher`, { max: 120, pattern: BUNDLE_ID });
  text(item.id, `${label}.id`, { max: 160, pattern: BUNDLE_ID });
  // The server remains authoritative for semantic-version range parsing.
  text(item.version, `${label}.version`, { max: 256 });
}

function currentInstallationRef(
  value: unknown,
  label: string,
): CurrentInstallationRef {
  const item = record(value, label);
  exactKeys(
    item,
    ["installationId", "revision", "lockHash", "overlayRevision"],
    [],
    label,
  );
  uuid(item.installationId, `${label}.installationId`);
  positiveInteger(item.revision, `${label}.revision`);
  sha256(item.lockHash, `${label}.lockHash`);
  text(item.overlayRevision, `${label}.overlayRevision`, { max: 160 });
  return {
    installationId: item.installationId,
    revision: item.revision,
    lockHash: item.lockHash,
    overlayRevision: item.overlayRevision,
  };
}

/** Build the exact resolve body without forwarding caller-owned extra fields. */
export function serializeCompositionRequest(value: unknown): CompositionRequest {
  const item = record(value, "Composition request");
  exactKeys(
    item,
    ["requested", "platformApiVersion", "platformRelease", "environment"],
    ["registrySnapshotHash", "currentInstallationRef"],
    "Composition request",
  );
  if (
    !Array.isArray(item.requested) ||
    item.requested.length < 1 ||
    item.requested.length > 64
  ) {
    throw new Error("Composition request.requested must contain 1-64 entries");
  }
  item.requested.forEach((entry, index) =>
    requestedBundle(entry, `Composition request.requested[${index}]`),
  );
  const coordinates = item.requested.map((entry) => {
    const coordinate = entry as Record<string, unknown>;
    return `${coordinate.publisher}\0${coordinate.id}`;
  });
  if (new Set(coordinates).size !== coordinates.length) {
    throw new Error("Composition request bundle coordinates must be unique");
  }
  text(item.platformApiVersion, "Composition request.platformApiVersion", {
    max: 256,
  });
  text(item.platformRelease, "Composition request.platformRelease", { max: 160 });
  if (!new Set(["dev", "staging", "prod"]).has(item.environment as string)) {
    throw new Error("Composition request.environment is invalid");
  }

  const result: CompositionRequest = {
    requested: item.requested.map((entry) => {
      const bundle = entry as Record<string, string>;
      return {
        publisher: bundle.publisher,
        id: bundle.id,
        version: bundle.version,
      };
    }),
    platformApiVersion: item.platformApiVersion,
    platformRelease: item.platformRelease,
    environment: item.environment as CompositionRequest["environment"],
  };
  if (Object.prototype.hasOwnProperty.call(item, "registrySnapshotHash")) {
    if (item.registrySnapshotHash !== null) {
      sha256(item.registrySnapshotHash, "Composition request.registrySnapshotHash");
    }
    result.registrySnapshotHash = item.registrySnapshotHash as
      | `sha256:${string}`
      | null;
  }
  if (Object.prototype.hasOwnProperty.call(item, "currentInstallationRef")) {
    result.currentInstallationRef =
      item.currentInstallationRef === null
        ? null
        : currentInstallationRef(
            item.currentInstallationRef,
            "Composition request.currentInstallationRef",
          );
  }
  return result;
}

/** Build the exact installation create body without forwarding injected data. */
export function serializeCreateInstallationRequest(
  value: unknown,
): CreateInstallationRequest {
  const item = record(value, "Create installation request");
  exactKeys(
    item,
    ["compositionId", "lockRevision", "overlayRevision", "displayName"],
    [],
    "Create installation request",
  );
  uuid(item.compositionId, "Create installation request.compositionId");
  positiveInteger(item.lockRevision, "Create installation request.lockRevision");
  text(item.overlayRevision, "Create installation request.overlayRevision", {
    max: 160,
  });
  text(item.displayName, "Create installation request.displayName", { max: 240 });
  return {
    compositionId: item.compositionId,
    lockRevision: item.lockRevision,
    overlayRevision: item.overlayRevision,
    displayName: item.displayName,
  };
}

function dependency(value: unknown, label: string): void {
  const item = record(value, label);
  exactKeys(item, ["publisher", "id", "version"], [], label);
  text(item.publisher, `${label}.publisher`, { max: 120, pattern: BUNDLE_ID });
  text(item.id, `${label}.id`, { max: 160, pattern: BUNDLE_ID });
  text(item.version, `${label}.version`, { max: 256 });
}

function conflict(value: unknown, label: string): void {
  const item = record(value, label);
  exactKeys(item, ["publisher", "id", "version"], [], label);
  text(item.publisher, `${label}.publisher`, { max: 120, pattern: BUNDLE_ID });
  text(item.id, `${label}.id`, { max: 160, pattern: BUNDLE_ID });
  nullableText(item.version, `${label}.version`, 256);
}

function permissionSet(value: unknown, label: string): void {
  const item = record(value, label);
  exactKeys(item, ["roles", "markings", "dataScopes", "actionTypes"], [], label);
  for (const key of ["roles", "markings", "dataScopes", "actionTypes"] as const) {
    stringArray(item[key], `${label}.${key}`);
  }
}

function contributionClaim(value: unknown, label: string): void {
  const item = record(value, label);
  if (item.kind === "api") {
    exactKeys(item, ["kind", "method", "path", "operationId", "mode"], [], label);
    text(item.method, `${label}.method`, { max: 16 });
    text(item.path, `${label}.path`, { max: 1024 });
    text(item.operationId, `${label}.operationId`, { max: 160 });
    if (item.mode !== "exclusive") throw new Error(`${label}.mode is invalid`);
    return;
  }
  if (item.kind === "navigation") {
    exactKeys(item, ["kind", "route", "mode"], [], label);
    text(item.route, `${label}.route`, { max: 1024 });
    if (item.mode !== "exclusive" && item.mode !== "shared") {
      throw new Error(`${label}.mode is invalid`);
    }
    return;
  }
  if (item.kind === "ui") {
    exactKeys(item, ["kind", "slot", "id", "mode"], [], label);
    text(item.slot, `${label}.slot`, { max: 160, pattern: BUNDLE_ID });
    text(item.id, `${label}.id`, { max: 160, pattern: BUNDLE_ID });
    if (item.mode !== "exclusive" && item.mode !== "shared") {
      throw new Error(`${label}.mode is invalid`);
    }
    return;
  }
  throw new Error(`${label}.kind is invalid`);
}

function migrationDescriptor(value: unknown, label: string): void {
  const item = record(value, label);
  exactKeys(item, ["planRef", "downgradePolicy"], [], label);
  nullableText(item.planRef, `${label}.planRef`, 1024);
  if (item.downgradePolicy !== "retain-canonical") {
    throw new Error(`${label}.downgradePolicy is invalid`);
  }
}

function resolvedBundle(value: unknown, index: number): void {
  const label = `Composition lock.payload.resolved[${index}]`;
  const item = record(value, label);
  exactKeys(
    item,
    [
      "publisher", "id", "version", "kind", "contentHash",
      "signatureFingerprint", "releaseEvidenceRevision", "dependencies",
      "optionalDependencies", "conflicts", "capabilities", "permissions",
      "migration", "contributions", "selectionReason",
    ],
    [],
    label,
  );
  text(item.publisher, `${label}.publisher`, { max: 120, pattern: BUNDLE_ID });
  text(item.id, `${label}.id`, { max: 160, pattern: BUNDLE_ID });
  text(item.version, `${label}.version`, { max: 256 });
  if (!BUNDLE_KINDS.has(item.kind as string)) throw new Error(`${label}.kind is invalid`);
  for (const key of [
    "contentHash",
    "signatureFingerprint",
    "releaseEvidenceRevision",
  ] as const) {
    sha256(item[key], `${label}.${key}`);
  }
  for (const key of ["dependencies", "optionalDependencies"] as const) {
    if (!Array.isArray(item[key])) throw new Error(`${label}.${key} must be an array`);
    item[key].forEach((entry, childIndex) =>
      dependency(entry, `${label}.${key}[${childIndex}]`),
    );
  }
  if (!Array.isArray(item.conflicts)) throw new Error(`${label}.conflicts must be an array`);
  item.conflicts.forEach((entry, childIndex) =>
    conflict(entry, `${label}.conflicts[${childIndex}]`),
  );
  const capabilities = record(item.capabilities, `${label}.capabilities`);
  exactKeys(capabilities, ["provides", "requires"], [], `${label}.capabilities`);
  stringArray(capabilities.provides, `${label}.capabilities.provides`, CAPABILITY_ID);
  stringArray(capabilities.requires, `${label}.capabilities.requires`, CAPABILITY_ID);
  permissionSet(item.permissions, `${label}.permissions`);
  migrationDescriptor(item.migration, `${label}.migration`);
  if (!Array.isArray(item.contributions)) {
    throw new Error(`${label}.contributions must be an array`);
  }
  item.contributions.forEach((entry, childIndex) =>
    contributionClaim(entry, `${label}.contributions[${childIndex}]`),
  );
  if (item.selectionReason !== "requested" && item.selectionReason !== "dependency") {
    throw new Error(`${label}.selectionReason is invalid`);
  }
}

function edge(value: unknown, index: number): void {
  const label = `Composition lock.payload.edges[${index}]`;
  const item = record(value, label);
  exactKeys(
    item,
    [
      "fromPublisher", "fromId", "fromVersion", "toPublisher", "toId",
      "toVersion", "constraint", "optional",
    ],
    [],
    label,
  );
  for (const key of ["fromPublisher", "toPublisher"] as const) {
    text(item[key], `${label}.${key}`, { max: 120, pattern: BUNDLE_ID });
  }
  for (const key of ["fromId", "toId"] as const) {
    text(item[key], `${label}.${key}`, { max: 160, pattern: BUNDLE_ID });
  }
  for (const key of ["fromVersion", "toVersion", "constraint"] as const) {
    text(item[key], `${label}.${key}`, { max: 256 });
  }
  if (typeof item.optional !== "boolean") throw new Error(`${label}.optional is invalid`);
}

function capabilityProvider(value: unknown, index: number): void {
  const label = `Composition lock.payload.capabilityProviders[${index}]`;
  const item = record(value, label);
  exactKeys(item, ["capability", "publisher", "id", "version"], [], label);
  text(item.capability, `${label}.capability`, { max: 160, pattern: CAPABILITY_ID });
  text(item.publisher, `${label}.publisher`, { max: 120, pattern: BUNDLE_ID });
  text(item.id, `${label}.id`, { max: 160, pattern: BUNDLE_ID });
  text(item.version, `${label}.version`, { max: 256 });
}

function permissionDiff(value: unknown): void {
  const label = "Composition lock.payload.permissionDiff";
  const item = record(value, label);
  exactKeys(item, ["baseline", "target", "added", "removed", "unchanged"], [], label);
  for (const key of ["baseline", "target", "added", "removed", "unchanged"] as const) {
    permissionSet(item[key], `${label}.${key}`);
  }
}

function migrationStep(value: unknown, label: string): void {
  const item = record(value, label);
  exactKeys(item, ["publisher", "id", "version", "planRef", "downgradePolicy"], [], label);
  text(item.publisher, `${label}.publisher`, { max: 120, pattern: BUNDLE_ID });
  text(item.id, `${label}.id`, { max: 160, pattern: BUNDLE_ID });
  text(item.version, `${label}.version`, { max: 256 });
  text(item.planRef, `${label}.planRef`, { max: 1024 });
  if (item.downgradePolicy !== "retain-canonical") {
    throw new Error(`${label}.downgradePolicy is invalid`);
  }
}

function migrationDiff(value: unknown): void {
  const label = "Composition lock.payload.migrationPlan";
  const item = record(value, label);
  exactKeys(item, ["baseline", "target", "added", "removed", "changed"], [], label);
  for (const key of ["baseline", "target", "added", "removed"] as const) {
    if (!Array.isArray(item[key])) throw new Error(`${label}.${key} must be an array`);
    item[key].forEach((entry, index) => migrationStep(entry, `${label}.${key}[${index}]`));
  }
  if (!Array.isArray(item.changed)) throw new Error(`${label}.changed must be an array`);
  item.changed.forEach((entry, index) => {
    const changeLabel = `${label}.changed[${index}]`;
    const change = record(entry, changeLabel);
    exactKeys(change, ["publisher", "id", "before", "after"], [], changeLabel);
    text(change.publisher, `${changeLabel}.publisher`, { max: 120, pattern: BUNDLE_ID });
    text(change.id, `${changeLabel}.id`, { max: 160, pattern: BUNDLE_ID });
    migrationStep(change.before, `${changeLabel}.before`);
    migrationStep(change.after, `${changeLabel}.after`);
  });
}

function contributionBinding(value: unknown, label: string): void {
  const item = record(value, label);
  exactKeys(item, ["publisher", "id", "version", "claim"], [], label);
  text(item.publisher, `${label}.publisher`, { max: 120, pattern: BUNDLE_ID });
  text(item.id, `${label}.id`, { max: 160, pattern: BUNDLE_ID });
  text(item.version, `${label}.version`, { max: 256 });
  contributionClaim(item.claim, `${label}.claim`);
}

function contributionDiff(value: unknown): void {
  const label = "Composition lock.payload.contributionDiff";
  const item = record(value, label);
  exactKeys(item, ["baseline", "target", "added", "removed", "unchanged"], [], label);
  for (const key of ["baseline", "target", "added", "removed", "unchanged"] as const) {
    if (!Array.isArray(item[key])) throw new Error(`${label}.${key} must be an array`);
    item[key].forEach((entry, index) =>
      contributionBinding(entry, `${label}.${key}[${index}]`),
    );
  }
}

function canonicalRequest(value: unknown): void {
  const item = record(value, "Composition lock.payload.request");
  exactKeys(
    item,
    ["requested", "platformApiVersion", "platformRelease", "environment"],
    [],
    "Composition lock.payload.request",
  );
  if (!Array.isArray(item.requested) || item.requested.length < 1) {
    throw new Error("Composition lock.payload.request.requested must be non-empty");
  }
  item.requested.forEach((entry, index) =>
    requestedBundle(entry, `Composition lock.payload.request.requested[${index}]`),
  );
  text(item.platformApiVersion, "Composition lock.payload.request.platformApiVersion", { max: 256 });
  text(item.platformRelease, "Composition lock.payload.request.platformRelease", { max: 160 });
  if (!new Set(["dev", "staging", "prod"]).has(item.environment as string)) {
    throw new Error("Composition lock.payload.request.environment is invalid");
  }
}

/** Fail-closed parser for resolve and get-lock success responses. */
export function parseStoredCompositionLock(value: unknown): StoredCompositionLock {
  const item = record(value, "Composition lock");
  exactKeys(
    item,
    [
      "compositionId", "revision", "payload", "lockHash", "permissionDiffHash",
      "migrationPlanHash", "contributionDiffHash", "createdAt",
    ],
    [],
    "Composition lock",
  );
  uuid(item.compositionId, "Composition lock.compositionId");
  positiveInteger(item.revision, "Composition lock.revision");
  for (const key of [
    "lockHash",
    "permissionDiffHash",
    "migrationPlanHash",
    "contributionDiffHash",
  ] as const) {
    sha256(item[key], `Composition lock.${key}`);
  }
  timestamp(item.createdAt, "Composition lock.createdAt");

  const payload = record(item.payload, "Composition lock.payload");
  exactKeys(
    payload,
    [
      "lockSchemaVersion", "resolverVersion", "request", "registrySnapshotHash",
      "resolved", "edges", "capabilityProviders", "permissionDiff",
      "migrationPlan", "contributionDiff", "currentInstallationRef",
    ],
    [],
    "Composition lock.payload",
  );
  if (payload.lockSchemaVersion !== "aos.dev/composition-lock/v1alpha1") {
    throw new Error("Composition lock.payload.lockSchemaVersion is invalid");
  }
  if (payload.resolverVersion !== "aos-resolver/1.0.0") {
    throw new Error("Composition lock.payload.resolverVersion is invalid");
  }
  canonicalRequest(payload.request);
  sha256(payload.registrySnapshotHash, "Composition lock.payload.registrySnapshotHash");
  if (!Array.isArray(payload.resolved) || payload.resolved.length < 1) {
    throw new Error("Composition lock.payload.resolved must be a non-empty array");
  }
  payload.resolved.forEach(resolvedBundle);
  if (!Array.isArray(payload.edges)) throw new Error("Composition lock.payload.edges must be an array");
  payload.edges.forEach(edge);
  if (!Array.isArray(payload.capabilityProviders)) {
    throw new Error("Composition lock.payload.capabilityProviders must be an array");
  }
  payload.capabilityProviders.forEach(capabilityProvider);
  permissionDiff(payload.permissionDiff);
  migrationDiff(payload.migrationPlan);
  contributionDiff(payload.contributionDiff);
  if (payload.currentInstallationRef !== null) {
    currentInstallationRef(
      payload.currentInstallationRef,
      "Composition lock.payload.currentInstallationRef",
    );
  }
  // Hashes and diffs remain server-owned facts; the browser deliberately does
  // not recompute canonical JSON, dependency resolution, or hash payloads.
  return value as StoredCompositionLock;
}
