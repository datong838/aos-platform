import { describe, expect, it } from "vitest";
import {
  parseRegistryBundleDetail,
  parseRegistryBundleList,
  parseRegistryVersionDetail,
} from "./registry";
import {
  REGISTRY_BUNDLE_DETAIL_FIXTURE,
  REGISTRY_BUNDLE_LIST_FIXTURE,
  REGISTRY_VERSION_DETAIL_FIXTURE,
} from "./registryFixtures";

describe("M3-0 Registry response contracts", () => {
  it("accepts the bare list and bundle detail emitted by PostgresRegistryStore", () => {
    expect(parseRegistryBundleList(REGISTRY_BUNDLE_LIST_FIXTURE)).toBe(
      REGISTRY_BUNDLE_LIST_FIXTURE,
    );
    expect(parseRegistryBundleDetail(REGISTRY_BUNDLE_DETAIL_FIXTURE)).toBe(
      REGISTRY_BUNDLE_DETAIL_FIXTURE,
    );
    expect(REGISTRY_BUNDLE_DETAIL_FIXTURE.versions[0]).toMatchObject({
      status: "published",
      signature: { algorithm: "Ed25519" },
    });
  });

  it("accepts the public version projection with nullable publisher and dates", () => {
    const parsed = parseRegistryVersionDetail(REGISTRY_VERSION_DETAIL_FIXTURE);
    expect(parsed.dependencies[0].publisher).toBeNull();
    expect(parsed.evidence[0].revokedAt).toBeNull();
    expect(parsed.manifest.spec.contributions).toBeUndefined();
    expect(parsed.lifecycleEvents.map((event) => event.toStatus)).toEqual([
      "validated",
      "published",
    ]);
  });

  it("does not confuse the Registry bare array with an items envelope", () => {
    expect(() =>
      parseRegistryBundleList({ items: REGISTRY_BUNDLE_LIST_FIXTURE }),
    ).toThrow("bare array");
  });

  it("rejects the legacy page Mock shape", () => {
    expect(() =>
      parseRegistryBundleList([
        {
          id: "asset-apollo-core-2.14.1",
          name: "apollo-core",
          version: "2.14.1",
          channel: "stable",
          status: "published",
        },
      ]),
    ).toThrow("keys mismatch");
  });

  it("fails closed when a required dynamic dictionary field drifts", () => {
    const drifted = structuredClone(REGISTRY_VERSION_DETAIL_FIXTURE) as unknown as Record<string, unknown>;
    delete drifted.contentHash;
    expect(() => parseRegistryVersionDetail(drifted)).toThrow(
      /missing=contentHash/,
    );
  });

  it("rejects internal audit fields that the public GET projection removes", () => {
    const leaked = structuredClone(REGISTRY_VERSION_DETAIL_FIXTURE) as unknown as {
      evidence: Array<Record<string, unknown>>;
      lifecycleEvents: Array<Record<string, unknown>>;
    };
    leaked.evidence[0].artifactRef = "bundle://private/evidence.json";
    leaked.lifecycleEvents[0].actor = "validator:test";
    expect(() => parseRegistryVersionDetail(leaked)).toThrow(/extra=artifactRef/);
  });

  it("rejects unknown status and non-sha256 content hashes", () => {
    const badStatus = structuredClone(REGISTRY_BUNDLE_DETAIL_FIXTURE) as unknown as {
      versions: Array<Record<string, unknown>>;
    };
    badStatus.versions[0].status = "stable";
    expect(() => parseRegistryBundleDetail(badStatus)).toThrow(/status is invalid/);

    const badHash = structuredClone(REGISTRY_VERSION_DETAIL_FIXTURE) as unknown as Record<string, unknown>;
    badHash.contentHash = "sha1:not-canonical";
    expect(() => parseRegistryVersionDetail(badHash)).toThrow(/sha256 digest/);
  });
});
