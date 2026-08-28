import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
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
import { getTheme, toggleTheme, type Theme } from "../theme";
import { ApiStatusBar } from "../components/ApiStatusBar";
import { OfflineBanner } from "../components/OfflineBanner";
import { WorkspaceSwitcher } from "../components/WorkspaceSwitcher";
import { OrgSwitcher } from "../components/OrgSwitcher";
import { PlatformBaseSwitcher } from "../components/PlatformBaseSwitcher";
import { EnvReadonlyBadge } from "../components/EnvReadonlyBadge";
import { getTenant } from "../api/tenant";
import {
  DEMO_VERSION,
  findNavPage,
  isNavPage,
  isNavSubgroup,
  NAV_ITEMS,
  workshopModuleNavPage,
} from "../nav";
import { NavIcon } from "./icons";
import type { IconName, NavPage } from "../nav";
import { OPS_NAV_SECTION } from "../lib/productCopy";
import {
  InstalledModuleNavigation,
  WORKSHOP_FOCUS_EVENT,
  findInstalledWorkshopRoute,
  isReplacedLegacyWorkshopRoute,
  useEcommerceWorkshopCatalog,
} from "../components/workshop";

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

  if (pathname === "/workshop/analyst") {
    const links: Array<{ to: string; icon: IconName; label: string }> = [
      { to: "/workshop/cockpit", icon: "monitor", label: "日常总控" },
      { to: "/workshop/operations", icon: "inbox", label: "运营驾驶舱" },
      { to: "/workshop/price-governance", icon: "activity", label: "价格治理" },
      { to: "/workshop/customer", icon: "user", label: "客户关系" },
      { to: "/workshop/buddy", icon: "chat", label: "Buddy" },
      { to: "/workshop/analyst", icon: "layers", label: "经营参谋" },
    ];
    return <nav className="p-nav-global analyst-exact-global" aria-label="全局导航">
      <div className="analyst-exact-global-brand"><NavIcon name="plus-circle" /><span>AOS</span></div>
      <div className="analyst-exact-global-links">{links.map((item) => <NavLink key={item.to} to={item.to} end title={item.label} aria-label={item.label} className={({ isActive }) => `analyst-exact-global-item${isActive ? " is-active" : ""}`}><NavIcon name={item.icon} /></NavLink>)}</div>
      <div className="analyst-exact-global-bottom">
        <button type="button" className="analyst-exact-global-item" title="帮助" aria-label="帮助"><NavIcon name="wrench" /></button>
        <UserMenu pref={pref} onAppearanceChange={onAppearanceChange} />
      </div>
    </nav>;
  }

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

/** 用户菜单下拉 —— 含工作区成员/我的资料/组织切换/平台地址/环境状态 + 外观切换 */
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
          <div className="p-user-menu-subheader">工作空间</div>
          <OrgSwitcher />
          <PlatformBaseSwitcher />
          <EnvReadonlyBadge />
          <div style={{ borderTop: "1px solid var(--aos-border)", margin: "4px 0" }} />
          <div className="p-user-menu-subheader">外观</div>
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

const ANALYST_VISUAL_WORKSHOP_LINKS: Array<{ to: string; label: string; icon: IconName }> = [
  { to: "/workshop/cockpit", label: "日常任务总控大屏", icon: "monitor" },
  { to: "/workshop/content-campaign", label: "内容与活动工作台", icon: "table" },
  { to: "/workshop/operations", label: "统一运营驾驶舱", icon: "inbox" },
  { to: "/workshop/creator-growth", label: "达人邀约驾驶舱", icon: "user" },
  { to: "/workshop/media-studio", label: "多媒体内容生产", icon: "film" },
  { to: "/workshop/analyst", label: "经营参谋 · 增长指挥中心", icon: "layers" },
  { to: "/workshop/price-governance", label: "价格治理驾驶舱", icon: "activity" },
  { to: "/workshop/customer", label: "客户关系工作台", icon: "user" },
];

function AnalystVisualNavigation() {
  const item = ({ to, label, icon }: { to: string; label: string; icon: IconName }) => <NavLink key={to} to={to} end className={({ isActive }) => `analyst-exact-side-item${isActive ? " is-active" : ""}`}><NavIcon name={icon} /><span>{label}</span></NavLink>;
  return <nav className="analyst-exact-side-nav" aria-label="经营参谋视觉稿主导航">
    <div className="analyst-exact-side-title">工作台</div>
    <div className="analyst-exact-side-section">{ANALYST_VISUAL_WORKSHOP_LINKS.map(item)}</div>
    <div className="analyst-exact-side-section">{item({ to: "/workshop/buddy", label: "Buddy · 智能助手", icon: "chat" })}</div>
    <div className="analyst-exact-side-title">应用程序构建工具</div>
    <div className="analyst-exact-side-section">
      {item({ to: "/workshop/canvas", label: "画布编辑", icon: "layers" })}
      {item({ to: "/workshop/graph", label: "对象探索", icon: "graph" })}
    </div>
    <div className="analyst-exact-side-title">AIP 决策引擎</div>
    <div className="analyst-exact-side-section">
      {item({ to: "/aip/logic", label: "AIP 逻辑画布", icon: "workflow" })}
      {item({ to: "/aip/drafts", label: "Draft 审批台", icon: "inbox" })}
    </div>
  </nav>;
}

type WorkshopVisualHeaderSpec = {
  brand?: string;
  title: string;
  crumb?: string;
  search?: string;
  context?: string;
  actions: string[];
};

const WORKSHOP_VISUAL_HEADERS: Record<string, WorkshopVisualHeaderSpec> = {
  "/workshop/operations": { brand: "栖月汇微商城", title: "统一运营驾驶舱", search: "搜索订单号、SKU、告警关键词…", actions: ["筛选", "＋ 新建处理"] },
  "/workshop/content-campaign": { brand: "栖月汇微商城", title: "内容与活动工作台", search: "搜索活动、内容、商品…", actions: ["保存草稿", "批准并发布"] },
  "/workshop/creator-growth": { brand: "栖月汇微商城", title: "达人邀约驾驶舱", search: "搜索达人、机构、邀约记录…", actions: ["导入达人", "＋ 新建邀约批次"] },
  "/workshop/media-studio": { brand: "栖月汇微商城", title: "多媒体内容生产", search: "搜索文案、视频、直播任务…", context: "栖月汇微商城", actions: ["查看内容计划", "＋ 新建内容任务"] },
  "/workshop/price-governance": { title: "价格治理驾驶舱", crumb: "工作台 › 增长引擎域 › 价格治理", context: "栖月汇微商城", actions: ["导出报告", "＋ 新建监测策略"] },
  "/workshop/customer": { title: "客户关系工作台", crumb: "工作台 › 运营执行域 › 客户关系", context: "栖月汇微商城 · 客户待核对", actions: ["导入客户", "＋ 新建触达任务"] },
};

function WorkshopPrimaryVisualHeader({ pathname }: { pathname: string }) {
  const spec = WORKSHOP_VISUAL_HEADERS[pathname];
  const navigate = useNavigate();
  const searchRef = useRef<HTMLInputElement>(null);
  const [actionNotice, setActionNotice] = useState("");
  if (!spec) return null;
  const runHeaderAction = (label: string) => {
    setActionNotice("");
    if (label === "筛选") { searchRef.current?.focus(); return; }
    if (label === "查看内容计划") { navigate("/workshop/content-campaign"); return; }
    const noun = label.replace(/^＋\s*/, "");
    setActionNotice(`${noun}预检已打开：当前没有可提交的正式业务数据，页面不会创建记录或触发外部操作。`);
  };
  return <>
    <div className="workshop-visual-header-left">
      {spec.title === "价格治理驾驶舱" || spec.title === "客户关系工作台" ? <h1>{spec.title}</h1> : null}
      {spec.brand ? <strong>{spec.brand}</strong> : null}
      {spec.brand || spec.crumb ? <span>/</span> : null}
      {spec.crumb ? <span>{spec.crumb}</span> : null}
      {spec.crumb && spec.title !== "价格治理驾驶舱" && spec.title !== "客户关系工作台" ? <span>/</span> : null}
      {spec.title !== "价格治理驾驶舱" && spec.title !== "客户关系工作台" ? <b>{spec.title}</b> : null}
    </div>
    {spec.search ? <label className="workshop-visual-header-search"><NavIcon name="search" /><input ref={searchRef} type="search" placeholder={spec.search} /></label> : <div />}
    <div className="workshop-visual-header-actions">
      {spec.context ? <span>{spec.context}</span> : null}
      {spec.actions.map((label, index) => <button key={label} type="button" className={index === spec.actions.length - 1 ? "is-primary" : ""} title={label === "筛选" ? "聚焦当前页只读检索" : label === "查看内容计划" ? "打开内容与活动工作台" : "打开安全预检，不写入业务数据"} onClick={() => runHeaderAction(label)}>{label}</button>)}
      {actionNotice ? <span className="workshop-header-action-notice" role="status">{actionNotice}<button type="button" aria-label="关闭操作提示" onClick={() => setActionNotice("")}>×</button></span> : null}
    </div>
  </>;
}

export function AppShell() {
  const [pref, setPref] = useState<AppearancePreference>(() =>
    readAppearancePreference(),
  );
  const [workspaceKey, setWorkspaceKey] = useState(
    () => `${getTenant().orgId}:${getTenant().projectId}`,
  );
  const location = useLocation();
  const contentRef = useRef<HTMLDivElement>(null);
  const workshopCatalog = useEcommerceWorkshopCatalog();
  const activeWorkshop = findInstalledWorkshopRoute(
    workshopCatalog.modules,
    location.pathname,
  );
  const staticActive = findNavPage(location.pathname);
  const unresolvedWorkshopRoute =
    !activeWorkshop &&
    location.pathname.startsWith("/workshop/") &&
    staticActive?.path === "/workshop";
  const active = activeWorkshop
    ? workshopModuleNavPage(activeWorkshop.module)
    : unresolvedWorkshopRoute
      ? undefined
      : staticActive;
  const onApolloRoute = location.pathname.startsWith("/apollo");
  const onAnalystVisualRoute = location.pathname === "/workshop/analyst";
  const onTaskCockpitVisualRoute = location.pathname === "/workshop/cockpit";
  const onWorkshopPrimaryVisualRoute = ["/workshop/cockpit", "/workshop/operations", "/workshop/content-campaign", "/workshop/creator-growth", "/workshop/media-studio", "/workshop/analyst", "/workshop/price-governance", "/workshop/customer"].includes(location.pathname);
  const onWorkshopFullSidebarVisualRoute = onWorkshopPrimaryVisualRoute;
  const onWorkshopMappedHeaderRoute = Boolean(WORKSHOP_VISUAL_HEADERS[location.pathname]);
  const cockpitDateLabel = new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", weekday: "short" }).format(new Date());

  const { collapsed: sidebarCollapsed, toggle: toggleSidebar } =
    useSidebarCollapsed();
  const { collapsed: collapsedSections, toggle: toggleSection, expand: expandSection } =
    useCollapsedSections();

  const [systemDark, setSystemDark] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches,
  );
  const [workshopFocusMode, setWorkshopFocusMode] = useState(false);

  useLayoutEffect(() => {
    const content = contentRef.current;
    if (!content) return;
    content.scrollTop = 0;
    content.scrollLeft = 0;
  }, [location.pathname, workspaceKey]);

  useEffect(() => {
    const onFocusMode = (event: Event) => {
      const detail = (event as CustomEvent<{ active?: boolean }>).detail;
      setWorkshopFocusMode(detail?.active === true);
    };
    window.addEventListener(WORKSHOP_FOCUS_EVENT, onFocusMode);
    return () => window.removeEventListener(WORKSHOP_FOCUS_EVENT, onFocusMode);
  }, []);

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
    () => active?.crumbs ?? (
      unresolvedWorkshopRoute
        ? ["工作台", "电商工作台"]
        : ["工作区", "AOS 概览"]
    ),
    [active, unresolvedWorkshopRoute],
  );

  const onAppearanceChange = useCallback((next: AppearancePreference) => {
    setPref(next);
    persistAppearance(next);
  }, []);

  // 顶栏快捷主题切换按钮：light/dark 二态切换（不影响 system 偏好）
  const [topbarTheme, setTopbarTheme] = useState<Theme>(() => getTheme());
  const onToggleTopbarTheme = useCallback(() => {
    const next = toggleTheme();
    setTopbarTheme(next);
    // 同步 pref 状态（如果之前是 system，切换后变成明确的 light/dark）
    setPref(next);
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
            {key === "工作台" ? <InstalledModuleNavigation /> : null}
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
        end
        className={() =>
          active?.id === item.id ? "aos-nav-link is-active" : "aos-nav-link"
        }
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

    const renderSubgroup = (label: string) => (
      <div key={`sub-${label}`} className="aos-nav-subgroup">
        {label}
      </div>
    );

    for (const item of NAV_ITEMS) {
      if (isNavSubgroup(item)) {
        // subgroup：添加到当前分组的页面列表中
        if (currentSectionKey !== null) {
          currentSectionPages.push(renderSubgroup(item.subgroup));
        }
      } else if (!isNavPage(item)) {
        // section：遇到新分组，先 flush 上一组
        if (currentSectionKey !== null) {
          flushSection(currentSectionKey, currentSectionPages);
          currentSectionPages = [];
        }
        currentSectionKey = item.section;
      } else {
        // page：hidden 页面不在侧边栏渲染，但路由保留
        if (item.hidden) continue;
        if (
          isReplacedLegacyWorkshopRoute(workshopCatalog.modules, item.path)
        ) continue;
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
  }, [collapsedSections, toggleSection, active?.id, workshopCatalog.modules]);

  return (
    <div className={`p-app${workshopFocusMode ? " is-workshop-focus" : ""}${onWorkshopPrimaryVisualRoute ? " is-workshop-primary-visual" : ""}${onAnalystVisualRoute ? " is-analyst-visual" : ""}${onTaskCockpitVisualRoute ? " is-task-cockpit-visual" : ""}`}>
      <GlobalNav
        onToggleSidebar={toggleSidebar}
        pathname={location.pathname}
        pref={pref}
        onAppearanceChange={onAppearanceChange}
      />
      <div className="p-main">
        <header className="topbar">
          {onAnalystVisualRoute ? <>
            <div className="analyst-exact-header-left">
              <h1>经营参谋 · 增长指挥中心</h1>
              <span>工作台 › 增长指挥域 › 经营参谋</span>
            </div>
            <div className="analyst-exact-header-right">
              <label><span>渠道视角</span><select aria-label="渠道视角" defaultValue=""><option value="">渠道未知</option></select></label>
              <span className="analyst-exact-owner" title="经营参谋（负责人未绑定）">经营参谋（负责人未绑定）</span>
              <button type="button" onClick={() => document.getElementById("analyst-tab-plan")?.click()}><NavIcon name="table" />查看今日方案</button>
            </div>
          </> : onTaskCockpitVisualRoute ? <>
            <div className="task-cockpit-exact-header-left"><strong>栖月汇微商城</strong><span>/</span><b>日常任务总控大屏</b></div>
            <div className="task-cockpit-exact-header-search"><NavIcon name="search" /><input type="search" placeholder="搜索任务、同事、关键词…" /></div>
            <div className="task-cockpit-exact-header-right"><span>{cockpitDateLabel}</span><button type="button" onClick={() => window.dispatchEvent(new CustomEvent("aos-workshop-cockpit-calendar"))}><NavIcon name="table" />日历视图</button></div>
          </> : onWorkshopMappedHeaderRoute ? <WorkshopPrimaryVisualHeader key={location.pathname} pathname={location.pathname} /> : <><div className="topbar-left">
            <nav className="breadcrumb" aria-label="面包屑">
              {crumbs.map((c, i) => (
                <span key={`${c}-${i}`} className="breadcrumb-item">
                  {i > 0 ? (
                    <span className="breadcrumb-sep">/</span>
                  ) : null}
                  <span className={i === crumbs.length - 1 ? "aos-text" : "aos-muted"}>
                    {c}
                  </span>
                </span>
              ))}
            </nav>
          </div>
          <div className="topbar-center">
            <div className="top-search">
              <NavIcon name="search" className="top-search-icon" />
              <input type="search" placeholder="搜索资源…" />
            </div>
          </div>
          <div className="topbar-right">
            <div className="topbar-actions">
              <OrgSwitcher />
              <WorkspaceSwitcher />
              <button
                type="button"
                className="topbar-theme-toggle"
                title={topbarTheme === "dark" ? "切换到浅色主题" : "切换到深色主题"}
                aria-label="切换主题"
                onClick={onToggleTopbarTheme}
              >
                <NavIcon name={topbarTheme === "dark" ? "sun" : "moon"} />
              </button>
            </div>
          </div>
          </>}
        </header>
        <div className="layout">
          <aside className={`aside${sidebarCollapsed ? " is-collapsed" : ""}`}>
            <button
              type="button"
              className="aside-toggle"
              title="折叠/展开侧栏"
              aria-label={sidebarCollapsed ? "展开侧栏" : "折叠侧栏"}
              aria-expanded={!sidebarCollapsed}
              onClick={toggleSidebar}
            >
              <NavIcon name="chevron" />
            </button>
            {onWorkshopFullSidebarVisualRoute ? null : <div className="brand-block">
              <div className="brand-mark" aria-hidden>
                <NavIcon name="layers" className="brand-mark-icon" />
              </div>
              <div>
                <div className="brand-title">AI操作系统</div>
                <div className="brand-sub">AOS 企业AI转型方案</div>
              </div>
            </div>}
            {onWorkshopFullSidebarVisualRoute ? <AnalystVisualNavigation /> : <nav className="nav" aria-label="主导航">
              {navNodes}
            </nav>}
            {onWorkshopFullSidebarVisualRoute ? null : <div className="aside-foot">AOS · {DEMO_VERSION}</div>}
          </aside>
          <main className="main">
            <OfflineBanner />
            <ApiStatusBar />
            <div className="content" ref={contentRef}>
              <Outlet key={workspaceKey} />
            </div>
          </main>
        </div>
      </div>
      <span className="sr-only" data-appearance-key={APPEARANCE_STORAGE_KEY} />
    </div>
  );
}
