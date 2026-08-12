import { describe, expect, it } from "vitest";

import { INTERACTION_HONESTY_MANIFEST } from "./interactionHonestyManifest";

const ONTOLOGY_ROUTES = [
  "/ontology",
  "/workshop/graph",
  "/ontology/funnel",
  "/ontology/okf-funnel",
  "/ontology/okf-overview",
  "/ontology/graph-health",
  "/ontology/wiki",
  "/ontology/wiki-index",
  "/ontology/branches",
] as const;

const AIP_AUTHORITY_ROUTES = ["/aip/memory-governance"] as const;

describe("O1-UX0 · interaction honesty coverage", () => {
  it("registers each ontology digital-twin route exactly once", () => {
    const routes = INTERACTION_HONESTY_MANIFEST.map((entry) => entry.route);
    for (const route of ONTOLOGY_ROUTES) {
      expect(routes.filter((candidate) => candidate === route)).toHaveLength(1);
    }
    for (const route of AIP_AUTHORITY_ROUTES) {
      expect(routes.filter((candidate) => candidate === route)).toHaveLength(1);
    }
    expect(new Set(routes).size).toBe(routes.length);
  });
});
