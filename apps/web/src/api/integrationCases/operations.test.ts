import { describe, expect, it } from "vitest";
import { INTEGRATION_CASE_HEADER_CONTRACT, INTEGRATION_CASE_OPERATIONS } from "./operations";

describe("M4-0 integration case operation contract", () => {
  it("freezes exactly the five canonical endpoints and operationIds", () => {
    expect(Object.values(INTEGRATION_CASE_OPERATIONS)).toHaveLength(5);
    expect(Object.values(INTEGRATION_CASE_OPERATIONS).map(({ operationId }) => operationId)).toEqual([
      "list_integration_cases",
      "create_integration_case",
      "get_integration_case",
      "create_integration_evidence_snapshot",
      "list_integration_case_timeline",
    ]);
  });

  it("requires idempotency and CAS only where the frozen contract requires them", () => {
    expect(INTEGRATION_CASE_OPERATIONS.createCase).toMatchObject({ requiresIdempotencyKey: true, requiresIfMatch: false, returnsEtag: true });
    expect(INTEGRATION_CASE_OPERATIONS.createSnapshot).toMatchObject({ requiresIdempotencyKey: true, requiresIfMatch: true, returnsEtag: true });
    expect(INTEGRATION_CASE_OPERATIONS.getCase.returnsEtag).toBe(true);
    expect(INTEGRATION_CASE_HEADER_CONTRACT.ifMatch.pattern).toBe('^"[1-9][0-9]*"$');
  });

  it("includes evidence integrity and validation status surfaces without inventing endpoints", () => {
    expect(INTEGRATION_CASE_OPERATIONS.createSnapshot.errorStatuses).toEqual([400, 401, 403, 404, 409, 422, 428, 500]);
    expect(Object.values(INTEGRATION_CASE_OPERATIONS).every(({ pathTemplate }) => pathTemplate.startsWith("/v1/integration-cases"))).toBe(true);
  });
});
