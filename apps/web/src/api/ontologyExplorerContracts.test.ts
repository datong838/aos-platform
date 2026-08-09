import { describe, expect, it } from "vitest";

import {
  ONTOLOGY_EXPLORER_ERROR_CODES,
  isOntologyExplorerErrorCode,
} from "./ontologyExplorerContracts";

describe("O1-UX0 · ontology explorer contracts", () => {
  it("freezes the public error-code set", () => {
    expect(ONTOLOGY_EXPLORER_ERROR_CODES).toEqual([
      "TENANT_SCOPE_REQUIRED",
      "TENANT_SCOPE_FORBIDDEN",
      "EXPLORATION_SHARE_FORBIDDEN",
      "EXPLORATION_NOT_FOUND",
      "IDEMPOTENCY_CONFLICT",
      "OBJECT_REFERENCE_UNSTABLE",
      "REVISION_CONFLICT",
      "GRAPH_QUERY_TOO_LARGE",
      "GRAPH_QUERY_INVALID",
      "OBJECT_SET_TYPE_MISMATCH",
      "GRAPH_QUERY_RATE_LIMITED",
      "GRAPH_AUTHORITY_UNAVAILABLE",
      "EXPLORATION_ARCHIVE_REQUIRED",
    ]);
  });

  it("recognizes only frozen error codes", () => {
    expect(isOntologyExplorerErrorCode("REVISION_CONFLICT")).toBe(true);
    expect(isOntologyExplorerErrorCode("UNKNOWN")).toBe(false);
  });
});

