/** 92/93 · Ontology recent + branch + favorites (local, honest). */

export type RecentKind = "objectType" | "link";

export type RecentEntry = {
  kind: RecentKind;
  id: string;
  label: string;
  href?: string;
  at: number;
};

const RECENT_KEY = "aos.ontology.recent.v1";
const BRANCH_KEY = "aos.ontology.branchId";
const FAVORITES_KEY = "aos.ontology.favorites.v1";
const MAX_RECENT = 8;

function safeParse(raw: string | null): RecentEntry[] {
  if (!raw) return [];
  try {
    const data = JSON.parse(raw) as unknown;
    if (!Array.isArray(data)) return [];
    return data
      .filter((x): x is RecentEntry => {
        if (!x || typeof x !== "object") return false;
        const e = x as RecentEntry;
        return (
          (e.kind === "objectType" || e.kind === "link") &&
          typeof e.id === "string" &&
          typeof e.label === "string" &&
          typeof e.at === "number"
        );
      })
      .slice(0, MAX_RECENT);
  } catch {
    return [];
  }
}

export function loadRecent(): RecentEntry[] {
  try {
    return safeParse(localStorage.getItem(RECENT_KEY));
  } catch {
    return [];
  }
}

export function pushRecent(entry: Omit<RecentEntry, "at"> & { at?: number }): RecentEntry[] {
  const nextItem: RecentEntry = {
    kind: entry.kind,
    id: entry.id,
    label: entry.label,
    href: entry.href,
    at: entry.at ?? Date.now(),
  };
  const prev = loadRecent().filter((x) => !(x.kind === nextItem.kind && x.id === nextItem.id));
  const next = [nextItem, ...prev].slice(0, MAX_RECENT);
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    /* ignore quota / private mode */
  }
  return next;
}

export function loadBranchPref(fallback = "main"): string {
  try {
    return localStorage.getItem(BRANCH_KEY) || fallback;
  } catch {
    return fallback;
  }
}

export function saveBranchPref(id: string): void {
  try {
    localStorage.setItem(BRANCH_KEY, id);
  } catch {
    /* ignore */
  }
}

/** Relative time in zh-CN; never invents dates. */
export function formatRelativeZh(at: number, now = Date.now()): string {
  const delta = Math.max(0, now - at);
  const sec = Math.floor(delta / 1000);
  if (sec < 45) return "刚刚";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} 分钟前`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour} 小时前`;
  const day = Math.floor(hour / 24);
  if (day === 1) return "昨天";
  if (day < 30) return `${day} 天前`;
  return new Date(at).toLocaleDateString("zh-CN");
}

/** 93 · 收藏 OT ids；null = 未配置（UI 回退前 3 个，不假装已收藏） */
export function loadFavorites(): string[] | null {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    if (raw == null) return null;
    const data = JSON.parse(raw) as unknown;
    if (!Array.isArray(data)) return [];
    return data.filter((x): x is string => typeof x === "string");
  } catch {
    return null;
  }
}

export function saveFavorites(ids: string[]): string[] {
  const next = [...new Set(ids)].slice(0, 12);
  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
  return next;
}

export function toggleFavorite(id: string): string[] {
  const cur = loadFavorites() ?? [];
  const next = cur.includes(id) ? cur.filter((x) => x !== id) : [id, ...cur];
  return saveFavorites(next);
}

export function isFavorite(id: string, list: string[] | null): boolean {
  if (!list) return false;
  return list.includes(id);
}

/** Field-level diff for branch overlay vs base. */
export function fieldDiff(
  base: Record<string, unknown> | null | undefined,
  branch: Record<string, unknown> | null | undefined,
): { key: string; base: string; branch: string }[] {
  const b = base && typeof base === "object" ? base : {};
  const br = branch && typeof branch === "object" ? branch : {};
  const keys = [...new Set([...Object.keys(b), ...Object.keys(br)])].sort();
  const out: { key: string; base: string; branch: string }[] = [];
  for (const key of keys) {
    const left = b[key];
    const right = br[key];
    if (JSON.stringify(left) === JSON.stringify(right)) continue;
    out.push({
      key,
      base: left === undefined ? "—" : JSON.stringify(left),
      branch: right === undefined ? "—" : JSON.stringify(right),
    });
  }
  return out;
}
