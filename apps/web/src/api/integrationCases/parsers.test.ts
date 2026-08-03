import { describe, expect, it } from "vitest";
import {
  parseCreateIntegrationCaseRequest,
  parseCreateIntegrationEvidenceSnapshotRequest,
  parseIntegrationCaseDetail,
  parseIntegrationCaseList,
  parseIntegrationCaseTimeline,
  parseIntegrationEvidenceSnapshot,
} from "./parsers";
import {
  CURRENT_CASE_DETAIL_FIXTURE,
  CURRENT_CASE_LIST_FIXTURE,
  REFERENCE_CASE_DETAIL_FIXTURE,
  REFERENCE_CASE_LIST_FIXTURE,
  SNAPSHOT_FIXTURE,
  TIMELINE_FIXTURE,
} from "./fixtures";
import { INTEGRATION_CASE_STAGES } from "./types";

function clone(value: unknown): Record<string, unknown> {
  return structuredClone(value) as Record<string, unknown>;
}

describe("M4-0 integration case strict response contracts", () => {
  it("accepts current list/detail and preserves measured zero separately from unavailable", () => {
    const list = parseIntegrationCaseList(CURRENT_CASE_LIST_FIXTURE);
    expect(list.stats?.datasetRowCount.value).toBe(0);
    expect(list.stats?.pipelineCount.value).toBeNull();
    expect(parseIntegrationCaseDetail(CURRENT_CASE_DETAIL_FIXTURE)).toBe(CURRENT_CASE_DETAIL_FIXTURE);
  });

  it("accepts anonymized references only with null tenant bindings and no statistics", () => {
    expect(parseIntegrationCaseList(REFERENCE_CASE_LIST_FIXTURE)).toBe(REFERENCE_CASE_LIST_FIXTURE);
    expect(parseIntegrationCaseDetail(REFERENCE_CASE_DETAIL_FIXTURE)).toBe(REFERENCE_CASE_DETAIL_FIXTURE);
  });

  it("freezes all eight server-owned stages", () => {
    expect(INTEGRATION_CASE_STAGES).toEqual([
      "planned", "connection_verified", "data_verified", "ontology_verified",
      "logic_verified", "workshop_verified", "production_ready", "production_active",
    ]);
  });

  it("accepts immutable snapshot and timeline responses", () => {
    expect(parseIntegrationEvidenceSnapshot(SNAPSHOT_FIXTURE)).toBe(SNAPSHOT_FIXTURE);
    expect(parseIntegrationCaseTimeline(TIMELINE_FIXTURE)).toBe(TIMELINE_FIXTURE);
  });

  it("rejects unknown, missing, extra and snake_case response fields", () => {
    const unknownStage = clone(CURRENT_CASE_LIST_FIXTURE) as { items: Array<Record<string, unknown>> };
    unknownStage.items[0].computedStage = "live";
    expect(() => parseIntegrationCaseList(unknownStage)).toThrow(/computedStage is invalid/);

    const missing = clone(CURRENT_CASE_LIST_FIXTURE);
    delete missing.total;
    expect(() => parseIntegrationCaseList(missing)).toThrow(/missing=total/);

    const extra = clone(CURRENT_CASE_DETAIL_FIXTURE);
    extra.rawClaims = {};
    expect(() => parseIntegrationCaseDetail(extra)).toThrow(/extra=rawClaims/);

    const snake = clone(SNAPSHOT_FIXTURE);
    snake.snapshot_revision = snake.snapshotRevision;
    delete snake.snapshotRevision;
    expect(() => parseIntegrationEvidenceSnapshot(snake)).toThrow(/snapshotRevision/);
  });

  it("rejects current/reference mixing and reference identity or metric leakage", () => {
    const mixed = clone(CURRENT_CASE_LIST_FIXTURE) as { items: Array<Record<string, unknown>> };
    mixed.items[0].scope = "reference";
    expect(() => parseIntegrationCaseList(mixed)).toThrow(/reference identity fields must be null/);

    const leakedOwner = clone(REFERENCE_CASE_LIST_FIXTURE) as { items: Array<Record<string, unknown>> };
    leakedOwner.items[0].owner = "source-tenant@example.test";
    expect(() => parseIntegrationCaseList(leakedOwner)).toThrow(/reference identity fields must be null/);

    const leakedStats = clone(REFERENCE_CASE_LIST_FIXTURE);
    leakedStats.stats = CURRENT_CASE_LIST_FIXTURE.stats;
    expect(() => parseIntegrationCaseList(leakedStats)).toThrow(/stats must be null/);
  });

  it("rejects coercion, unsafe numeric values, invalid UUID/hash and naive timestamps", () => {
    const coercion = clone(CURRENT_CASE_LIST_FIXTURE);
    coercion.total = "1";
    expect(() => parseIntegrationCaseList(coercion)).toThrow(/non-negative safe integer/);

    const badUuid = clone(CURRENT_CASE_DETAIL_FIXTURE);
    badUuid.caseId = "NOT-A-UUID";
    expect(() => parseIntegrationCaseDetail(badUuid)).toThrow(/canonical lowercase UUID/);

    const badHash = clone(SNAPSHOT_FIXTURE);
    badHash.snapshotHash = "sha1:abc";
    expect(() => parseIntegrationEvidenceSnapshot(badHash)).toThrow(/sha256 digest/);

    const naiveTime = clone(TIMELINE_FIXTURE) as { items: Array<Record<string, unknown>> };
    naiveTime.items[0].createdAt = "2026-08-03T09:00:00";
    expect(() => parseIntegrationCaseTimeline(naiveTime)).toThrow(/timestamp with timezone/);
  });

  it("rejects null-to-zero ambiguity and impossible metric coverage", () => {
    const nullWithMeasurement = clone(CURRENT_CASE_LIST_FIXTURE) as {
      stats: { pipelineCount: Record<string, unknown> };
    };
    nullWithMeasurement.stats.pipelineCount.measuredCaseCount = 1;
    expect(() => parseIntegrationCaseList(nullWithMeasurement)).toThrow(/null value requires zero/);

    const impossible = clone(CURRENT_CASE_LIST_FIXTURE) as {
      stats: { datasetRowCount: Record<string, unknown> };
    };
    impossible.stats.datasetRowCount.measuredCaseCount = 2;
    expect(() => parseIntegrationCaseList(impossible)).toThrow(/exceeds eligibleCaseCount/);
  });

  it("rejects leaked raw evidence data and inconsistent revoke semantics", () => {
    const leaked = clone(CURRENT_CASE_DETAIL_FIXTURE) as { latestEvidence: Array<Record<string, unknown>> };
    leaked.latestEvidence[0].claims = { authMode: "secret" };
    expect(() => parseIntegrationCaseDetail(leaked)).toThrow(/extra=claims/);

    const revoked = clone(CURRENT_CASE_DETAIL_FIXTURE) as { latestEvidence: Array<Record<string, unknown>> };
    revoked.latestEvidence[0].outcome = "revoked";
    expect(() => parseIntegrationCaseDetail(revoked)).toThrow(/revokedAt is inconsistent/);

    const unknownType = clone(CURRENT_CASE_DETAIL_FIXTURE) as { latestEvidence: Array<Record<string, unknown>> };
    unknownType.latestEvidence[0].evidenceType = "free_form_claim";
    expect(() => parseIntegrationCaseDetail(unknownType)).toThrow(/evidenceType is invalid/);
  });

  it("rejects non-changing or non-monotonic timeline events", () => {
    const unchanged = clone(TIMELINE_FIXTURE) as { items: Array<Record<string, unknown>> };
    unchanged.items[0].newStage = "planned";
    expect(() => parseIntegrationCaseTimeline(unchanged)).toThrow(/must change stage/);

    const duplicate = clone(TIMELINE_FIXTURE) as { items: Array<Record<string, unknown>>; total: number };
    duplicate.items.push({ ...duplicate.items[0] });
    duplicate.total = 2;
    expect(() => parseIntegrationCaseTimeline(duplicate)).toThrow(/sequence must increase/);
  });
});

describe("M4-0 integration case write body boundaries", () => {
  it("accepts only the three frozen create fields and an empty snapshot body", () => {
    expect(parseCreateIntegrationCaseRequest({
      installationId: "00000000-0000-4000-8000-000000000103",
      overlayRevision: "overlay-7",
      displayName: "Commerce case",
    })).toEqual({
      installationId: "00000000-0000-4000-8000-000000000103",
      overlayRevision: "overlay-7",
      displayName: "Commerce case",
    });
    expect(parseCreateIntegrationEvidenceSnapshotRequest({})).toEqual({});
  });

  it.each(["caseId", "stage", "evidence", "cutoffAt", "metrics", "producer", "scope", "owner", "requiredMarkings"])(
    "rejects client injection through %s",
    (field) => {
      const request: Record<string, unknown> = {
        installationId: "00000000-0000-4000-8000-000000000103",
        overlayRevision: "overlay-7",
        displayName: "Commerce case",
        [field]: "injected",
      };
      expect(() => parseCreateIntegrationCaseRequest(request)).toThrow(/extra=/);
    },
  );

  it("rejects every non-empty snapshot body", () => {
    expect(() => parseCreateIntegrationEvidenceSnapshotRequest({ cutoffAt: "2026-08-03T09:00:00Z" })).toThrow(/extra=cutoffAt/);
    expect(() => parseCreateIntegrationEvidenceSnapshotRequest([])).toThrow(/must be an object/);
  });
});
