import { describe, expect, it } from "vitest";

import { STORED_COMPOSITION_LOCK_FIXTURE } from "./compositionFixtures";
import { INSTALLATION_ACTION_FIXTURES, INSTALLATION_SUBMITTED_FIXTURE } from "./installationActionFixtures";
import {
  buildApproveInstallationRequest,
  serializeApproveInstallationRequest,
  serializeEmptyInstallationAction,
  serializeRejectInstallationRequest,
  serializeRollbackInstallationRequest,
} from "./installationActions";
import { parseInstallationDetail } from "./installations";

describe("installation action contracts", () => {
  it("parses complete lifecycle response fixtures fail-closed", () => {
    expect(INSTALLATION_ACTION_FIXTURES.map((fixture) => parseInstallationDetail(fixture).state)).toEqual([
      "submitted", "approved", "rejected", "applied", "active", "rolled_back",
    ]);
  });

  it("serializes empty actions and reasons exactly", () => {
    expect(serializeEmptyInstallationAction()).toEqual({});
    expect(() => serializeEmptyInstallationAction({ evidence: [] })).toThrow(TypeError);
    expect(serializeRejectInstallationRequest({ reason: "policy mismatch" })).toEqual({ reason: "policy mismatch" });
    expect(serializeRollbackInstallationRequest({ reason: "operator rollback" })).toEqual({ reason: "operator rollback" });
    for (const invalid of ["", " padded", "padded ", "bad\u0000reason", "bad\u001freason", "bad\u0085reason", "x".repeat(2_001)]) {
      expect(() => serializeRejectInstallationRequest({ reason: invalid })).toThrow(TypeError);
      expect(() => serializeRollbackInstallationRequest({ reason: invalid })).toThrow(TypeError);
    }
  });

  it("builds approval from matching server installation and lock hashes without recomputing", () => {
    expect(buildApproveInstallationRequest(INSTALLATION_SUBMITTED_FIXTURE, STORED_COMPOSITION_LOCK_FIXTURE)).toEqual({
      lockHash: STORED_COMPOSITION_LOCK_FIXTURE.lockHash,
      permissionDiffHash: STORED_COMPOSITION_LOCK_FIXTURE.permissionDiffHash,
      migrationPlanHash: STORED_COMPOSITION_LOCK_FIXTURE.migrationPlanHash,
      contributionDiffHash: STORED_COMPOSITION_LOCK_FIXTURE.contributionDiffHash,
    });
    expect(() => buildApproveInstallationRequest(
      { ...INSTALLATION_SUBMITTED_FIXTURE, current: { ...INSTALLATION_SUBMITTED_FIXTURE.current, lockHash: `sha256:${"f".repeat(64)}` } },
      STORED_COMPOSITION_LOCK_FIXTURE,
    )).toThrow(/lockHash/);
  });

  it("rejects non-exact approval bodies", () => {
    const valid = buildApproveInstallationRequest(INSTALLATION_SUBMITTED_FIXTURE, STORED_COMPOSITION_LOCK_FIXTURE);
    expect(serializeApproveInstallationRequest(valid)).toEqual(valid);
    expect(() => serializeApproveInstallationRequest({ ...valid, actor: "reviewer" })).toThrow(TypeError);
    expect(() => serializeApproveInstallationRequest({ ...valid, lockHash: "sha256:short" })).toThrow(TypeError);
  });
});
