/**
 * TWC.8 / 187m — offline queue storage backends (localStorage | memory | Tauri SQLite cache).
 */
import type { OfflineQueueItem } from "./offlineQueueTypes";

export type OfflineQueueBackend = {
  kind: "localStorage" | "sqlite" | "memory";
  list(orgId: string, projectId: string): OfflineQueueItem[];
  write(orgId: string, projectId: string, items: OfflineQueueItem[]): void;
  clearScope(orgId: string, projectId: string): number;
  clearAll(): number;
};

const PREFIX = "aos.offline.queue.v1:";

function lsRead(key: string): OfflineQueueItem[] {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as OfflineQueueItem[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function lsWrite(key: string, items: OfflineQueueItem[]): void {
  try {
    localStorage.setItem(key, JSON.stringify(items));
  } catch (e) {
    console.warn("[aos-offline]", {
      event: "queue_persist_failed",
      error: e instanceof Error ? e.message : String(e),
    });
  }
}

export const localStorageBackend: OfflineQueueBackend = {
  kind: "localStorage",
  list(orgId, projectId) {
    return lsRead(`${PREFIX}${orgId}:${projectId}`);
  },
  write(orgId, projectId, items) {
    lsWrite(`${PREFIX}${orgId}:${projectId}`, items);
  },
  clearScope(orgId, projectId) {
    const key = `${PREFIX}${orgId}:${projectId}`;
    const n = lsRead(key).length;
    try {
      localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
    return n;
  },
  clearAll() {
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
  },
};

/** In-memory backend for tests / SQLite cache front. */
export function createMemoryBackend(): OfflineQueueBackend {
  const store = new Map<string, OfflineQueueItem[]>();
  const keyOf = (o: string, p: string) => `${o}:${p}`;
  return {
    kind: "memory",
    list(orgId, projectId) {
      return [...(store.get(keyOf(orgId, projectId)) || [])];
    },
    write(orgId, projectId, items) {
      store.set(keyOf(orgId, projectId), [...items]);
    },
    clearScope(orgId, projectId) {
      const k = keyOf(orgId, projectId);
      const n = store.get(k)?.length || 0;
      store.delete(k);
      return n;
    },
    clearAll() {
      const n = store.size;
      store.clear();
      return n;
    },
  };
}

let _backend: OfflineQueueBackend = localStorageBackend;

export function getOfflineQueueBackend(): OfflineQueueBackend {
  return _backend;
}

export function setOfflineQueueBackend(b: OfflineQueueBackend): void {
  _backend = b;
}

export function resetOfflineQueueBackend(): void {
  _backend = localStorageBackend;
}

export function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/**
 * 187m — sync memory cache + fire-and-forget SQLite persist via Tauri invoke.
 * list/write stay synchronous for existing OfflineBanner / client flush.
 */
export function createTauriSqliteBackend(
  invokeFn: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>,
): OfflineQueueBackend {
  const cache = createMemoryBackend();
  const persist = (orgId: string, projectId: string, items: OfflineQueueItem[]) => {
    void invokeFn("oq_replace", { orgId, projectId, items }).catch((e) => {
      console.warn("[aos-offline]", {
        event: "oq_replace_failed",
        error: e instanceof Error ? e.message : String(e),
      });
    });
  };
  return {
    kind: "sqlite",
    list(orgId, projectId) {
      return cache.list(orgId, projectId);
    },
    write(orgId, projectId, items) {
      cache.write(orgId, projectId, items);
      persist(orgId, projectId, items);
    },
    clearScope(orgId, projectId) {
      const n = cache.clearScope(orgId, projectId);
      void invokeFn("oq_clear", { orgId, projectId }).catch(() => undefined);
      return n;
    },
    clearAll() {
      const n = cache.clearAll();
      void invokeFn("oq_clear_all", {}).catch(() => undefined);
      return n;
    },
  };
}

export async function hydrateTauriBackend(
  backend: OfflineQueueBackend,
  invokeFn: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>,
  orgId: string,
  projectId: string,
): Promise<void> {
  if (backend.kind !== "sqlite") return;
  try {
    const rows = (await invokeFn("oq_list", { orgId, projectId })) as OfflineQueueItem[];
    if (Array.isArray(rows)) {
      backend.write(orgId, projectId, rows);
    }
  } catch (e) {
    console.warn("[aos-offline]", {
      event: "oq_hydrate_failed",
      error: e instanceof Error ? e.message : String(e),
    });
  }
}

export async function initOfflineQueueBackend(
  invokeFn?: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>,
): Promise<OfflineQueueBackend["kind"]> {
  if (invokeFn) {
    setOfflineQueueBackend(createTauriSqliteBackend(invokeFn));
    return "sqlite";
  }
  if (!isTauriRuntime()) {
    resetOfflineQueueBackend();
    return "localStorage";
  }
  // Desktop should pass invoke; without it keep localStorage (honest fallback)
  console.warn("[aos-offline]", {
    event: "tauri_detected_without_invoke_fallback_localStorage",
  });
  resetOfflineQueueBackend();
  return "localStorage";
}

export { PREFIX as OFFLINE_QUEUE_PREFIX };
