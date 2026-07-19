import { describe, expect, it } from "vitest";
import { OPS_GUIDE_TIERS } from "../lib/opsStartGuideContent";
import { isNavPage, NAV_ITEMS } from "../nav";
import { OPS_NAV_SECTION } from "../lib/productCopy";

describe("167 OpsStartGuide", () => {
  it("covers four 20a/72 tiers plus airgap", () => {
    const ids = OPS_GUIDE_TIERS.map((t) => t.id);
    expect(ids).toEqual(["local", "enterprise", "group", "saas", "airgap"]);
    for (const t of OPS_GUIDE_TIERS) {
      expect(t.start.length).toBeGreaterThan(0);
      expect(t.stop.length).toBeGreaterThan(0);
      expect(t.health.length).toBeGreaterThan(0);
    }
  });

  it("nav page lives under 运维交付", () => {
    const idx = NAV_ITEMS.findIndex(
      (i) => "section" in i && i.section === OPS_NAV_SECTION,
    );
    expect(idx).toBeGreaterThanOrEqual(0);
    const page = NAV_ITEMS.find(
      (i) => isNavPage(i) && i.path === "/settings/ops-start-guide",
    );
    expect(page).toBeTruthy();
    expect(isNavPage(page!) && page.status).toBe("live");
    const pageIdx = NAV_ITEMS.findIndex(
      (i) => isNavPage(i) && i.path === "/settings/ops-start-guide",
    );
    expect(pageIdx).toBeGreaterThan(idx);
  });
});
