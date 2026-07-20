/** Shared types for offline queue (187m). */
export type OfflineQueueItem = {
  id: string;
  method: string;
  path: string;
  body?: unknown;
  summary: string;
  createdAt: string;
  lastError?: string;
};
