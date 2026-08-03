import { describe, expect, it } from "vitest";

import {
  COMPOSITION_REQUEST_FIXTURE,
  CREATE_INSTALLATION_REQUEST_FIXTURE,
  STORED_COMPOSITION_LOCK_FIXTURE,
} from "./compositionFixtures";
import {
  parseStoredCompositionLock,
  serializeCompositionRequest,
  serializeCreateInstallationRequest,
} from "./compositions";

describe("M3-3 composition contracts", () => {
  it("serializes only the exact resolve and create request aliases", () => {
    expect(serializeCompositionRequest(COMPOSITION_REQUEST_FIXTURE)).toEqual(
      COMPOSITION_REQUEST_FIXTURE,
    );
    expect(
      serializeCreateInstallationRequest(CREATE_INSTALLATION_REQUEST_FIXTURE),
    ).toEqual(CREATE_INSTALLATION_REQUEST_FIXTURE);
  });

  it("rejects unknown, snake_case and injected request fields", () => {
    expect(() =>
      serializeCompositionRequest({
        ...COMPOSITION_REQUEST_FIXTURE,
        platform_api_version: "1.0.0",
      }),
    ).toThrow("extra=platform_api_version");
    expect(() =>
      serializeCompositionRequest({
        ...COMPOSITION_REQUEST_FIXTURE,
        orgId: "org-injected",
      }),
    ).toThrow("extra=orgId");
    expect(() =>
      serializeCreateInstallationRequest({
        ...CREATE_INSTALLATION_REQUEST_FIXTURE,
        requestedBy: "actor-injected",
      }),
    ).toThrow("extra=requestedBy");
  });

  it("rejects invalid basic request structure without implementing semver", () => {
    expect(() =>
      serializeCompositionRequest({
        ...COMPOSITION_REQUEST_FIXTURE,
        requested: [],
      }),
    ).toThrow("1-64");

    const duplicate = COMPOSITION_REQUEST_FIXTURE.requested[0];
    expect(() =>
      serializeCompositionRequest({
        ...COMPOSITION_REQUEST_FIXTURE,
        requested: [duplicate, { ...duplicate, version: "2.x" }],
      }),
    ).toThrow("coordinates must be unique");

    expect(() =>
      serializeCreateInstallationRequest({
        ...CREATE_INSTALLATION_REQUEST_FIXTURE,
        compositionId: "not-a-uuid",
      }),
    ).toThrow("compositionId is invalid");
  });

  it("accepts the canonical stored lock without cloning or recomputing hashes", () => {
    expect(parseStoredCompositionLock(STORED_COMPOSITION_LOCK_FIXTURE)).toBe(
      STORED_COMPOSITION_LOCK_FIXTURE,
    );
    expect(STORED_COMPOSITION_LOCK_FIXTURE.payload.contributionDiff.added).toHaveLength(1);
  });

  it("fails closed on top-level and nested schema drift", () => {
    const missing = structuredClone(STORED_COMPOSITION_LOCK_FIXTURE) as unknown as Record<
      string,
      unknown
    >;
    delete missing.permissionDiffHash;
    expect(() => parseStoredCompositionLock(missing)).toThrow(
      "missing=permissionDiffHash",
    );

    const injected = structuredClone(STORED_COMPOSITION_LOCK_FIXTURE) as unknown as {
      payload: Record<string, unknown>;
    };
    injected.payload.tenantId = "tenant-private";
    expect(() => parseStoredCompositionLock(injected)).toThrow("extra=tenantId");
  });

  it("rejects illegal UUID, hash, enum and timezone values", () => {
    const badUuid = structuredClone(STORED_COMPOSITION_LOCK_FIXTURE);
    badUuid.compositionId = "NOT-A-UUID";
    expect(() => parseStoredCompositionLock(badUuid)).toThrow(
      "compositionId is invalid",
    );

    const badHash = structuredClone(STORED_COMPOSITION_LOCK_FIXTURE);
    badHash.lockHash = "sha256:not-canonical";
    expect(() => parseStoredCompositionLock(badHash)).toThrow("lockHash is invalid");

    const badKind = structuredClone(STORED_COMPOSITION_LOCK_FIXTURE) as unknown as {
      payload: { resolved: Array<Record<string, unknown>> };
    };
    badKind.payload.resolved[0].kind = "LegacyPack";
    expect(() => parseStoredCompositionLock(badKind)).toThrow("kind is invalid");

    const badTime = structuredClone(STORED_COMPOSITION_LOCK_FIXTURE);
    badTime.createdAt = "2026-08-03T08:00:00";
    expect(() => parseStoredCompositionLock(badTime)).toThrow("with timezone");
  });
});
