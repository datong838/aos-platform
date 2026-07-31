import { NAV_ITEMS } from "./navigation/items";
import type {
  IconName,
  NavItem,
  NavPage,
  NavSection,
  NavSubgroup,
} from "./navigation/types";

export { NAV_ITEMS };
export type { IconName, NavItem, NavPage, NavSection, NavSubgroup };

export function isNavSection(item: NavItem): item is NavSection {
  return "section" in item;
}

export function isNavSubgroup(item: NavItem): item is NavSubgroup {
  return "subgroup" in item;
}

export function isNavPage(item: NavItem): item is NavPage {
  return "path" in item;
}

export function navPages(): NavPage[] {
  return NAV_ITEMS.filter(isNavPage);
}

export function findNavPage(pathname: string): NavPage | undefined {
  const pages = navPages();
  const exact = pages.find((p) => p.path === pathname);
  if (exact) return exact;
  // longest prefix match，且必须落在路径段边界（避免 /workshop 误匹配 /workshop/buddy）
  return pages
    .filter(
      (p) =>
        p.path !== "/" &&
        (pathname === p.path || pathname.startsWith(`${p.path}/`)),
    )
    .sort((a, b) => b.path.length - a.path.length)[0];
}

export const DEMO_VERSION = "v1.6.5";
