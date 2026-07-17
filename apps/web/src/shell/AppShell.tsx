import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  APPEARANCE_STORAGE_KEY,
  applyThemeToDocument,
  persistAppearance,
  readAppearancePreference,
  resolveTheme,
  type AppearancePreference,
} from "../lib/appearance";
import { DEMO_VERSION, findNavPage, isNavPage, NAV_ITEMS } from "../nav";
import { NavIcon } from "./icons";

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
  const menuRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const active = findNavPage(location.pathname);

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

  const crumbs = useMemo(
    () => active?.crumbs ?? ["概览"],
    [active],
  );

  function onAppearanceChange(next: AppearancePreference) {
    setPref(next);
    persistAppearance(next);
    setMenuOpen(false);
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
          {NAV_ITEMS.map((item, idx) =>
            isNavPage(item) ? (
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
                  <span className="aos-nav-badge" title="蓝图占位 · T-UI S2">
                    S2
                  </span>
                ) : null}
              </NavLink>
            ) : (
              <div key={`sec-${idx}`} className="aos-nav-section">
                {item.section}
              </div>
            ),
          )}
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
        <div className="content">
          <Outlet />
        </div>
      </div>
      <span className="sr-only" data-appearance-key={APPEARANCE_STORAGE_KEY} />
    </div>
  );
}
