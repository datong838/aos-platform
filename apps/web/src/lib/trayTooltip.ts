/** 195m — tray tooltip copy from connectivity + offline queue length. */
export type TrayConnectivity = "online" | "offline" | "unknown";

export function formatTrayTooltip(
  connectivity: TrayConnectivity,
  queueLen: number,
): string {
  const n = Math.max(0, Math.floor(queueLen || 0));
  if (connectivity === "offline") {
    return n > 0 ? `AOS 桌面 · 离线（待同步 ${n}）` : "AOS 桌面 · 离线";
  }
  if (n > 0) {
    return `AOS 桌面 · 待同步 ${n}`;
  }
  return "AOS 桌面";
}
