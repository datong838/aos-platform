/**
 * TWC.8 / 187m — 待同步队列（按工作区隔离；禁离线直写）
 * 默认同构 localStorage；桌面可切 Tauri SQLite（缓存同步 API + 后台持久化）
 */
import { getTenant } from "../api/tenant";
import type { OfflineQueueItem } from "./offlineQueueTypes";
import {
  createMemoryBackend,
  createTauriSqliteBackend,
  getOfflineQueueBackend,
  initOfflineQueueBackend,
  isTauriRuntime,
  localStorageBackend,
  OFFLINE_QUEUE_PREFIX,
  resetOfflineQueueBackend,
  setOfflineQueueBackend,
  type OfflineQueueBackend,
} from "./offlineQueueBackend";

export type { OfflineQueueItem } from "./offlineQueueTypes";
export {
  setOfflineQueueBackend,
  resetOfflineQueueBackend,
  createMemoryBackend,
  createTauriSqliteBackend,
  initOfflineQueueBackend,
  getOfflineQueueBackend,
  isTauriRuntime,
};

function scopeIds(orgId?: string, projectId?: string): {
  orgId: string;
  projectId: string;
} {
  const t = getTenant();
  return { orgId: orgId ?? t.orgId, projectId: projectId ?? t.projectId };
}

function syncList(backend: OfflineQueueBackend, orgId: string, projectId: string): OfflineQueueItem[] {
  const out = backend.list(orgId, projectId);
  if (out && typeof (out as Promise<unknown>).then === "function") {
    return [];
  }
  return (out as OfflineQueueItem[]) || [];
}

function syncWrite(
  backend: OfflineQueueBackend,
  orgId: string,
  projectId: string,
  items: OfflineQueueItem[],
): void {
  const r = backend.write(orgId, projectId, items);
  if (r && typeof (r as Promise<unknown>).then === "function") {
    void (r as Promise<void>);
  }
}

function emitChanged(size: number) {
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("aos-offline-queue-changed", {
        detail: { size },
      }),
    );
  }
}

export function listOfflineQueue(
  orgId?: string,
  projectId?: string,
): OfflineQueueItem[] {
  const { orgId: o, projectId: p } = scopeIds(orgId, projectId);
  return syncList(getOfflineQueueBackend(), o, p);
}

export function enqueueOfflineWrite(input: {
  method: string;
  path: string;
  body?: unknown;
  summary?: string;
}): OfflineQueueItem {
  const { orgId, projectId } = scopeIds();
  const backend = getOfflineQueueBackend();
  const items = syncList(backend, orgId, projectId);
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
  syncWrite(backend, orgId, projectId, items);
  console.info("[aos-offline]", {
    event: "enqueued",
    orgId,
    projectId,
    method: item.method,
    path: item.path,
    queueSize: items.length,
    backend: backend.kind,
  });
  emitChanged(items.length);
  return item;
}

export function removeOfflineQueueItem(id: string): void {
  const { orgId, projectId } = scopeIds();
  const backend = getOfflineQueueBackend();
  const next = syncList(backend, orgId, projectId).filter((x) => x.id !== id);
  syncWrite(backend, orgId, projectId, next);
  emitChanged(next.length);
}

export function markOfflineQueueError(id: string, lastError: string): void {
  const { orgId, projectId } = scopeIds();
  const backend = getOfflineQueueBackend();
  const items = syncList(backend, orgId, projectId).map((x) =>
    x.id === id ? { ...x, lastError } : x,
  );
  syncWrite(backend, orgId, projectId, items);
}

export function clearOfflineQueueForWorkspace(
  orgId: string,
  projectId: string,
): number {
  const backend = getOfflineQueueBackend();
  const r = backend.clearScope(orgId, projectId);
  if (r && typeof (r as Promise<unknown>).then === "function") {
    void (r as Promise<number>);
    return 0;
  }
  return r as number;
}

export function clearAllOfflineQueues(): number {
  const backend = getOfflineQueueBackend();
  const r = backend.clearAll();
  if (r && typeof (r as Promise<unknown>).then === "function") {
    void (r as Promise<number>);
    return 0;
  }
  return r as number;
}

export { OFFLINE_QUEUE_PREFIX as PREFIX, localStorageBackend };
