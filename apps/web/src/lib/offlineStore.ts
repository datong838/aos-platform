/**
 * TWC.8 — 在线/离线态（探针 + navigator.onLine）
 */
export type Connectivity = "online" | "offline" | "unknown";

let connectivity: Connectivity = "unknown";

export function getConnectivity(): Connectivity {
  return connectivity;
}

export function isOffline(): boolean {
  return connectivity === "offline";
}

export function setConnectivity(next: Connectivity, reason = "probe"): void {
  if (connectivity === next) return;
  connectivity = next;
  console.info("[aos-offline]", {
    event: "connectivity",
    state: next,
    reason,
  });
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("aos-offline-changed", { detail: { state: next } }),
    );
  }
}

/** 综合浏览器与健康探针 */
export function applyProbeResult(ok: boolean): void {
  const browserOffline =
    typeof navigator !== "undefined" && navigator.onLine === false;
  if (browserOffline || !ok) {
    setConnectivity("offline", browserOffline ? "navigator" : "health");
  } else {
    setConnectivity("online", "health");
  }
}

export function bindBrowserOnlineListeners(): () => void {
  if (typeof window === "undefined") return () => undefined;
  const on = () => {
    /* 仅标记可能恢复；真值仍靠探针 */
    console.info("[aos-offline]", { event: "browser_online" });
  };
  const off = () => setConnectivity("offline", "navigator");
  window.addEventListener("online", on);
  window.addEventListener("offline", off);
  if (navigator.onLine === false) setConnectivity("offline", "navigator");
  return () => {
    window.removeEventListener("online", on);
    window.removeEventListener("offline", off);
  };
}
