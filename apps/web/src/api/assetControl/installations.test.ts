import { describe, expect, it } from "vitest";

import {
  INSTALLATION_DETAIL_FIXTURE,
  INSTALLATION_LIST_FIXTURE,
} from "./installationFixtures";
import { parseInstallationDetail, parseInstallationList } from "./installations";

describe("M3-2 installation read contracts", () => {
  it("accepts the canonical list envelope and current detail", () => {
    expect(parseInstallationList(INSTALLATION_LIST_FIXTURE)).toBe(
      INSTALLATION_LIST_FIXTURE,
    );
    expect(parseInstallationDetail(INSTALLATION_DETAIL_FIXTURE)).toBe(
      INSTALLATION_DETAIL_FIXTURE,
    );
    expect(INSTALLATION_DETAIL_FIXTURE.events).toHaveLength(
      INSTALLATION_DETAIL_FIXTURE.currentRevision,
    );
    expect("revisions" in INSTALLATION_DETAIL_FIXTURE).toBe(false);
  });

  it("rejects a bare list, unknown fields and invalid pagination", () => {
    expect(() => parseInstallationList(INSTALLATION_LIST_FIXTURE.items)).toThrow(
      "must be an object",
    );

    const leaked = structuredClone(INSTALLATION_LIST_FIXTURE) as unknown as Record<
      string,
      unknown
    >;
    leaked.internalTenantId = "tenant-private";
    expect(() => parseInstallationList(leaked)).toThrow("extra=internalTenantId");

    const invalidPage = structuredClone(INSTALLATION_LIST_FIXTURE);
    invalidPage.limit = 101;
    expect(() => parseInstallationList(invalidPage)).toThrow("limit must be <= 100");
  });

  it("rejects illegal states, pointers, etag versions and timestamps", () => {
    const badState = structuredClone(INSTALLATION_LIST_FIXTURE) as unknown as {
      items: Array<Record<string, unknown>>;
    };
    badState.items[0].state = "failed";
    expect(() => parseInstallationList(badState)).toThrow("state is invalid");

    const badPointers = structuredClone(INSTALLATION_LIST_FIXTURE);
    badPointers.items[0].activeRevision = 4;
    expect(() => parseInstallationList(badPointers)).toThrow(
      "activeRevision must equal currentRevision",
    );

    const badEtag = structuredClone(INSTALLATION_LIST_FIXTURE);
    badEtag.items[0].etagVersion = 4;
    expect(() => parseInstallationList(badEtag)).toThrow(
      "etagVersion must equal currentRevision",
    );

    const badTime = structuredClone(INSTALLATION_LIST_FIXTURE);
    badTime.items[0].updatedAt = "2026-08-03T08:04:00";
    expect(() => parseInstallationList(badTime)).toThrow("with timezone");
  });

  it("rejects malformed current revisions, hashes and evidence enums", () => {
    const badParent = structuredClone(INSTALLATION_DETAIL_FIXTURE);
    badParent.current.parentRevision = 3;
    expect(() => parseInstallationDetail(badParent)).toThrow(
      "parentRevision must identify the previous revision",
    );

    const badHash = structuredClone(INSTALLATION_DETAIL_FIXTURE) as unknown as {
      current: Record<string, unknown>;
    };
    badHash.current.lockHash = "sha1:not-canonical";
    expect(() => parseInstallationDetail(badHash)).toThrow("sha256 digest");

    const badEvidence = structuredClone(INSTALLATION_DETAIL_FIXTURE) as unknown as {
      events: Array<{ evidence: Record<string, unknown> | null }>;
    };
    badEvidence.events[3].evidence!.type = "client_attestation";
    expect(() => parseInstallationDetail(badEvidence)).toThrow(
      "evidence.type is invalid",
    );
  });

  it("rejects broken event continuity and a mismatched decision", () => {
    const brokenHistory = structuredClone(INSTALLATION_DETAIL_FIXTURE);
    brokenHistory.events[3].fromRevision = 2;
    expect(() => parseInstallationDetail(brokenHistory)).toThrow(
      "event history is not continuous",
    );

    const wrongDecision = structuredClone(INSTALLATION_DETAIL_FIXTURE);
    wrongDecision.decision!.actor = wrongDecision.current.requestedBy;
    expect(() => parseInstallationDetail(wrongDecision)).toThrow(
      "decision identity is inconsistent",
    );
  });
});
