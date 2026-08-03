import type {
  RegistryBundleDetail,
  RegistryBundleSummary,
  RegistryVersionDetail,
} from "./registry";

const CONTENT_HASH = `sha256:${"c".repeat(64)}`;
const ARTIFACT_HASH = `sha256:${"a".repeat(64)}`;
const EVIDENCE_HASH = `sha256:${"b".repeat(64)}`;
const EVIDENCE_REVISION = `sha256:${"e".repeat(64)}`;

const SIGNATURE = {
  algorithm: "Ed25519" as const,
  keyId: "test-key",
  signature: "base64-signature",
  signedAt: "2026-08-03T12:00:00+00:00",
};

const VERSION_SUMMARY = {
  version: "1.0.0",
  contentHash: CONTENT_HASH,
  signature: SIGNATURE,
  status: "published" as const,
  createdBy: "publisher:test",
  createdAt: "2026-08-03T12:00:00+00:00",
  updatedAt: "2026-08-03T12:02:00+00:00",
};

export const REGISTRY_BUNDLE_LIST_FIXTURE: RegistryBundleSummary[] = [
  {
    publisher: "aos",
    bundleId: "solution.example",
    kind: "SolutionPack",
    displayName: "Example Solution",
    createdAt: "2026-08-03T12:00:00+00:00",
  },
];

export const REGISTRY_BUNDLE_DETAIL_FIXTURE: RegistryBundleDetail = {
  ...REGISTRY_BUNDLE_LIST_FIXTURE[0],
  versions: [VERSION_SUMMARY],
};

/**
 * Mirrors GET /v1/asset-bundles/{bundleId}/versions/{version} after
 * RegistryService._public_version_projection has removed internal audit data.
 */
export const REGISTRY_VERSION_DETAIL_FIXTURE: RegistryVersionDetail = {
  publisher: "aos",
  bundleId: "solution.example",
  kind: "SolutionPack",
  displayName: "Example Solution",
  version: "1.0.0",
  manifest: {
    apiVersion: "aos.dev/v1alpha1",
    kind: "SolutionPack",
    metadata: {
      id: "solution.example",
      version: "1.0.0",
      displayName: "Example Solution",
      publisher: "aos",
      license: "internal",
    },
    spec: {
      platformApi: ">=1.7.0 <2.0.0",
      dependencies: [
        { id: "domain.orders", version: ">=1.0.0 <2.0.0", publisher: null },
      ],
      optionalDependencies: [
        { id: "plugin.insights", version: "^1.1.0", publisher: "partner" },
      ],
      conflicts: [],
      exports: {
        ontology: [], links: [], metrics: [], agents: [], logic: [], workshops: [],
        evals: [], policies: [], connectors: [], schemas: [], mappings: [], backend: [], ui: [],
      },
      capabilities: { provides: [], requires: [] },
      permissions: { roles: [], markings: [], dataScopes: [], actionTypes: [] },
      migrations: { plan: null, downgradePolicy: "retain-canonical" },
      preflight: null,
      regression: null,
      rollback: null,
    },
  },
  contentHash: CONTENT_HASH,
  signature: SIGNATURE,
  status: "published",
  createdBy: "publisher:test",
  createdAt: "2026-08-03T12:00:00+00:00",
  updatedAt: "2026-08-03T12:02:00+00:00",
  dependencies: [
    { publisher: null, id: "domain.orders", versionRange: ">=1.0.0 <2.0.0", optional: false, ordinal: 0 },
    { publisher: "partner", id: "plugin.insights", versionRange: "^1.1.0", optional: true, ordinal: 0 },
  ],
  artifacts: [
    {
      relativePath: "bundle.yaml",
      artifactRef: "bundle://fixtures/aos/solution.example/bundle.yaml",
      digest: ARTIFACT_HASH,
      size: 128,
      mediaType: "application/yaml",
    },
  ],
  evidence: [
    {
      type: "manifest_validation",
      artifactHash: EVIDENCE_HASH,
      status: "valid",
      observedAt: "2026-08-03T12:00:00+00:00",
      expiresAt: "2026-08-03T13:00:00+00:00",
      revokedAt: null,
    },
  ],
  lifecycleEvents: [
    {
      sequence: 1,
      fromStatus: "draft",
      toStatus: "validated",
      evidenceRevision: EVIDENCE_REVISION,
      createdAt: "2026-08-03T12:01:00+00:00",
    },
    {
      sequence: 2,
      fromStatus: "validated",
      toStatus: "published",
      evidenceRevision: EVIDENCE_REVISION,
      createdAt: "2026-08-03T12:02:00+00:00",
    },
  ],
};
