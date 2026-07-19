import { useEffect, useState } from "react";
import { flushOfflineQueue, probeApiHealth } from "../api/client";
import {
  bindBrowserOnlineListeners,
  getConnectivity,
  isOffline,
} from "../lib/offlineStore";
import {
  listOfflineQueue,
  removeOfflineQueueItem,
  type OfflineQueueItem,
} from "../lib/offlineQueue";

/**
 * TWC.8 / UI-09 — 离线横幅与待同步抽屉
 * 与 ApiStatusBar 并存：离线时展示本条；可达时本条在有队列时仍提示冲刷。
 */
export function OfflineBanner() {
  const [offline, setOffline] = useState(() => isOffline());
  const [queueSize, setQueueSize] = useState(() => listOfflineQueue().length);
  const [drawer, setDrawer] = useState(false);
  const [items, setItems] = useState<OfflineQueueItem[]>([]);
  const [flushMsg, setFlushMsg] = useState("");
  const [retrying, setRetrying] = useState(false);
  const [retryMsg, setRetryMsg] = useState("");

  useEffect(() => {
    const unbind = bindBrowserOnlineListeners();
    function onConn() {
      setOffline(getConnectivity() === "offline");
      if (getConnectivity() !== "offline") setRetryMsg("");
    }
    function onQ() {
      setQueueSize(listOfflineQueue().length);
      setItems(listOfflineQueue());
    }
    window.addEventListener("aos-offline-changed", onConn);
    window.addEventListener("aos-offline-queue-changed", onQ);
    setOffline(isOffline());
    setQueueSize(listOfflineQueue().length);
    return () => {
      unbind();
      window.removeEventListener("aos-offline-changed", onConn);
      window.removeEventListener("aos-offline-queue-changed", onQ);
    };
  }, []);

  if (!offline && queueSize === 0) return null;

  const openDrawer = () => {
    setItems(listOfflineQueue());
    setDrawer(true);
  };

  const discard = (id: string) => {
    if (!offline || window.confirm("确认丢弃该待同步项？不可恢复。")) {
      removeOfflineQueueItem(id);
      setItems(listOfflineQueue());
      setQueueSize(listOfflineQueue().length);
    }
  };

  async function onRetry() {
    setRetrying(true);
    setRetryMsg("探测中…");
    try {
      const r = await probeApiHealth();
      if (r.ok) {
        setOffline(false);
        setRetryMsg("");
      } else {
        setRetryMsg(
          `仍不可达 · ${r.detail} · 本机执行 bash scripts/demo/ensure-api.sh，或打开启停说明`,
        );
      }
    } finally {
      setRetrying(false);
    }
  }

  return (
    <div
      className={
        offline
          ? "aos-offline-banner"
          : "aos-offline-banner aos-offline-banner-queued"
      }
      role={offline ? "alert" : "status"}
      data-ui="UI-09"
    >
      {offline
        ? `⚠ 当前离线 · 仅可浏览已缓存内容 · 写操作已排队（${queueSize}）`
        : `有待同步写操作（${queueSize}）`}
      <button type="button" className="aos-offline-banner-btn" onClick={openDrawer}>
        查看队列
      </button>
      {offline ? (
        <button
          type="button"
          className="aos-offline-banner-btn"
          data-testid="offline-retry-connect"
          disabled={retrying}
          onClick={() => void onRetry()}
        >
          {retrying ? "探测中…" : "重试连接"}
        </button>
      ) : (
        <button
          type="button"
          className="aos-offline-banner-btn"
          onClick={() =>
            void (async () => {
              const r = await flushOfflineQueue();
              setFlushMsg(
                `冲刷完成 · 成功 ${r.ok} · 失败 ${r.fail} · 剩余 ${r.remaining}`,
              );
              setQueueSize(r.remaining);
              setItems(listOfflineQueue());
            })()
          }
        >
          冲刷队列
        </button>
      )}
      {retryMsg ? (
        <span className="aos-muted" data-testid="offline-retry-msg">
          {" "}
          · {retryMsg}
        </span>
      ) : null}
      {flushMsg ? <span className="aos-muted"> · {flushMsg}</span> : null}
      {drawer ? (
        <div className="aos-offline-drawer" role="dialog" aria-label="待同步队列">
          <div className="aos-offline-drawer-head">
            <strong>待同步队列</strong>
            <button
              type="button"
              className="aos-offline-banner-btn"
              onClick={() => setDrawer(false)}
            >
              关闭
            </button>
          </div>
          {items.length === 0 ? (
            <p className="aos-muted">队列为空</p>
          ) : (
            <ul className="aos-offline-drawer-list">
              {items.map((it) => (
                <li key={it.id}>
                  <div>
                    <code>{it.summary}</code>
                    <div className="aos-muted">{it.createdAt}</div>
                    {it.lastError ? (
                      <div className="aos-offline-err">{it.lastError}</div>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    className="aos-offline-banner-btn"
                    onClick={() => discard(it.id)}
                  >
                    丢弃
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
