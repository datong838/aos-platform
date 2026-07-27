import { describe, expect, it } from "vitest";
import { isNavPage, NAV_ITEMS, navPages } from "./nav";
import { readAppearancePreference } from "./lib/appearance";
import { S2_LIVE_PATHS, S2_LIVE_ROUTES } from "./pages/s2/routes";

describe("nav product sections alignment", () => {
  it("keeps narrative sections in order", () => {
    const sections = NAV_ITEMS.filter((i) => "section" in i).map(
      (i) => (i as { section: string }).section,
    );
    expect(sections).toEqual([
      "工作台",
      "应用程序构建工具",
      "AIP 决策引擎",
      "模型管理",
      "本体 · 数字孪生",
      "管道与数据治理",
      "数据源与同步",
      "运维交付",
    ]);
  });

  it("TWB.2 ops section collapses by default flag", () => {
    const ops = NAV_ITEMS.find(
      (i) => "section" in i && (i as { section: string }).section === "运维交付",
    ) as { collapseDefault?: boolean };
    expect(ops.collapseDefault).toBe(true);
    expect(navPages().filter((p) => p.path.startsWith("/apollo")).length).toBeGreaterThanOrEqual(7);
  });

  it("exposes full page count with live paths", () => {
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
    // Sub-routes that are action/detail pages, not primary nav entries
    const ACTION_PATHS = new Set([
      "/data/sources/new",
      "/data/builds/current",
      "/ontology/functions",
      "/settings/profile",
      "/settings/audit",
      "/settings/permissions",
      "/workshop/risk-alerts",
    ]);
    // Pages explicitly kept as s2 stubs (planned for future waves)
    const PLANNED_S2 = new Set([
      "/workshop/widget-registry",
      "/workshop/variables",
      "/workshop/styles",
    ]);
    for (const path of S2_LIVE_PATHS) {
      if (path.includes(":")) continue; // parametric deep links not in flat nav
      if (ACTION_PATHS.has(path)) continue; // action pages not in primary nav
      if (PLANNED_S2.has(path)) continue; // still s2 stubs
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
    // no remaining DEMO s2 stubs except explicitly planned pages (223-plan W4)
    const remainingS2 = navPages().filter((p) => p.status === "s2");
    for (const p of remainingS2) {
      expect(PLANNED_S2.has(p.path), `unexpected s2 stub: ${p.path}`).toBe(true);
    }
  });
});

describe("appearance default", () => {
  it("defaults to dark when unset", () => {
    const storage = { getItem: () => null };
    expect(readAppearancePreference(storage)).toBe("dark");
  });
});
