import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
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
import type { IconName, NavPage } from "../nav";
import { OPS_NAV_SECTION } from "../lib/productCopy";

const APPEARANCE_OPTS: {
  id: AppearancePreference;
  label: string;
  icon: "sun" | "moon" | "monitor";
}[] = [
  { id: "light", label: "浅色", icon: "sun" },
  { id: "dark", label: "深色", icon: "moon" },
  { id: "system", label: "跟随系统", icon: "monitor" },
];

// 侧边栏折叠状态 localStorage key
const SIDEBAR_KEY = "aos:sidebar-collapsed";
// 分组抽屉折叠状态 localStorage key（JSON 数组）
const SECTIONS_KEY = "aos:nav-sections-collapsed";

/** 侧边栏折叠/展开 —— 偏好存 localStorage */
function useSidebarCollapsed() {
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem(SIDEBAR_KEY) === "1";
  });
  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(SIDEBAR_KEY, next ? "1" : "0");
      return next;
    });
  }, []);
  return { collapsed, toggle };
}

/** 分组抽屉式折叠 —— collapseDefault 的分组默认折叠，用户偏好存 localStorage */
function useCollapsedSections() {
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    // 初始化：collapseDefault 的分组默认折叠
    const defaults = new Set<string>();
    for (const item of NAV_ITEMS) {
      if ("section" in item && item.collapseDefault) {
        defaults.add(item.section);
      }
    }
    // 从 localStorage 恢复用户偏好
    try {
      const saved = JSON.parse(localStorage.getItem(SECTIONS_KEY) || "[]");
      return new Set(saved.length > 0 ? saved : defaults);
    } catch {
      return defaults;
    }
  });

  const toggle = useCallback((section: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      localStorage.setItem(SECTIONS_KEY, JSON.stringify([...next]));
      return next;
    });
  }, []);

  // 展开指定分组（不 toggle，兼容外部 aos-ops-nav-expand 事件 / apollo 路由）
  const expand = useCallback((section: string) => {
    setCollapsed((prev) => {
      if (!prev.has(section)) return prev;
      const next = new Set(prev);
      next.delete(section);
      localStorage.setItem(SECTIONS_KEY, JSON.stringify([...next]));
      return next;
    });
  }, []);

  return { collapsed, toggle, expand };
}

/** 全局深色导航栏 —— 左侧 48px 窄条，上半部分功能图标，下半部分帮助+用户 */
function GlobalNav({
  onToggleSidebar,
  pathname,
  pref,
  onAppearanceChange,
}: {
  onToggleSidebar: () => void;
  pathname: string;
  pref: AppearancePreference;
  onAppearanceChange: (next: AppearancePreference) => void;
}) {
  const navigate = useNavigate();

  // 上半部分图标：menu 切换侧栏，home 回首页，其余装饰性
  const topItems: {
    icon: IconName;
    label: string;
    active?: boolean;
    onClick?: () => void;
  }[] = [
    { icon: "menu", label: "菜单", onClick: onToggleSidebar },
    { icon: "home", label: "首页", active: pathname === "/", onClick: () => navigate("/") },
    { icon: "search", label: "搜索" },
    { icon: "bell", label: "通知" },
    { icon: "clock", label: "历史" },
    { icon: "folder", label: "项目" },
    { icon: "apps", label: "应用", active: pathname.startsWith("/workshop") },
    { icon: "database", label: "数据", active: pathname.startsWith("/data") },
  ];

  return (
    <nav className="p-nav-global" aria-label="全局导航">
      <div className="p-nav-global-top">
        {topItems.map((it) => (
          <button
            key={it.icon}
            type="button"
            className={`p-nav-g-item${it.active ? " is-active" : ""}`}
            title={it.label}
            onClick={it.onClick}
          >
            <NavIcon name={it.icon} />
          </button>
        ))}
      </div>
      <div className="p-nav-global-bottom">
        <button type="button" className="p-nav-g-item" title="帮助">
          <NavIcon name="wrench" />
        </button>
        <UserMenu pref={pref} onAppearanceChange={onAppearanceChange} />
      </div>
    </nav>
  );
}

/** 用户菜单下拉 —— 含工作区成员/我的资料/组织与加入 + 外观切换 */
function UserMenu({
  pref,
  onAppearanceChange,
}: {
  pref: AppearancePreference;
  onAppearanceChange: (next: AppearancePreference) => void;
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // 点击菜单外部关闭
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!menuRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const handleAppearance = useCallback(
    (next: AppearancePreference) => {
      onAppearanceChange(next);
      setOpen(false);
    },
    [onAppearanceChange],
  );

  return (
    <div ref={menuRef} style={{ position: "relative" }}>
      <button
        type="button"
        className="p-nav-g-item"
        title="用户"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <NavIcon name="user" />
      </button>
      {open ? (
        <div className="p-user-menu" role="menu">
          <Link
            className="p-user-menu-item"
            to="/workspace/members"
            onClick={() => setOpen(false)}
          >
            工作区成员
          </Link>
          <Link
            className="p-user-menu-item"
            to="/settings/profile"
            onClick={() => setOpen(false)}
          >
            我的资料
          </Link>
          <Link
            className="p-user-menu-item"
            to="/org/membership"
            onClick={() => setOpen(false)}
          >
            组织与加入
          </Link>
          <div style={{ borderTop: "1px solid var(--aos-border)", margin: "4px 0" }} />
          {APPEARANCE_OPTS.map((o) => (
            <button
              key={o.id}
              type="button"
              role="menuitem"
              className={`p-user-menu-item${pref === o.id ? " is-selected" : ""}`}
              onClick={() => handleAppearance(o.id)}
            >
              <NavIcon name={o.icon} />
              {o.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function AppShell() {
  const [pref, setPref] = useState<AppearancePreference>(() =>
    readAppearancePreference(),
  );
  const [workspaceKey, setWorkspaceKey] = useState(
    () => `${getTenant().orgId}:${getTenant().projectId}`,
  );
  const location = useLocation();
  const active = findNavPage(location.pathname);
  const onApolloRoute = location.pathname.startsWith("/apollo");

  const { collapsed: sidebarCollapsed, toggle: toggleSidebar } =
    useSidebarCollapsed();
  const { collapsed: collapsedSections, toggle: toggleSection, expand: expandSection } =
    useCollapsedSections();

  const [systemDark, setSystemDark] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches,
  );

  // 外观：监听系统主题变化
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setSystemDark(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  // 外观：应用到文档
  useEffect(() => {
    applyThemeToDocument(resolveTheme(pref, systemDark));
    document.documentElement.setAttribute("data-aos-appearance", pref);
  }, [pref, systemDark]);

  // 工作区切换：监听 aos-workspace-changed 事件
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

  // 兼容外部 expandOpsNav() 调用：展开运维交付分组
  useEffect(() => {
    function onExpand() {
      expandSection(OPS_NAV_SECTION);
    }
    window.addEventListener("aos-ops-nav-expand", onExpand);
    return () => window.removeEventListener("aos-ops-nav-expand", onExpand);
  }, [expandSection]);

  // /apollo 路由下自动展开运维交付分组，避免当前页所属分组被折叠
  useEffect(() => {
    if (onApolloRoute) {
      expandSection(OPS_NAV_SECTION);
    }
  }, [onApolloRoute, expandSection]);

  const crumbs = useMemo(
    () => active?.crumbs ?? ["工作区", "AOS 概览"],
    [active],
  );

  const onAppearanceChange = useCallback((next: AppearancePreference) => {
    setPref(next);
    persistAppearance(next);
  }, []);

  // 侧边栏导航渲染：跳过 hidden 页面，所有分组使用抽屉式折叠
  const navNodes = useMemo(() => {
    const nodes: ReactNode[] = [];
    let currentSectionKey: string | null = null;
    let currentSectionPages: ReactNode[] = [];

    const flushSection = (key: string, pages: ReactNode[]) => {
      const isCollapsed = collapsedSections.has(key);
      nodes.push(
        <div key={`sec-${key}`} className="aos-nav-section-wrap">
          <button
            type="button"
            className={`aos-nav-section-toggle${isCollapsed ? " is-collapsed" : ""}`}
            aria-expanded={!isCollapsed}
            onClick={() => toggleSection(key)}
          >
            <span>{key}</span>
            <NavIcon name="chevron" className="aos-nav-section-arrow" />
          </button>
          <div
            className={`aos-nav-section-content${isCollapsed ? " is-collapsed" : ""}`}
          >
            {pages}
          </div>
        </div>,
      );
    };

    const renderPage = (item: NavPage) => (
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
      </NavLink>
    );

    for (const item of NAV_ITEMS) {
      if (!isNavPage(item)) {
        // 遇到新分组：先 flush 上一组
        if (currentSectionKey !== null) {
          flushSection(currentSectionKey, currentSectionPages);
          currentSectionPages = [];
        }
        currentSectionKey = item.section;
      } else {
        // hidden 页面不在侧边栏渲染，但路由保留
        if (item.hidden) continue;
        if (currentSectionKey === null) {
          // 不属于任何分组的页面（如概览）直接渲染
          nodes.push(renderPage(item));
        } else {
          currentSectionPages.push(renderPage(item));
        }
      }
    }
    // flush 最后一组
    if (currentSectionKey !== null) {
      flushSection(currentSectionKey, currentSectionPages);
    }

    return nodes;
  }, [collapsedSections, toggleSection]);

  return (
    <div className="p-app">
      <GlobalNav
        onToggleSidebar={toggleSidebar}
        pathname={location.pathname}
        pref={pref}
        onAppearanceChange={onAppearanceChange}
      />
      <div className="p-main">
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
          <div className="top-search" aria-hidden>
            <NavIcon name="search" className="top-search-icon" />
            <input type="search" placeholder="搜索资源…" disabled />
          </div>
          <div className="topbar-actions">
            <EnvReadonlyBadge />
            <OrgSwitcher />
            <WorkspaceSwitcher />
            <PlatformBaseSwitcher />
          </div>
        </header>
        <div className="layout">
          <aside className={`aside${sidebarCollapsed ? " is-collapsed" : ""}`}>
            <button
              type="button"
              className="aside-toggle"
              title="折叠/展开侧栏"
              onClick={toggleSidebar}
            >
              <NavIcon name="chevron" />
            </button>
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
          <main className="main">
            <OfflineBanner />
            <ApiStatusBar />
            <div className="content">
              <Outlet key={workspaceKey} />
            </div>
          </main>
        </div>
      </div>
      <span className="sr-only" data-appearance-key={APPEARANCE_STORAGE_KEY} />
    </div>
  );
}
