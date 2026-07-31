export type NavSection = {
  section: string;
  /** 默认折叠（如运维交付） */
  collapseDefault?: boolean;
};

export type NavSubgroup = {
  subgroup: string;
};

export type NavPage = {
  id: string;
  path: string;
  label: string;
  icon: IconName;
  /** live = React 已接线；s2 = 蓝图占位（T-UI S2） */
  status: "live" | "s2";
  crumbs?: string[];
  /** hidden = 不在侧边栏渲染，但路由保留 */
  hidden?: boolean;
};

export type NavItem = NavSection | NavSubgroup | NavPage;

export type IconName =
  | "home"
  | "apps"
  | "layers"
  | "inbox"
  | "graph"
  | "chat"
  | "ontology"
  | "server"
  | "stairs"
  | "plug"
  | "plus-circle"
  | "spark"
  | "film"
  | "wrench"
  | "workflow"
  | "git"
  | "check"
  | "funnel"
  | "heart"
  | "wiki"
  | "bell"
  | "table"
  | "chevron"
  | "sun"
  | "moon"
  | "monitor"
  | "search"
  | "menu"
  | "clock"
  | "folder"
  | "database"
  | "user"
  | "star"
  | "close"
  | "trash"
  | "sync"
  | "route"
  | "activity"
  | "eye";
