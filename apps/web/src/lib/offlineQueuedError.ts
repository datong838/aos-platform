/**
 * TWC.8 — 离线写被拦截后的错误（已入队，非生产直写）
 */
export class OfflineQueuedError extends Error {
  readonly code = "OFFLINE_QUEUED";
  readonly queueId: string;

  constructor(queueId: string, summary: string) {
    super(`当前离线 · 已加入待同步队列：${summary}`);
    this.name = "OfflineQueuedError";
    this.queueId = queueId;
  }
}

export function isOfflineQueuedError(e: unknown): e is OfflineQueuedError {
  return e instanceof OfflineQueuedError ||
    (typeof e === "object" &&
      e !== null &&
      (e as { code?: string }).code === "OFFLINE_QUEUED");
}
