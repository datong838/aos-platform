import type { ExtensionRuntimeIdentity } from "./extensionBridge";

export function ExtensionNavigation({ title, route, identity }: { title: string; route: string; identity: ExtensionRuntimeIdentity }) {
  return (
    <header aria-label="扩展页面导航" style={{ alignItems: "center", borderBottom: "1px solid var(--border, #dce3ec)", display: "flex", gap: 12, minHeight: 48, padding: "0 16px" }}>
      <strong>{title}</strong>
      <span aria-current="page" style={{ color: "var(--muted, #6b7a90)", fontSize: 13 }}>{route}</span>
      <span style={{ marginLeft: "auto", color: "var(--muted, #6b7a90)", fontSize: 12 }}>运行代次 {identity.generation} · 安全周期 {identity.executionEpoch}</span>
    </header>
  );
}
