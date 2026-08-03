import type {
  CompositionRequest,
  CreateInstallationRequest,
  StoredCompositionLock,
} from "./types";

const HASH = `sha256:${"a".repeat(64)}` as const;

export const COMPOSITION_REQUEST_FIXTURE: CompositionRequest = {
  requested: [{ publisher: "aos", id: "commerce", version: "^1.0.0" }],
  platformApiVersion: "1.0.0",
  platformRelease: "2026.08",
  environment: "dev",
  registrySnapshotHash: null,
  currentInstallationRef: null,
};

export const CREATE_INSTALLATION_REQUEST_FIXTURE: CreateInstallationRequest = {
  compositionId: "00000000-0000-4000-8000-000000000001",
  lockRevision: 1,
  overlayRevision: "overlay-1",
  displayName: "Commerce",
};

const EMPTY_PERMISSIONS = {
  roles: [],
  markings: [],
  dataScopes: [],
  actionTypes: [],
};

const API_CLAIM = {
  kind: "api" as const,
  method: "GET",
  path: "/v1/commerce/orders",
  operationId: "list_commerce_orders",
  mode: "exclusive" as const,
};

const CONTRIBUTION = {
  publisher: "aos",
  id: "commerce",
  version: "1.0.0",
  claim: API_CLAIM,
};

export const STORED_COMPOSITION_LOCK_FIXTURE: StoredCompositionLock = {
  compositionId: CREATE_INSTALLATION_REQUEST_FIXTURE.compositionId,
  revision: 1,
  payload: {
    lockSchemaVersion: "aos.dev/composition-lock/v1alpha1",
    resolverVersion: "aos-resolver/1.0.0",
    request: {
      requested: COMPOSITION_REQUEST_FIXTURE.requested,
      platformApiVersion: COMPOSITION_REQUEST_FIXTURE.platformApiVersion,
      platformRelease: COMPOSITION_REQUEST_FIXTURE.platformRelease,
      environment: COMPOSITION_REQUEST_FIXTURE.environment,
    },
    registrySnapshotHash: HASH,
    resolved: [
      {
        publisher: "aos",
        id: "commerce",
        version: "1.0.0",
        kind: "DomainPack",
        contentHash: HASH,
        signatureFingerprint: HASH,
        releaseEvidenceRevision: HASH,
        dependencies: [],
        optionalDependencies: [],
        conflicts: [],
        capabilities: { provides: ["commerce.orders"], requires: [] },
        permissions: EMPTY_PERMISSIONS,
        migration: { planRef: null, downgradePolicy: "retain-canonical" },
        contributions: [API_CLAIM],
        selectionReason: "requested",
      },
    ],
    edges: [],
    capabilityProviders: [
      {
        capability: "commerce.orders",
        publisher: "aos",
        id: "commerce",
        version: "1.0.0",
      },
    ],
    permissionDiff: {
      baseline: EMPTY_PERMISSIONS,
      target: EMPTY_PERMISSIONS,
      added: EMPTY_PERMISSIONS,
      removed: EMPTY_PERMISSIONS,
      unchanged: EMPTY_PERMISSIONS,
    },
    migrationPlan: {
      baseline: [],
      target: [],
      added: [],
      removed: [],
      changed: [],
    },
    contributionDiff: {
      baseline: [],
      target: [CONTRIBUTION],
      added: [CONTRIBUTION],
      removed: [],
      unchanged: [],
    },
    currentInstallationRef: null,
  },
  lockHash: HASH,
  permissionDiffHash: HASH,
  migrationPlanHash: HASH,
  contributionDiffHash: HASH,
  createdAt: "2026-08-03T08:00:00+00:00",
};
