import { describe, expect, it } from "vitest";

import { INTERACTION_HONESTY_MANIFEST } from "./interactionHonestyManifest";
import { NAV_ITEMS } from "./navigation/items";

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

const AIP_AUTHORITY_ROUTES = ["/aip/memory-governance", "/aip/assist", "/aip/analyst"] as const;

const AIP_MENU_ROUTES = NAV_ITEMS.flatMap((item) =>
  "path" in item && item.path.startsWith("/aip/") ? [item.path] : [],
);

const ECOMMERCE_WORKSHOP_ROUTES = [
  "/workshop/cockpit",
  "/workshop/content-campaign",
  "/workshop/operations",
  "/workshop/creator-growth",
  "/workshop/media-studio",
  "/workshop/analyst",
  "/workshop/price-governance",
  "/workshop/customer",
] as const;

describe("O1-UX0 · interaction honesty coverage", () => {
  it("registers each ontology digital-twin route exactly once", () => {
    const routes = INTERACTION_HONESTY_MANIFEST.map((entry) => entry.route);
    for (const route of ONTOLOGY_ROUTES) {
      expect(routes.filter((candidate) => candidate === route)).toHaveLength(1);
    }
    for (const route of AIP_AUTHORITY_ROUTES) {
      expect(routes.filter((candidate) => candidate === route)).toHaveLength(1);
      expect(INTERACTION_HONESTY_MANIFEST.find((entry) => entry.route === route)?.sourceMode).toBe("live");
    }
    for (const route of ECOMMERCE_WORKSHOP_ROUTES) {
      expect(routes.filter((candidate) => candidate === route)).toHaveLength(1);
    }
    expect(new Set(routes).size).toBe(routes.length);
  });

  it("keeps every visible AIP menu page under the interaction-honesty gate", () => {
    const normalizedManifestRoutes = new Set(
      INTERACTION_HONESTY_MANIFEST.map((entry) => entry.route.replace("/:flowId", "")),
    );

    expect(AIP_MENU_ROUTES).toHaveLength(25);
    expect(AIP_MENU_ROUTES.filter((route) => !normalizedManifestRoutes.has(route))).toEqual([]);

    for (const route of AIP_MENU_ROUTES) {
      const entry = INTERACTION_HONESTY_MANIFEST.find(
        (candidate) => candidate.route.replace("/:flowId", "") === route,
      );
      expect(entry?.sourceMode, route).toBe("live");
      expect(entry?.sourceFile, route).toMatch(/^apps\/web\/src\//);
      expect(entry?.tests.length, route).toBeGreaterThan(0);
      expect(entry?.fallbackPolicy.length, route).toBeGreaterThan(20);
    }
  });
});
