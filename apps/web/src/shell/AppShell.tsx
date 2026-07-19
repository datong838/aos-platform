import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  APPEARANCE_STORAGE_KEY,
  applyThemeToDocument,
  persistAppearance,
  readAppearancePreference,
  resolveTheme,
  type AppearancePreference,
} from "../lib/appearance";
import { ApiStatusBar } from "../components/ApiStatusBar";
import { OfflineBanner } from "../components/OfflineBanner";
import { WorkspaceSwitcher } from "../components/WorkspaceSwitcher";
import { OrgSwitcher } from "../components/OrgSwitcher";
import { PlatformBaseSwitcher } from "../components/PlatformBaseSwitcher";
import { EnvReadonlyBadge } from "../components/EnvReadonlyBadge";
import { getTenant } from "../api/tenant";
import { DEMO_VERSION, findNavPage, isNavPage, NAV_ITEMS } from "../nav";
import { NavIcon } from "./icons";
import type { NavItem, NavSection } from "../nav";
import {
  persistOpsNavOpen,
  resolveOpsNavDefaultOpen,
} from "../lib/opsNav";

const APPEARANCE_OPTS: {
  id: AppearancePreference;
  label: string;
  icon: "sun" | "moon" | "monitor";
}[] = [
  { id: "light", label: "浅色", icon: "sun" },
  { id: "dark", label: "深色", icon: "moon" },
  { id: "system", label: "跟随系统", icon: "monitor" },
];

export function AppShell() {
  const [pref, setPref] = useState<AppearancePreference>(() =>
    readAppearancePreference(),
  );
  const [menuOpen, setMenuOpen] = useState(false);
  const [opsNavOpen, setOpsNavOpen] = useState(() =>
    resolveOpsNavDefaultOpen(getTenant().roles),
  );
  const [workspaceKey, setWorkspaceKey] = useState(
    () => `${getTenant().orgId}:${getTenant().projectId}`,
  );
  const menuRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const active = findNavPage(location.pathname);
  const onApolloRoute = location.pathname.startsWith("/apollo");
  const showOpsPages = opsNavOpen || onApolloRoute;

  const [systemDark, setSystemDark] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches,
  );

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setSystemDark(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    applyThemeToDocument(resolveTheme(pref, systemDark));
    document.documentElement.setAttribute("data-aos-appearance", pref);
  }, [pref, systemDark]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => {
    function onWs(e: Event) {
      const d = (e as CustomEvent).detail as {
        orgId?: string;
        projectId?: string;
      };
      if (d?.orgId && d?.projectId) {
        setWorkspaceKey(`${d.orgId}:${d.projectId}`);
      } else {
        const t = getTenant();
        setWorkspaceKey(`${t.orgId}:${t.projectId}`);
      }
    }
    window.addEventListener("aos-workspace-changed", onWs);
    return () => window.removeEventListener("aos-workspace-changed", onWs);
  }, []);

  useEffect(() => {
    function onExpand() {
      setOpsNavOpen(true);
      persistOpsNavOpen(true);
      console.info("[aos-ops-nav]", { event: "expanded_via_ui14" });
    }
    window.addEventListener("aos-ops-nav-expand", onExpand);
    return () => window.removeEventListener("aos-ops-nav-expand", onExpand);
  }, []);

  // /v1/me 写入 roles 后：仅在无手动偏好时按桌面+角色纠正默认
  useEffect(() => {
    function refreshDefault() {
      try {
        if (localStorage.getItem("aos-ops-nav-open-v1") != null) return;
      } catch {
        /* ignore */
      }
      setOpsNavOpen(resolveOpsNavDefaultOpen(getTenant().roles));
    }
    refreshDefault();
    window.addEventListener("aos-tenant-updated", refreshDefault);
    return () => window.removeEventListener("aos-tenant-updated", refreshDefault);
  }, []);

  const crumbs = useMemo(
    () => active?.crumbs ?? ["工作区", "AOS 概览"],
    [active],
  );

  function onAppearanceChange(next: AppearancePreference) {
    setPref(next);
    persistAppearance(next);
    setMenuOpen(false);
  }

  const navNodes: ReactNode[] = [];
  let hideOpsPages = false;
  for (let idx = 0; idx < NAV_ITEMS.length; idx++) {
    const item: NavItem = NAV_ITEMS[idx];
    if (!isNavPage(item)) {
      const sec = item as NavSection;
      hideOpsPages = Boolean(sec.collapseDefault) && !showOpsPages;
      if (sec.collapseDefault) {
        navNodes.push(
          <button
            key={`sec-${idx}`}
            type="button"
            className="aos-nav-section aos-nav-section-toggle"
            aria-expanded={showOpsPages}
            onClick={() =>
              setOpsNavOpen((v) => {
                const next = !v;
                persistOpsNavOpen(next);
                return next;
              })
            }
          >
            <span>{sec.section}</span>
            <span className="aos-nav-ops-meta">
              运维面 · {showOpsPages ? "收起" : "展开"}
            </span>
          </button>,
        );
      } else {
        navNodes.push(
          <div key={`sec-${idx}`} className="aos-nav-section">
            {sec.section}
          </div>,
        );
      }
      continue;
    }
    if (hideOpsPages) continue;
    navNodes.push(
      <NavLink
        key={item.id}
        to={item.path}
        data-nav-id={item.id}
        data-nav-status={item.status}
        className={({ isActive }) =>
          isActive ? "aos-nav-link is-active" : "aos-nav-link"
        }
        end={item.path === "/"}
      >
        <NavIcon name={item.icon} />
        <span className="aos-nav-label">{item.label}</span>
        {item.status === "s2" ? (
          <span className="aos-nav-badge" title="导航占位">
            占位
          </span>
        ) : null}
      </NavLink>,
    );
  }

  return (
    <div className="layout">
      <aside className="aside">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden>
            <NavIcon name="layers" className="brand-mark-icon" />
          </div>
          <div>
            <div className="brand-title">AI操作系统</div>
            <div className="brand-sub">AOS 企业AI转型方案</div>
          </div>
        </div>
        <nav className="nav" aria-label="主导航">
          {navNodes}
        </nav>
        <div className="aside-foot">AOS · {DEMO_VERSION}</div>
      </aside>

      <div className="main">
        <header className="topbar">
          <nav className="breadcrumb" aria-label="面包屑">
            {crumbs.map((c, i) => (
              <span key={`${c}-${i}`} className="breadcrumb-item">
                {i > 0 ? (
                  <NavIcon name="chevron" className="breadcrumb-chevron" />
                ) : null}
                <span className={i === crumbs.length - 1 ? "aos-text" : "aos-muted"}>
                  {c}
                </span>
              </span>
            ))}
          </nav>
          <div className="topbar-actions">
            <EnvReadonlyBadge />
            <OrgSwitcher />
            <WorkspaceSwitcher />
            <PlatformBaseSwitcher />
            <div className="top-search" aria-hidden>
              <NavIcon name="search" className="top-search-icon" />
              <input type="search" placeholder="搜索资源…" disabled />
            </div>
            <div className="aos-appearance" ref={menuRef}>
              <button
                type="button"
                className="aos-appearance-btn"
                aria-label="外观"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((v) => !v)}
              >
                <NavIcon
                  name={
                    APPEARANCE_OPTS.find((o) => o.id === pref)?.icon ?? "monitor"
                  }
                />
                外观
              </button>
              {menuOpen ? (
                <div className="aos-appearance-menu" role="menu">
                  {APPEARANCE_OPTS.map((o) => (
                    <button
                      key={o.id}
                      type="button"
                      role="menuitem"
                      className={
                        pref === o.id
                          ? "aos-appearance-item is-selected"
                          : "aos-appearance-item"
                      }
                      onClick={() => onAppearanceChange(o.id)}
                    >
                      <NavIcon name={o.icon} />
                      {o.label}
                      <span className="aos-check">✓</span>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </header>
        <OfflineBanner />
        <ApiStatusBar />
        <div className="content">
          <Outlet key={workspaceKey} />
        </div>
      </div>
      <span className="sr-only" data-appearance-key={APPEARANCE_STORAGE_KEY} />
    </div>
  );
}
