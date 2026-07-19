import { describe, expect, it } from "vitest";
import { isNavPage, NAV_ITEMS, navPages } from "./nav";
import { readAppearancePreference } from "./lib/appearance";
import { S2_LIVE_PATHS, S2_LIVE_ROUTES } from "./pages/s2/routes";

describe("nav DEMO_PAGES alignment", () => {
  it("keeps narrative sections in order", () => {
    const sections = NAV_ITEMS.filter((i) => "section" in i).map(
      (i) => (i as { section: string }).section,
    );
    expect(sections).toEqual([
      "工作台",
      "AIP 决策引擎",
      "本体 · 数字孪生",
      "数据集成",
      "交付 Apollo",
    ]);
  });

  it("exposes full DEMO page count with live paths", () => {
    const pages = navPages();
    expect(pages.length).toBeGreaterThanOrEqual(35);
    expect(pages.every((p) => p.icon && p.path && p.id)).toBe(true);
    expect(pages.some((p) => p.status === "live")).toBe(true);
    expect(pages.every((p) => p.status === "live" || p.status === "s2")).toBe(true);
    expect(NAV_ITEMS.filter(isNavPage).find((p) => p.id === "index")?.path).toBe(
      "/",
    );
  });

  it("T-UI S2 knife-1～3 promotes all DEMO deep paths to live", () => {
    expect(S2_LIVE_ROUTES.length).toBeGreaterThanOrEqual(32);
    expect(S2_LIVE_PATHS.has("/analytics")).toBe(true);
    for (const path of S2_LIVE_PATHS) {
      if (path.includes(":")) continue; // parametric deep links not in flat nav
      const page = navPages().find((p) => p.path === path);
      expect(page, path).toBeTruthy();
      expect(page!.status, path).toBe("live");
    }
    // knife-3 remainder (were stubs) + TA.0 analytics
    for (const path of [
      "/ontology/okf-funnel",
      "/apollo/ferry",
      "/data/code-repos",
      "/apollo/release",
      "/data/pipeline-proposals",
      "/data/lineage",
      "/apollo/change",
      "/analytics",
    ]) {
      expect(navPages().find((p) => p.path === path)?.status).toBe("live");
    }
    // no remaining DEMO s2 stubs
    expect(navPages().filter((p) => p.status === "s2")).toEqual([]);
  });
});

describe("appearance default", () => {
  it("defaults to dark when unset", () => {
    const storage = { getItem: () => null };
    expect(readAppearancePreference(storage)).toBe("dark");
  });
});
