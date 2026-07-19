/**
 * TWC.8 — 待同步队列（按工作区隔离；禁离线直写）
 */
import { getTenant } from "../api/tenant";

export type OfflineQueueItem = {
  id: string;
  method: string;
  path: string;
  body?: unknown;
  summary: string;
  createdAt: string;
  lastError?: string;
};

const PREFIX = "aos.offline.queue.v1:";

function scopeKey(orgId?: string, projectId?: string): string {
  const t = getTenant();
  return `${PREFIX}${orgId ?? t.orgId}:${projectId ?? t.projectId}`;
}

function readRaw(key: string): OfflineQueueItem[] {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as OfflineQueueItem[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeRaw(key: string, items: OfflineQueueItem[]): void {
  try {
    localStorage.setItem(key, JSON.stringify(items));
  } catch (e) {
    console.warn("[aos-offline]", {
      event: "queue_persist_failed",
      error: e instanceof Error ? e.message : String(e),
    });
  }
}

export function listOfflineQueue(
  orgId?: string,
  projectId?: string,
): OfflineQueueItem[] {
  return readRaw(scopeKey(orgId, projectId));
}

export function enqueueOfflineWrite(input: {
  method: string;
  path: string;
  body?: unknown;
  summary?: string;
}): OfflineQueueItem {
  const key = scopeKey();
  const items = readRaw(key);
  const item: OfflineQueueItem = {
    id: `oq-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    method: input.method.toUpperCase(),
    path: input.path,
    body: input.body,
    summary:
      input.summary ||
      `${input.method.toUpperCase()} ${input.path}`.slice(0, 120),
    createdAt: new Date().toISOString(),
  };
  items.push(item);
  writeRaw(key, items);
  const t = getTenant();
  console.info("[aos-offline]", {
    event: "enqueued",
    orgId: t.orgId,
    projectId: t.projectId,
    method: item.method,
    path: item.path,
    queueSize: items.length,
  });
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("aos-offline-queue-changed", {
        detail: { size: items.length },
      }),
    );
  }
  return item;
}

export function removeOfflineQueueItem(id: string): void {
  const key = scopeKey();
  const next = readRaw(key).filter((x) => x.id !== id);
  writeRaw(key, next);
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("aos-offline-queue-changed", {
        detail: { size: next.length },
      }),
    );
  }
}

export function markOfflineQueueError(id: string, lastError: string): void {
  const key = scopeKey();
  const items = readRaw(key).map((x) =>
    x.id === id ? { ...x, lastError } : x,
  );
  writeRaw(key, items);
}

export function clearOfflineQueueForWorkspace(
  orgId: string,
  projectId: string,
): number {
  const key = scopeKey(orgId, projectId);
  const n = readRaw(key).length;
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
  return n;
}

/** 切区：清除所有 aos.offline.queue.v1:* */
export function clearAllOfflineQueues(): number {
  let n = 0;
  try {
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k?.startsWith(PREFIX)) keys.push(k);
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

export { PREFIX as OFFLINE_QUEUE_PREFIX };
