import { beforeEach, describe, expect, it } from "vitest";
import {
  persistOpsNavOpen,
  resolveOpsNavDefaultOpen,
  rolesExpandOpsByDefault,
  STORAGE_KEY,
} from "./opsNav";
import { isNavPage, NAV_ITEMS, navPages } from "../nav";
import { OPS_NAV_SECTION } from "./productCopy";

describe("TWC.7 ops nav policy", () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.innerHTML = "";
  });

  it("admin roles expand by default flag", () => {
    expect(rolesExpandOpsByDefault(["developer"])).toBe(true);
    expect(rolesExpandOpsByDefault(["platform_admin"])).toBe(true);
    expect(rolesExpandOpsByDefault(["viewer"])).toBe(false);
  });

  it("without preference stays collapsed on web (no desktop shell)", () => {
    expect(resolveOpsNavDefaultOpen(["developer"])).toBe(false);
  });

  it("desktop shell + developer defaults open", () => {
    document.body.innerHTML = `<div data-shell="desktop"></div>`;
    expect(resolveOpsNavDefaultOpen(["developer"])).toBe(true);
    expect(resolveOpsNavDefaultOpen(["viewer"])).toBe(false);
  });

  it("manual preference overrides role", () => {
    document.body.innerHTML = `<div data-shell="desktop"></div>`;
    persistOpsNavOpen(false);
    expect(localStorage.getItem(STORAGE_KEY)).toBe("0");
    expect(resolveOpsNavDefaultOpen(["developer"])).toBe(false);
    persistOpsNavOpen(true);
    expect(resolveOpsNavDefaultOpen(["viewer"])).toBe(true);
  });

  it("Apollo seven pages remain and section is collapsible", () => {
    const apollo = navPages().filter((p) => p.path.startsWith("/apollo"));
    expect(apollo.length).toBeGreaterThanOrEqual(7);
    const ops = NAV_ITEMS.find(
      (i) => !isNavPage(i) && (i as { section: string }).section === OPS_NAV_SECTION,
    ) as { collapseDefault?: boolean };
    expect(ops.collapseDefault).toBe(true);
  });
});
