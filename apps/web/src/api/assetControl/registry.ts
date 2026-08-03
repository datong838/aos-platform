/**
 * M3-0 Registry response contracts.
 *
 * These shapes mirror the dynamic dictionaries returned by
 * asset_bundles.py -> RegistryService -> PostgresRegistryStore. They are
 * intentionally separate from the legacy AssetBundlesPage mock model.
 */

export type RegistryBundleKind =
  | "DomainPack"
  | "SolutionPack"
  | "VerticalPack"
  | "PlatformAdapterPack"
  | "PluginPack";

export type RegistryVersionStatus =
  | "draft"
  | "validated"
  | "published"
  | "deprecated"
  | "revoked"
  | "rejected";

export type RegistryEvidenceStatus =
  | "pending"
  | "valid"
  | "invalid"
  | "expired"
  | "revoked";

export type RegistryEvidenceType =
  | "manifest_validation"
  | "content_hash"
  | "signature_verification"
  | "sbom"
  | "dependency_resolution"
  | "permission_diff"
  | "migration_plan"
  | "preflight"
  | "bundle_evals"
  | "installation_apply"
  | "installation_verify"
  | "rollback"
  | "source_connection"
  | "pipeline_run"
  | "dataset_revision"
  | "data_quality"
  | "ontology_revision"
  | "logic_publication"
  | "logic_eval"
  | "workshop_validation"
  | "action_safety";

export interface RegistrySignature {
  algorithm: "Ed25519";
  keyId: string;
  signature: string;
  signedAt: string;
}

export interface RegistryVersionSummary {
  version: string;
  contentHash: string;
  signature: RegistrySignature | null;
  status: RegistryVersionStatus;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export interface RegistryBundleSummary {
  publisher: string;
  bundleId: string;
  kind: RegistryBundleKind;
  displayName: string;
  createdAt: string;
}

export interface RegistryBundleDetail extends RegistryBundleSummary {
  versions: RegistryVersionSummary[];
}

export interface RegistryManifestDependency {
  id: string;
  version: string;
  // The persisted manifest emits the nullable Pydantic field even when omitted
  // in bundle.yaml.
  publisher: string | null;
}

export interface RegistryManifestConflict {
  id: string;
  version: string | null;
  publisher: string | null;
}

export interface RegistryManifestExports {
  ontology: string[];
  links: string[];
  metrics: string[];
  agents: string[];
  logic: string[];
  workshops: string[];
  evals: string[];
  policies: string[];
  connectors: string[];
  schemas: string[];
  mappings: string[];
  backend: string[];
  ui: string[];
}

export interface RegistryManifest {
  apiVersion: "aos.dev/v1alpha1";
  kind: RegistryBundleKind;
  metadata: {
    id: string;
    version: string;
    displayName: string;
    publisher: string;
    license: string;
  };
  spec: {
    platformApi: string;
    dependencies: RegistryManifestDependency[];
    optionalDependencies: RegistryManifestDependency[];
    conflicts: RegistryManifestConflict[];
    exports: RegistryManifestExports;
    capabilities: { provides: string[]; requires: string[] };
    permissions: {
      roles: string[];
      markings: string[];
      dataScopes: string[];
      actionTypes: string[];
    };
    migrations: {
      plan: string | null;
      downgradePolicy: "retain-canonical";
    };
    preflight: string | null;
    regression: string | null;
    rollback: string | null;
    // Pydantic excludes this field when the list is empty. Contribution claim
    // variants remain server-owned JSON until M3 needs to render them.
    contributions?: Record<string, unknown>[];
  };
}

export interface RegistryVersionDependency {
  publisher: string | null;
  id: string;
  versionRange: string;
  optional: boolean;
  ordinal: number;
}

export interface RegistryArtifact {
  relativePath: string;
  artifactRef: string;
  digest: string;
  size: number;
  mediaType: string;
}

/** Public GET projection deliberately omits artifactRef and metadata. */
export interface RegistryPublicEvidence {
  type: RegistryEvidenceType;
  artifactHash: string;
  status: RegistryEvidenceStatus;
  observedAt: string;
  expiresAt: string | null;
  revokedAt: string | null;
}

/** Public GET projection deliberately omits actor, reason and evidenceSnapshot. */
export interface RegistryPublicLifecycleEvent {
  sequence: number;
  fromStatus: RegistryVersionStatus;
  toStatus: RegistryVersionStatus;
  evidenceRevision: string;
  createdAt: string;
}

export interface RegistryVersionDetail {
  publisher: string;
  bundleId: string;
  kind: RegistryBundleKind;
  displayName: string;
  version: string;
  manifest: RegistryManifest;
  contentHash: string;
  signature: RegistrySignature | null;
  status: RegistryVersionStatus;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  dependencies: RegistryVersionDependency[];
  artifacts: RegistryArtifact[];
  evidence: RegistryPublicEvidence[];
  lifecycleEvents: RegistryPublicLifecycleEvent[];
}

const BUNDLE_KINDS = new Set<RegistryBundleKind>([
  "DomainPack",
  "SolutionPack",
  "VerticalPack",
  "PlatformAdapterPack",
  "PluginPack",
]);
const VERSION_STATUSES = new Set<RegistryVersionStatus>([
  "draft",
  "validated",
  "published",
  "deprecated",
  "revoked",
  "rejected",
]);
const EVIDENCE_STATUSES = new Set<RegistryEvidenceStatus>([
  "pending",
  "valid",
  "invalid",
  "expired",
  "revoked",
]);
const EVIDENCE_TYPES = new Set<RegistryEvidenceType>([
  "manifest_validation", "content_hash", "signature_verification", "sbom",
  "dependency_resolution", "permission_diff", "migration_plan", "preflight",
  "bundle_evals", "installation_apply", "installation_verify", "rollback",
  "source_connection", "pipeline_run", "dataset_revision", "data_quality",
  "ontology_revision", "logic_publication", "logic_eval", "workshop_validation",
  "action_safety",
]);
const SHA256 = /^sha256:[0-9a-f]{64}$/;

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

function exactKeys(
  value: Record<string, unknown>,
  required: readonly string[],
  optional: readonly string[] = [],
  label = "response",
): void {
  const allowed = new Set([...required, ...optional]);
  const missing = required.filter((key) => !(key in value));
  const extra = Object.keys(value).filter((key) => !allowed.has(key));
  if (missing.length || extra.length) {
    throw new Error(`${label} keys mismatch; missing=${missing.join(",")}; extra=${extra.join(",")}`);
  }
}

function string(value: unknown, label: string): asserts value is string {
  if (typeof value !== "string" || value.length === 0) throw new Error(`${label} must be a non-empty string`);
}

function nullableString(value: unknown, label: string): void {
  if (value !== null) string(value, label);
}

function stringArray(value: unknown, label: string): asserts value is string[] {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
  value.forEach((item, index) => string(item, `${label}[${index}]`));
}

function timestamp(value: unknown, label: string): void {
  string(value, label);
  if (!value.includes("T") || Number.isNaN(Date.parse(value))) throw new Error(`${label} must be an ISO timestamp`);
}

function sha256(value: unknown, label: string): void {
  string(value, label);
  if (!SHA256.test(value)) throw new Error(`${label} must be a sha256 digest`);
}

function signature(value: unknown, label: string): void {
  if (value === null) return;
  const item = record(value, label);
  exactKeys(item, ["algorithm", "keyId", "signature", "signedAt"], [], label);
  if (item.algorithm !== "Ed25519") throw new Error(`${label}.algorithm is invalid`);
  string(item.keyId, `${label}.keyId`);
  string(item.signature, `${label}.signature`);
  timestamp(item.signedAt, `${label}.signedAt`);
}

function bundleSummary(value: unknown, detail: boolean): void {
  const item = record(value, "Registry bundle");
  exactKeys(
    item,
    detail
      ? ["publisher", "bundleId", "kind", "displayName", "createdAt", "versions"]
      : ["publisher", "bundleId", "kind", "displayName", "createdAt"],
    [],
    "Registry bundle",
  );
  string(item.publisher, "Registry bundle.publisher");
  string(item.bundleId, "Registry bundle.bundleId");
  if (!BUNDLE_KINDS.has(item.kind as RegistryBundleKind)) throw new Error("Registry bundle.kind is invalid");
  string(item.displayName, "Registry bundle.displayName");
  timestamp(item.createdAt, "Registry bundle.createdAt");
  if (detail) {
    if (!Array.isArray(item.versions)) throw new Error("Registry bundle.versions must be an array");
    item.versions.forEach(versionSummary);
  }
}

function versionSummary(value: unknown, index = 0): void {
  const item = record(value, `Registry version summary[${index}]`);
  exactKeys(item, ["version", "contentHash", "signature", "status", "createdBy", "createdAt", "updatedAt"], [], "Registry version summary");
  string(item.version, "Registry version summary.version");
  sha256(item.contentHash, "Registry version summary.contentHash");
  signature(item.signature, "Registry version summary.signature");
  if (!VERSION_STATUSES.has(item.status as RegistryVersionStatus)) throw new Error("Registry version summary.status is invalid");
  string(item.createdBy, "Registry version summary.createdBy");
  timestamp(item.createdAt, "Registry version summary.createdAt");
  timestamp(item.updatedAt, "Registry version summary.updatedAt");
}

function manifest(value: unknown): void {
  const item = record(value, "Registry manifest");
  exactKeys(item, ["apiVersion", "kind", "metadata", "spec"], [], "Registry manifest");
  if (item.apiVersion !== "aos.dev/v1alpha1") throw new Error("Registry manifest.apiVersion is invalid");
  if (!BUNDLE_KINDS.has(item.kind as RegistryBundleKind)) throw new Error("Registry manifest.kind is invalid");

  const metadata = record(item.metadata, "Registry manifest.metadata");
  exactKeys(metadata, ["id", "version", "displayName", "publisher", "license"], [], "Registry manifest.metadata");
  ["id", "version", "displayName", "publisher", "license"].forEach((key) => string(metadata[key], `Registry manifest.metadata.${key}`));

  const spec = record(item.spec, "Registry manifest.spec");
  exactKeys(spec, ["platformApi", "dependencies", "optionalDependencies", "conflicts", "exports", "capabilities", "permissions", "migrations", "preflight", "regression", "rollback"], ["contributions"], "Registry manifest.spec");
  string(spec.platformApi, "Registry manifest.spec.platformApi");
  for (const key of ["dependencies", "optionalDependencies"] as const) {
    if (!Array.isArray(spec[key])) throw new Error(`Registry manifest.spec.${key} must be an array`);
    spec[key].forEach((raw, index) => {
      const dep = record(raw, `${key}[${index}]`);
      exactKeys(dep, ["id", "version", "publisher"], [], key);
      string(dep.id, `${key}.id`); string(dep.version, `${key}.version`); nullableString(dep.publisher, `${key}.publisher`);
    });
  }
  if (!Array.isArray(spec.conflicts)) throw new Error("Registry manifest.spec.conflicts must be an array");
  spec.conflicts.forEach((raw, index) => {
    const conflict = record(raw, `conflicts[${index}]`);
    exactKeys(conflict, ["id", "version", "publisher"], [], "conflict");
    string(conflict.id, "conflict.id"); nullableString(conflict.version, "conflict.version"); nullableString(conflict.publisher, "conflict.publisher");
  });
  const exports = record(spec.exports, "Registry manifest.spec.exports");
  const exportKeys = ["ontology", "links", "metrics", "agents", "logic", "workshops", "evals", "policies", "connectors", "schemas", "mappings", "backend", "ui"];
  exactKeys(exports, exportKeys, [], "Registry manifest.spec.exports");
  exportKeys.forEach((key) => stringArray(exports[key], `exports.${key}`));
  const capabilities = record(spec.capabilities, "Registry manifest.spec.capabilities");
  exactKeys(capabilities, ["provides", "requires"], [], "capabilities");
  stringArray(capabilities.provides, "capabilities.provides"); stringArray(capabilities.requires, "capabilities.requires");
  const permissions = record(spec.permissions, "Registry manifest.spec.permissions");
  exactKeys(permissions, ["roles", "markings", "dataScopes", "actionTypes"], [], "permissions");
  ["roles", "markings", "dataScopes", "actionTypes"].forEach((key) => stringArray(permissions[key], `permissions.${key}`));
  const migrations = record(spec.migrations, "Registry manifest.spec.migrations");
  exactKeys(migrations, ["plan", "downgradePolicy"], [], "migrations");
  nullableString(migrations.plan, "migrations.plan");
  if (migrations.downgradePolicy !== "retain-canonical") throw new Error("migrations.downgradePolicy is invalid");
  nullableString(spec.preflight, "spec.preflight"); nullableString(spec.regression, "spec.regression"); nullableString(spec.rollback, "spec.rollback");
  if (spec.contributions !== undefined && (!Array.isArray(spec.contributions) || spec.contributions.some((entry) => typeof entry !== "object" || entry === null || Array.isArray(entry)))) {
    throw new Error("Registry manifest.spec.contributions must be an object array");
  }
}

/** Fail-closed parser for GET /v1/asset-bundles (the response is a bare array). */
export function parseRegistryBundleList(value: unknown): RegistryBundleSummary[] {
  if (!Array.isArray(value)) throw new Error("Registry bundle list must be a bare array");
  value.forEach((item) => bundleSummary(item, false));
  return value as RegistryBundleSummary[];
}

/** Fail-closed parser for GET /v1/asset-bundles/{bundleId}. */
export function parseRegistryBundleDetail(value: unknown): RegistryBundleDetail {
  bundleSummary(value, true);
  return value as RegistryBundleDetail;
}

/** Fail-closed parser for the service's public Registry version projection. */
export function parseRegistryVersionDetail(value: unknown): RegistryVersionDetail {
  const item = record(value, "Registry version");
  exactKeys(item, ["publisher", "bundleId", "kind", "displayName", "version", "manifest", "contentHash", "signature", "status", "createdBy", "createdAt", "updatedAt", "dependencies", "artifacts", "evidence", "lifecycleEvents"], [], "Registry version");
  ["publisher", "bundleId", "displayName", "version", "createdBy"].forEach((key) => string(item[key], `Registry version.${key}`));
  if (!BUNDLE_KINDS.has(item.kind as RegistryBundleKind)) throw new Error("Registry version.kind is invalid");
  manifest(item.manifest);
  sha256(item.contentHash, "Registry version.contentHash"); signature(item.signature, "Registry version.signature");
  if (!VERSION_STATUSES.has(item.status as RegistryVersionStatus)) throw new Error("Registry version.status is invalid");
  timestamp(item.createdAt, "Registry version.createdAt"); timestamp(item.updatedAt, "Registry version.updatedAt");

  if (!Array.isArray(item.dependencies)) throw new Error("Registry version.dependencies must be an array");
  item.dependencies.forEach((raw, index) => {
    const dep = record(raw, `Registry version.dependencies[${index}]`);
    exactKeys(dep, ["publisher", "id", "versionRange", "optional", "ordinal"], [], "Registry dependency");
    nullableString(dep.publisher, "Registry dependency.publisher"); string(dep.id, "Registry dependency.id"); string(dep.versionRange, "Registry dependency.versionRange");
    if (typeof dep.optional !== "boolean" || !Number.isInteger(dep.ordinal) || (dep.ordinal as number) < 0) throw new Error("Registry dependency flags are invalid");
  });
  if (!Array.isArray(item.artifacts)) throw new Error("Registry version.artifacts must be an array");
  item.artifacts.forEach((raw) => {
    const artifact = record(raw, "Registry artifact");
    exactKeys(artifact, ["relativePath", "artifactRef", "digest", "size", "mediaType"], [], "Registry artifact");
    string(artifact.relativePath, "Registry artifact.relativePath"); string(artifact.artifactRef, "Registry artifact.artifactRef"); sha256(artifact.digest, "Registry artifact.digest"); string(artifact.mediaType, "Registry artifact.mediaType");
    if (!Number.isInteger(artifact.size) || (artifact.size as number) < 0) throw new Error("Registry artifact.size is invalid");
  });
  if (!Array.isArray(item.evidence)) throw new Error("Registry version.evidence must be an array");
  item.evidence.forEach((raw) => {
    const evidence = record(raw, "Registry public evidence");
    exactKeys(evidence, ["type", "artifactHash", "status", "observedAt", "expiresAt", "revokedAt"], [], "Registry public evidence");
    if (!EVIDENCE_TYPES.has(evidence.type as RegistryEvidenceType)) throw new Error("Registry evidence.type is invalid");
    sha256(evidence.artifactHash, "Registry evidence.artifactHash");
    if (!EVIDENCE_STATUSES.has(evidence.status as RegistryEvidenceStatus)) throw new Error("Registry evidence.status is invalid");
    timestamp(evidence.observedAt, "Registry evidence.observedAt");
    if (evidence.expiresAt !== null) timestamp(evidence.expiresAt, "Registry evidence.expiresAt");
    if (evidence.revokedAt !== null) timestamp(evidence.revokedAt, "Registry evidence.revokedAt");
  });
  if (!Array.isArray(item.lifecycleEvents)) throw new Error("Registry version.lifecycleEvents must be an array");
  item.lifecycleEvents.forEach((raw) => {
    const event = record(raw, "Registry public lifecycle event");
    exactKeys(event, ["sequence", "fromStatus", "toStatus", "evidenceRevision", "createdAt"], [], "Registry public lifecycle event");
    if (!Number.isInteger(event.sequence) || (event.sequence as number) < 1) throw new Error("Registry lifecycle sequence is invalid");
    if (!VERSION_STATUSES.has(event.fromStatus as RegistryVersionStatus) || !VERSION_STATUSES.has(event.toStatus as RegistryVersionStatus)) throw new Error("Registry lifecycle status is invalid");
    sha256(event.evidenceRevision, "Registry lifecycle evidenceRevision"); timestamp(event.createdAt, "Registry lifecycle createdAt");
  });
  return value as RegistryVersionDetail;
}
