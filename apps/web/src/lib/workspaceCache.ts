/**
 * TWC.6 — 切工作区时清理本地缓存（防串区）
 * 保留：外观偏好、API Base、当前租户由 setTenant 写入
 * TWC.8 — 一并清离线队列/快照（防串区）
 */
import { clearAllOfflineQueues } from "./offlineQueue";
import { clearAllOfflineSnapshots } from "./offlineSnapshot";

const ONTOLOGY_KEYS = [
  "aos.ontology.recent.v1",
  "aos.ontology.branchId",
  "aos.ontology.favorites.v1",
] as const;

const MP_DRAFT_PREFIX = "aos.mp.draft.";

export function clearWorkspaceLocalCache(reason = "workspace-changed"): {
  sessionRemoved: number;
  localRemoved: number;
  offlineRemoved: number;
} {
  let sessionRemoved = 0;
  let localRemoved = 0;
  try {
    const keys: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i);
      if (k && k.startsWith(MP_DRAFT_PREFIX)) keys.push(k);
    }
    for (const k of keys) {
      sessionStorage.removeItem(k);
      sessionRemoved += 1;
    }
  } catch {
    /* ignore */
  }
  try {
    for (const k of ONTOLOGY_KEYS) {
      if (localStorage.getItem(k) != null) {
        localStorage.removeItem(k);
        localRemoved += 1;
      }
    }
  } catch {
    /* ignore */
  }
  const offlineRemoved = clearAllOfflineQueues() + clearAllOfflineSnapshots();
  console.info("[aos-workspace-cache]", {
    event: "cleared",
    reason,
    sessionRemoved,
    localRemoved,
    offlineRemoved,
  });
  return { sessionRemoved, localRemoved, offlineRemoved };
}

export { MP_DRAFT_PREFIX, ONTOLOGY_KEYS };
