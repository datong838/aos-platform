import { describe, expect, expectTypeOf, it } from "vitest";

import type {
  ApiErrorBody,
  ApproveInstallationRequest,
  CompositionRequest,
  EmptyInstallationActionRequest,
  InstallationListResponse,
  InstallationResponse,
  StoredCompositionLock,
} from "./types";

const hash = `sha256:${"a".repeat(64)}` as const;
const emptyPermissions = {
  roles: [],
  markings: [],
  dataScopes: [],
  actionTypes: [],
};

const compositionRequest = {
  requested: [{ publisher: "aos", id: "commerce", version: "^1.0.0" }],
  platformApiVersion: "1.0.0",
  platformRelease: "2026.08",
  environment: "dev",
  registrySnapshotHash: null,
  currentInstallationRef: null,
} satisfies CompositionRequest;

const compositionLock = {
  compositionId: "00000000-0000-4000-8000-000000000001",
  revision: 1,
  payload: {
    lockSchemaVersion: "aos.dev/composition-lock/v1alpha1",
    resolverVersion: "aos-resolver/1.0.0",
    request: {
      requested: compositionRequest.requested,
      platformApiVersion: compositionRequest.platformApiVersion,
      platformRelease: compositionRequest.platformRelease,
      environment: compositionRequest.environment,
    },
    registrySnapshotHash: hash,
    resolved: [
      {
        publisher: "aos",
        id: "commerce",
        version: "1.0.0",
        kind: "DomainPack",
        contentHash: hash,
        signatureFingerprint: hash,
        releaseEvidenceRevision: hash,
        dependencies: [],
        optionalDependencies: [],
        conflicts: [],
        capabilities: { provides: [], requires: [] },
        permissions: emptyPermissions,
        migration: { planRef: null, downgradePolicy: "retain-canonical" },
        contributions: [],
        selectionReason: "requested",
      },
    ],
    edges: [],
    capabilityProviders: [],
    permissionDiff: {
      baseline: emptyPermissions,
      target: emptyPermissions,
      added: emptyPermissions,
      removed: emptyPermissions,
      unchanged: emptyPermissions,
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
      target: [],
      added: [],
      removed: [],
      unchanged: [],
    },
    currentInstallationRef: null,
  },
  lockHash: hash,
  permissionDiffHash: hash,
  migrationPlanHash: hash,
  contributionDiffHash: hash,
  createdAt: "2026-08-03T08:00:00Z",
} satisfies StoredCompositionLock;

const installation = {
  installationId: "00000000-0000-4000-8000-000000000002",
  displayName: "Commerce",
  state: "draft",
  currentRevision: 1,
  activeRevision: null,
  previousActiveRevision: null,
  etagVersion: 1,
  createdAt: "2026-08-03T08:00:00Z",
  updatedAt: "2026-08-03T08:00:00Z",
  current: {
    installationId: "00000000-0000-4000-8000-000000000002",
    revision: 1,
    parentRevision: null,
    state: "draft",
    compositionId: compositionLock.compositionId,
    lockRevision: 1,
    lockHash: hash,
    permissionDiffHash: hash,
    migrationPlanHash: hash,
    contributionDiffHash: hash,
    overlayRevision: "overlay-1",
    requestedBy: "maker@example.test",
    decisionId: null,
    createdAt: "2026-08-03T08:00:00Z",
  },
  decision: null,
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
      createdAt: "2026-08-03T08:00:00Z",
    },
  ],
} satisfies InstallationResponse;

describe("asset-control canonical aliases", () => {
  it("preserves the composition lock response shape", () => {
    expect(compositionLock.payload.request).toEqual({
      requested: compositionRequest.requested,
      platformApiVersion: "1.0.0",
      platformRelease: "2026.08",
      environment: "dev",
    });
    expect(compositionLock.payload.permissionDiff.target.dataScopes).toEqual([]);
  });

  it("preserves installation revision and history aliases", () => {
    const response = installation satisfies InstallationResponse;
    const list = {
      items: [response],
      total: 1,
      limit: 50,
      offset: 0,
    } satisfies InstallationListResponse;

    expect(list.items[0].etagVersion).toBe(1);
    expect(response.events[0]).toMatchObject({
      fromRevision: null,
      toRevision: 1,
      fromState: null,
      toState: "draft",
    });
  });

  it("freezes empty, approval and error bodies", () => {
    const empty = {} satisfies EmptyInstallationActionRequest;
    const approval = {
      lockHash: hash,
      permissionDiffHash: hash,
      migrationPlanHash: hash,
      contributionDiffHash: hash,
    } satisfies ApproveInstallationRequest;
    const error = {
      code: "INSTALLATION_CONFLICT",
      message: "installation changed",
      details: { expected: 1, actual: 2 },
      traceId: "trace-1",
    } satisfies ApiErrorBody;

    expect(empty).toEqual({});
    expect(approval.lockHash).toBe(hash);
    expect(error.details).toEqual({ expected: 1, actual: 2 });
    expectTypeOf(error).toMatchTypeOf<ApiErrorBody>();
  });
});
