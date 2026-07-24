/**
 * TWC.8 — 只读快照（按工作区 + path；切区由 workspaceCache 清）
 */
import { getTenant } from "../api/tenant";

const PREFIX = "aos.offline.snap.v1:";
const MAX_PER_WS = 40;
const INDEX_PREFIX = "aos.offline.snapidx.v1:";

type Snap = { body: unknown; savedAt: string };

function wsPart(orgId?: string, projectId?: string): string {
  const t = getTenant();
  return `${orgId ?? t.orgId}:${projectId ?? t.projectId}`;
}

function snapKey(path: string, orgId?: string, projectId?: string): string {
  return `${PREFIX}${wsPart(orgId, projectId)}:${path}`;
}

function indexKey(orgId?: string, projectId?: string): string {
  return `${INDEX_PREFIX}${wsPart(orgId, projectId)}`;
}

function readIndex(orgId?: string, projectId?: string): string[] {
  try {
    const raw = localStorage.getItem(indexKey(orgId, projectId));
    if (!raw) return [];
    const p = JSON.parse(raw) as string[];
    return Array.isArray(p) ? p : [];
  } catch {
    return [];
  }
}

function writeIndex(paths: string[], orgId?: string, projectId?: string): void {
  try {
    localStorage.setItem(indexKey(orgId, projectId), JSON.stringify(paths));
  } catch {
    /* ignore */
  }
}

export function saveOfflineSnapshot(path: string, body: unknown): void {
  const key = snapKey(path);
  const snap: Snap = { body, savedAt: new Date().toISOString() };
  try {
    localStorage.setItem(key, JSON.stringify(snap));
  } catch {
    console.warn("[aos-offline]", { event: "snap_persist_failed", path });
    return;
  }
  let idx = readIndex().filter((p) => p !== path);
  idx.push(path);
  while (idx.length > MAX_PER_WS) {
    const drop = idx.shift();
    if (drop) {
      try {
        localStorage.removeItem(snapKey(drop));
      } catch {
        /* ignore */
      }
    }
  }
  writeIndex(idx);
}

export function readOfflineSnapshot<T>(path: string): T | null {
  try {
    const raw = localStorage.getItem(snapKey(path));
    if (!raw) return null;
    const snap = JSON.parse(raw) as Snap;
    return snap.body as T;
  } catch {
    return null;
  }
}

export function clearAllOfflineSnapshots(): number {
  let n = 0;
  try {
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k?.startsWith(PREFIX) || k?.startsWith(INDEX_PREFIX)) keys.push(k);
    }
    for (const k of keys) {
      localStorage.removeItem(k);
      n += 1;
    }
  } catch {
    /* ignore */
  }
  return n;
}

export { PREFIX as OFFLINE_SNAP_PREFIX, INDEX_PREFIX as OFFLINE_SNAP_INDEX_PREFIX };
