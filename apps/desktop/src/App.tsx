/** TWC.2～6 — 桌面：欢迎 → 登录 → 同构座舱 · 深链 · 切区清缓存 */
import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { App as WebApp } from "@aos-web/App";
import { probeApiHealth, bootstrapTenantFromMe } from "@aos-web/api/client";
import { expandOpsNav } from "@aos-web/lib/opsNav";
import { LOCAL_PLATFORM_NAME } from "@aos-web/lib/productCopy";
import { clearWorkspaceLocalCache } from "@aos-web/lib/workspaceCache";
import { Welcome } from "./Welcome";
import { Login } from "./Login";
import { AboutDialog } from "./AboutDialog";
import { UpdateDialog } from "./UpdateDialog";
import { checkDesktopUpdate } from "./update/check";
import type { UpdateManifest } from "./update/verify";
import BuddyLegacyApp from "./BuddyLegacyApp";
import {
  DEFAULT_DESKTOP_VIEW,
  type DesktopViewMode,
} from "./buddyMode";
import { isLoggedIn, restoreSession } from "./session";
import {
  navigateFromDeepLink,
  parseAosDeepLink,
  queuePendingDeepLink,
  takePendingDeepLink,
} from "./deepLink";
import "./desktop.css";

type Phase = "checking" | "welcome" | "login" | "shell";

function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function openPlatformAdmin() {
  expandOpsNav();
  window.history.pushState({}, "", "/apollo");
  window.dispatchEvent(new PopStateEvent("popstate"));
  console.info("[aos-desktop]", { event: "ui14_platform_admin" });
}

export default function App() {
  const [phase, setPhase] = useState<Phase>("checking");
  const [aboutOpen, setAboutOpen] = useState(false);
  const [updateOpen, setUpdateOpen] = useState(false);
  const [updateManifest, setUpdateManifest] = useState<UpdateManifest | null>(
    null,
  );
  const [updateError, setUpdateError] = useState("");
  const [viewMode, setViewMode] = useState<DesktopViewMode>(DEFAULT_DESKTOP_VIEW);
  const [toast, setToast] = useState("");

  async function runCheckUpdate() {
    setUpdateError("");
    const r = await checkDesktopUpdate("0.1.0");
    if (r.status === "available") {
      setUpdateManifest(r.manifest);
      setUpdateOpen(true);
      return;
    }
    if (r.status === "invalid") {
      setUpdateManifest(null);
      setUpdateError(r.reason);
      setUpdateOpen(true);
      showToast(`更新清单无效：${r.reason}`);
      return;
    }
    setUpdateManifest(null);
    setUpdateError("");
    setUpdateOpen(true);
  }
  function showToast(msg: string) {
    setToast(msg);
    window.setTimeout(() => setToast(""), 4000);
  }

  function consumeDeepLinkUrl(raw: string, loggedIn: boolean) {
    const parsed = parseAosDeepLink(raw);
    console.info("[aos-deeplink]", {
      event: "received",
      kind: parsed.kind,
      path: parsed.path,
      reason: parsed.reason,
    });
    if (parsed.kind === "rejected") {
      showToast(`深链拒绝：${parsed.reason || "unknown"}`);
      return;
    }
    if (parsed.kind === "auth_callback") {
      showToast("已收到登录回调 · 请完成开发令牌登录（OIDC 完整流见后续）");
      if (!loggedIn) setPhase("login");
      return;
    }
    if (!loggedIn) {
      queuePendingDeepLink(raw);
      showToast("请先登录，随后打开深链目标");
      setPhase("login");
      return;
    }
    if (navigateFromDeepLink(parsed)) {
      showToast(`已打开 ${parsed.path}`);
    }
  }

  function flushPendingDeepLink() {
    const pending = takePendingDeepLink();
    if (pending) consumeDeepLinkUrl(pending, true);
  }

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const health = await probeApiHealth();
      if (cancelled) return;
      console.info("[aos-desktop]", {
        event: "health_probe",
        ok: health.ok,
        detail: health.detail,
      });
      if (!health.ok) {
        setPhase("welcome");
        return;
      }
      const restored = await restoreSession();
      if (cancelled) return;
      if (restored || isLoggedIn()) {
        await bootstrapTenantFromMe();
        setPhase("shell");
        flushPendingDeepLink();
      } else {
        setPhase("login");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    function onWs() {
      clearWorkspaceLocalCache("desktop-listener");
    }
    window.addEventListener("aos-workspace-changed", onWs);
    return () => window.removeEventListener("aos-workspace-changed", onWs);
  }, []);

  useEffect(() => {
    if (!isTauri()) return;
    let unsubs: Array<() => void> = [];
    void listen("aos-desktop-about", () => setAboutOpen(true)).then((fn) => {
      unsubs.push(fn);
    });
    void listen("aos-desktop-check-update", () => {
      void runCheckUpdate();
    }).then((fn) => unsubs.push(fn));
    void listen("aos-desktop-buddy-classic", () => {
      setViewMode("buddy-classic");
      console.info("[aos-desktop]", { event: "ui13_buddy_classic" });
    }).then((fn) => unsubs.push(fn));
    void listen<{ path?: string }>("aos-desktop-navigate", (ev) => {
      const path = ev.payload?.path;
      if (path) {
        console.info("[aos-desktop]", { event: "navigate", path });
        window.history.pushState({}, "", path);
        window.dispatchEvent(new PopStateEvent("popstate"));
      }
    }).then((fn) => unsubs.push(fn));

    void import("@tauri-apps/plugin-deep-link")
      .then(({ onOpenUrl }) =>
        onOpenUrl((urls) => {
          for (const u of urls) consumeDeepLinkUrl(u, isLoggedIn() || phase === "shell");
        }),
      )
      .then((un) => {
        if (typeof un === "function") unsubs.push(un);
      })
      .catch((e) => {
        console.warn("[aos-deeplink]", {
          event: "plugin_unavailable",
          error: e instanceof Error ? e.message : String(e),
        });
      });

    return () => unsubs.forEach((u) => u());
  }, [phase]);

  async function enterShellAfterLogin() {
    await bootstrapTenantFromMe();
    setPhase("shell");
    flushPendingDeepLink();
  }

  if (phase === "checking") {
    return (
      <div className="aos-desktop-boot" data-shell="desktop">
        正在连接平台…
      </div>
    );
  }

  if (phase === "welcome") {
    return (
      <Welcome
        onEnterShell={() => {
          console.info("[aos-desktop]", { event: "welcome_continue" });
          setPhase(isLoggedIn() ? "shell" : "login");
        }}
      />
    );
  }

  if (phase === "login") {
    return <Login onLoggedIn={() => void enterShellAfterLogin()} />;
  }

  if (viewMode === "buddy-classic") {
    return (
      <div className="aos-desktop-root" data-shell="desktop" data-ui="UI-13">
        <div className="aos-desktop-ribbon">
          <span>Buddy 经典三栏 · 非默认首页</span>
          <button
            type="button"
            className="aos-desktop-ribbon-btn"
            onClick={() => setViewMode("cockpit")}
          >
            返回座舱
          </button>
        </div>
        <div className="aos-desktop-webhost">
          <BuddyLegacyApp />
        </div>
      </div>
    );
  }

  return (
    <div className="aos-desktop-root" data-shell="desktop">
      <div className="aos-desktop-ribbon" title={LOCAL_PLATFORM_NAME}>
        <span>AOS 桌面 · 同构座舱（≥ Web）</span>
        <div className="aos-desktop-ribbon-actions">
          <button
            type="button"
            className="aos-desktop-ribbon-btn"
            data-ui="UI-14"
            onClick={openPlatformAdmin}
            title="展开运维交付 · 进入 Hub（克制入口）"
          >
            平台管理
          </button>
          <button
            type="button"
            className="aos-desktop-ribbon-btn"
            data-ui="UI-13"
            onClick={() => {
              setViewMode("buddy-classic");
              console.info("[aos-desktop]", { event: "ui13_buddy_classic" });
            }}
          >
            Buddy 三栏
          </button>
          <button
            type="button"
            className="aos-desktop-ribbon-btn"
            data-ui="UI-10"
            onClick={() => void runCheckUpdate()}
          >
            检查更新
          </button>
          <button
            type="button"
            className="aos-desktop-ribbon-btn"
            onClick={() => setAboutOpen(true)}
          >
            关于
          </button>
        </div>
      </div>
      {toast ? (
        <div className="aos-desktop-toast" data-ui="UI-15" role="status">
          {toast}
        </div>
      ) : null}
      <div className="aos-desktop-webhost">
        <WebApp />
      </div>
      <AboutDialog open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <UpdateDialog
        open={updateOpen}
        manifest={updateManifest}
        error={updateError}
        onClose={() => setUpdateOpen(false)}
      />
    </div>
  );
}
