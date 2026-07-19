import { describe, expect, it } from "vitest";
import {
  assertNotCallingLocalPlatformApollo,
  LOCAL_PLATFORM_NAME,
  MODEL_CONFIG_NO_VAULT,
  OPS_NAV_SECTION,
} from "./productCopy";
import { isNavPage, NAV_ITEMS, navPages } from "../nav";

describe("TWB.2 / TWB.3 product copy & nav", () => {
  it("本机探活 never equals Apollo", () => {
    expect(LOCAL_PLATFORM_NAME).toBe("本机探活");
    expect(LOCAL_PLATFORM_NAME.toLowerCase()).not.toContain("apollo");
    expect(assertNotCallingLocalPlatformApollo("本机探活")).toBe(true);
    expect(assertNotCallingLocalPlatformApollo("本机 Apollo")).toBe(false);
  });

  it("ops section is collapsible and apollo routes preserved", () => {
    const ops = NAV_ITEMS.find(
      (i) => "section" in i && (i as { section: string }).section === OPS_NAV_SECTION,
    ) as { section: string; collapseDefault?: boolean } | undefined;
    expect(ops?.collapseDefault).toBe(true);

    const apolloPages = navPages().filter((p) => p.path.startsWith("/apollo"));
    expect(apolloPages.length).toBeGreaterThanOrEqual(7);
    expect(apolloPages.every((p) => p.status === "live")).toBe(true);
  });

  it("local platform page is live under 运维交付", () => {
    const page = navPages().find((p) => p.path === "/settings/local-platform");
    expect(page?.label).toBe(LOCAL_PLATFORM_NAME);
    expect(page?.status).toBe("live");
    expect(page?.crumbs?.[0]).toBe(OPS_NAV_SECTION);

    const opsIdx = NAV_ITEMS.findIndex(
      (i) => "section" in i && (i as { section: string }).section === OPS_NAV_SECTION,
    );
    const lpIdx = NAV_ITEMS.findIndex(
      (i) => isNavPage(i) && i.path === "/settings/local-platform",
    );
    expect(opsIdx).toBeGreaterThanOrEqual(0);
    expect(lpIdx).toBeGreaterThan(opsIdx);
  });

  it("model config copy forbids vault console from业务座舱", () => {
    expect(MODEL_CONFIG_NO_VAULT).toMatch(/secretRef/);
    expect(MODEL_CONFIG_NO_VAULT).toMatch(/Vault/);
  });

  it("workspace members still present", () => {
    expect(NAV_ITEMS.filter(isNavPage).some((p) => p.path === "/workspace/members")).toBe(
      true,
    );
  });
});
