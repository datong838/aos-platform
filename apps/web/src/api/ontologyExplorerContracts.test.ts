import { describe, expect, it } from "vitest";

import {
  ONTOLOGY_EXPLORER_ERROR_CODES,
  hasKnownGraphMetadata,
  isEdgeAuthority,
  isGraphDomain,
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

describe("O1-UA1 · common ontology contract guards", () => {
  it("accepts only frozen graph domains and edge authorities", () => {
    expect(isGraphDomain("domain")).toBe(true);
    expect(isGraphDomain("operational_lineage")).toBe(true);
    expect(isGraphDomain("business-ish")).toBe(false);
    expect(isEdgeAuthority("authoritative")).toBe(true);
    expect(isEdgeAuthority("inferred")).toBe(true);
    expect(isEdgeAuthority("compat_projection")).toBe(true);
    expect(isEdgeAuthority("trusted_by_client")).toBe(false);
  });

  it("fails closed when graph metadata is absent or unknown", () => {
    expect(hasKnownGraphMetadata({ graphDomain: "domain", edgeAuthority: "authoritative" })).toBe(true);
    expect(hasKnownGraphMetadata({ graphDomain: "domain", edgeAuthority: "inferred" })).toBe(true);
    expect(hasKnownGraphMetadata({ graphDomain: "domain" })).toBe(false);
    expect(hasKnownGraphMetadata({ graphDomain: "unknown", edgeAuthority: "authoritative" })).toBe(false);
  });
});
