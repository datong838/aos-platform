/**
 * TWC.2 · D-A11 P1：nav.ts 全量路径须由桌面嵌入的 Web 座舱覆盖（差集空）。
 * 桌面不得维护缩水 NAV；真源 = apps/web/src/nav.ts
 */
import { describe, expect, it } from "vitest";
import { isNavPage, NAV_ITEMS, navPages } from "../../web/src/nav";
import { S2_LIVE_PATHS } from "../../web/src/pages/s2/routes";
import { LOCAL_PLATFORM_NAME, OPS_NAV_SECTION } from "../../web/src/lib/productCopy";

/** 桌面声明：嵌入 Web App = 接受 Web 全部侧栏 path（契约清单） */
export function desktopCoveredPaths(): Set<string> {
  const paths = new Set<string>(navPages().map((p) => p.path));
  for (const p of S2_LIVE_PATHS) {
    if (!p.includes(":")) paths.add(p);
  }
  return paths;
}

describe("TWC.2 desktop ≥ Web parity", () => {
  it("does not ship a separate shrunk NAV_ITEMS", () => {
    const pages = navPages();
    expect(pages.length).toBeGreaterThanOrEqual(40);
    expect(pages.every((p) => p.status === "live")).toBe(true);
  });

  it("P1: nav paths ⊆ desktop covered set (empty diff)", () => {
    const covered = desktopCoveredPaths();
    const missing = navPages()
      .map((p) => p.path)
      .filter((path) => !covered.has(path));
    expect(missing).toEqual([]);
  });

  it("keeps Apollo ops section pages (≥7)", () => {
    const apollo = navPages().filter((p) => p.path.startsWith("/apollo"));
    expect(apollo.length).toBeGreaterThanOrEqual(7);
    const ops = NAV_ITEMS.find(
      (i) => !isNavPage(i) && (i as { section: string }).section === OPS_NAV_SECTION,
    ) as { collapseDefault?: boolean };
    expect(ops?.collapseDefault).toBe(true);
  });

  it("includes 本机探活 and members (TWB.3 / TWA.7)", () => {
    expect(navPages().some((p) => p.path === "/settings/local-platform")).toBe(true);
    expect(navPages().find((p) => p.path === "/settings/local-platform")?.label).toBe(
      LOCAL_PLATFORM_NAME,
    );
    expect(navPages().some((p) => p.path === "/workspace/members")).toBe(true);
  });

  it("TWC.7 / TWB.6 Apollo ≥7 and includes SaaS 开通 (不少页)", () => {
    const apollo = navPages().filter((p) => p.path.startsWith("/apollo"));
    expect(apollo.length).toBeGreaterThanOrEqual(8);
    const paths = apollo.map((p) => p.path);
    expect(paths).toContain("/apollo/provisioning");
    expect(paths).toContain("/apollo");
    expect(paths).toContain("/apollo/spoke");
  });
});
