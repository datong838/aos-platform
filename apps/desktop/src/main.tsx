import React from "react";
import ReactDOM from "react-dom/client";
import { bootstrapTenantFromMe } from "@aos-web/api/client";
import { setApiBase, STORAGE_KEY as API_BASE_KEY } from "@aos-web/api/apiBase";
import { applyChannelApiBase } from "./channel";
import "@aos-web/styles.css";
import App from "./App";

/** 176 · 桌面非浏览器：补 Cmd/Ctrl+R 整页刷新 */
function bindDesktopReload() {
  window.addEventListener("keydown", (e) => {
    const mod = e.metaKey || e.ctrlKey;
    if (!mod || e.key.toLowerCase() !== "r") return;
    e.preventDefault();
    window.location.reload();
  });
}

async function boot() {
  bindDesktopReload();
  applyChannelApiBase(setApiBase, () => {
    try {
      return Boolean(localStorage.getItem(API_BASE_KEY));
    } catch {
      return false;
    }
  });
  console.info("[aos-desktop]", {
    event: "boot",
    shell: "desktop",
    parity: "web-embed",
  });
  await bootstrapTenantFromMe();
  ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

void boot();
