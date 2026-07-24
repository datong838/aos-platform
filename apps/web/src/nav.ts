/** Side-nav narrative — order locked to foundry/html + product sections (运维交付收口见 163) */
import { LOCAL_PLATFORM_NAME, OPS_NAV_SECTION } from "./lib/productCopy";

export type NavSection = {
  section: string;
  /** 默认折叠（如运维交付） */
  collapseDefault?: boolean;
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
export type NavItem = NavSection | NavPage;

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
  | "activity";

export const NAV_ITEMS: NavItem[] = [
  { id: "index", path: "/", label: "概览", icon: "home", status: "live", crumbs: ["工作区", "AOS 概览"] },

  // hidden pages — 路由保留，不在侧边栏渲染，通过全局导航用户菜单访问
  {
    id: "workspace-members",
    path: "/workspace/members",
    label: "工作区成员",
    icon: "apps",
    status: "live",
    crumbs: ["工作区", "成员"],
    hidden: true,
  },
  {
    id: "my-profile",
    path: "/settings/profile",
    label: "我的资料",
    icon: "user",
    status: "live",
    crumbs: ["工作区", "我的资料"],
    hidden: true,
  },
  {
    id: "org-membership",
    path: "/org/membership",
    label: "组织与加入",
    icon: "apps",
    status: "live",
    crumbs: ["工作区", "组织与加入"],
    hidden: true,
  },

  { section: "工作台" },
  { id: "workshop", path: "/workshop", label: "应用列表", icon: "apps", status: "live", crumbs: ["工作台", "应用列表"] },
  {
    id: "workshop-module",
    path: "/workshop/inbox",
    label: "风险告警管理",
    icon: "inbox",
    status: "live",
    crumbs: ["工作台", "风险告警管理"],
  },
  {
    id: "workshop-cop",
    path: "/workshop/cop",
    label: "态势大屏",
    icon: "ontology",
    status: "live",
    crumbs: ["工作台", "态势大屏"],
  },
  {
    id: "workshop-aip-chat",
    path: "/workshop/buddy",
    label: "Buddy 智能助手",
    icon: "chat",
    status: "live",
    crumbs: ["工作台", "Buddy 智能助手"],
  },
  {
    id: "analytics",
    path: "/analytics",
    label: "分析建模",
    icon: "table",
    status: "live",
    crumbs: ["工作台", "分析建模"],
  },

  { section: "应用程序构建工具" },
  {
    id: "workshop-canvas",
    path: "/workshop/canvas",
    label: "画布编辑",
    icon: "layers",
    status: "live",
    crumbs: ["构建工具", "画布编辑"],
  },
  {
    id: "workshop-module-interface",
    path: "/workshop/module-interface",
    label: "模块接口",
    icon: "apps",
    status: "live",
    crumbs: ["构建工具", "模块接口"],
  },
  {
    id: "workshop-events",
    path: "/workshop/events",
    label: "事件配置",
    icon: "bell",
    status: "live",
    crumbs: ["构建工具", "事件配置"],
  },
  {
    id: "workshop-publish",
    path: "/workshop/publish",
    label: "发布入口",
    icon: "server",
    status: "live",
    crumbs: ["构建工具", "发布入口"],
  },

  { section: "AIP 决策引擎" },
  // ─── 应用层（User Facing） ───
  {
    id: "aip-assist",
    path: "/aip/assist",
    label: "AIP Assist",
    icon: "chat",
    status: "live",
    crumbs: ["AIP", "AIP Assist"],
  },
  {
    id: "agents",
    path: "/aip/studio",
    label: "Chatbot Studio",
    icon: "chat",
    status: "live",
    crumbs: ["AIP", "Chatbot Studio"],
  },
  {
    id: "aip-analyst",
    path: "/aip/analyst",
    label: "AIP Analyst",
    icon: "table",
    status: "live",
    crumbs: ["AIP", "AIP Analyst"],
  },
  // ─── 编排构建层（Build Layer） ───
  {
    id: "aip-logic",
    path: "/aip/logic",
    label: "AIP 逻辑画布",
    icon: "workflow",
    status: "live",
    crumbs: ["AIP", "逻辑画布"],
  },
  {
    id: "aip-tools",
    path: "/aip/tools",
    label: "Agent 工具面板",
    icon: "wrench",
    status: "live",
    crumbs: ["AIP", "Agent 工具面板"],
  },
  {
    id: "aip-maturity",
    path: "/aip/maturity",
    label: "成熟度楼梯",
    icon: "stairs",
    status: "live",
    crumbs: ["AIP", "成熟度楼梯"],
  },
  {
    id: "aip-capabilities",
    path: "/aip/capabilities",
    label: "重能力接入",
    icon: "film",
    status: "live",
    crumbs: ["AIP", "重能力接入"],
  },
  // ─── 质量保障层（Quality Gate） ───
  {
    id: "aip-evals",
    path: "/aip/evals",
    label: "Evals 门控",
    icon: "check",
    status: "live",
    crumbs: ["AIP", "Evals 门控"],
  },
  {
    id: "aip-draft-inbox",
    path: "/aip/drafts",
    label: "Draft 审批台",
    icon: "inbox",
    status: "live",
    crumbs: ["AIP", "Draft 审批台"],
  },
  {
    id: "aip-decision-lineage",
    path: "/aip/lineage",
    label: "决策谱系",
    icon: "git",
    status: "live",
    crumbs: ["AIP", "决策谱系"],
  },
  // ─── 可观测性层（Observability） ───
  {
    id: "aip-observability",
    path: "/aip/observability",
    label: "可观测性",
    icon: "activity",
    status: "live",
    crumbs: ["AIP", "可观测性"],
  },

  { section: "模型管理" },
  // ─── 模型基础设施层（Model Infra） ───
  {
    id: "aip-model-catalog",
    path: "/aip/model-catalog",
    label: "模型目录",
    icon: "database",
    status: "live",
    crumbs: ["模型管理", "模型目录"],
  },
  {
    id: "aip-model-providers",
    path: "/aip/model-providers",
    label: "模型供应商",
    icon: "plug",
    status: "live",
    crumbs: ["模型管理", "模型供应商"],
  },
  {
    id: "aip-model-router",
    path: "/aip/model-router",
    label: "模型路由",
    icon: "spark",
    status: "live",
    crumbs: ["模型管理", "模型路由"],
  },
  {
    id: "aip-capacity-management",
    path: "/aip/capacity",
    label: "容量管理",
    icon: "database",
    status: "live",
    crumbs: ["模型管理", "容量管理"],
  },

  { section: "本体 · 数字孪生" },
  {
    id: "ontology",
    path: "/ontology",
    label: "本体管理",
    icon: "ontology",
    status: "live",
    crumbs: ["本体", "本体管理"],
  },
  {
    id: "workshop-object-view",
    path: "/workshop/graph",
    label: "对象探索",
    icon: "graph",
    status: "live",
    crumbs: ["本体", "对象探索"],
  },
  {
    id: "ontology-funnel",
    path: "/ontology/funnel",
    label: "漏斗管道",
    icon: "funnel",
    status: "live",
    crumbs: ["本体", "漏斗管道"],
  },
  {
    id: "funnel",
    path: "/ontology/okf-funnel",
    label: "OKF 行业漏斗",
    icon: "spark",
    status: "live",
    crumbs: ["本体", "OKF 漏斗"],
  },
  {
    id: "okf-overview",
    path: "/ontology/okf-overview",
    label: "OKF 概览",
    icon: "server",
    status: "live",
    crumbs: ["本体", "OKF 概览"],
  },
  {
    id: "ontology-graph-health",
    path: "/ontology/graph-health",
    label: "图谱健康度",
    icon: "heart",
    status: "live",
    crumbs: ["本体", "图谱健康度"],
  },
  {
    id: "ontology-wiki",
    path: "/ontology/wiki",
    label: "活知识 Wiki",
    icon: "wiki",
    status: "live",
    crumbs: ["本体", "Wiki"],
  },
  {
    id: "ontology-branches",
    path: "/ontology/branches",
    label: "分支管理",
    icon: "git",
    status: "live",
    crumbs: ["本体", "分支管理"],
  },

  { section: "管道与数据治理" },
  {
    id: "pipeline-list",
    path: "/data/pipelines",
    label: "管道构建",
    icon: "workflow",
    status: "live",
    crumbs: ["管道", "管道构建"],
  },
  {
    id: "pipeline-proposals",
    path: "/data/pipeline-proposals",
    label: "管道提案",
    icon: "git",
    status: "live",
    crumbs: ["管道", "管道提案"],
  },
  {
    id: "schedules",
    path: "/data/schedules",
    label: "计划编辑器",
    icon: "bell",
    status: "live",
    crumbs: ["管道", "计划编辑器"],
  },
  {
    id: "builds",
    path: "/data/builds",
    label: "搭建",
    icon: "layers",
    status: "live",
    crumbs: ["管道", "搭建"],
  },
  {
    id: "dataset",
    path: "/data/datasets",
    label: "数据集预览",
    icon: "table",
    status: "live",
    crumbs: ["管道", "数据集"],
  },
  {
    id: "code-repositories",
    path: "/data/code-repos",
    label: "代码库",
    icon: "layers",
    status: "live",
    crumbs: ["管道", "代码库"],
  },
  {
    id: "lineage",
    path: "/data/lineage",
    label: "数据沿袭",
    icon: "git",
    status: "live",
    crumbs: ["管道", "沿袭"],
  },
  {
    id: "health",
    path: "/data/health",
    label: "数据健康",
    icon: "heart",
    status: "live",
    crumbs: ["管道", "健康"],
  },

  { section: "数据源与同步" },
  {
    id: "data-connection",
    path: "/data",
    label: "数据链接器",
    icon: "plug",
    status: "live",
    crumbs: ["数据源", "数据链接器"],
  },
  {
    id: "data-connection-agents",
    path: "/data/agents",
    label: "边缘代理",
    icon: "server",
    status: "live",
    crumbs: ["数据源", "边缘代理"],
  },
  {
    id: "sync-config",
    path: "/data/sync-config",
    label: "同步配置",
    icon: "sync",
    status: "live",
    crumbs: ["数据源", "同步配置"],
  },
  {
    id: "sync-routes",
    path: "/data/sync-routes",
    label: "同步路由",
    icon: "route",
    status: "live",
    crumbs: ["数据源", "同步路由"],
  },
  {
    id: "media-sets",
    path: "/data/media-sets",
    label: "媒体集",
    icon: "film",
    status: "live",
    crumbs: ["数据源", "媒体集"],
  },
  {
    id: "aip-doc-intelligence",
    path: "/aip/doc-intelligence",
    label: "文档智能",
    icon: "folder",
    status: "live",
    crumbs: ["数据源", "文档智能"],
  },

  { section: OPS_NAV_SECTION, collapseDefault: true },
  {
    id: "local-platform",
    path: "/settings/local-platform",
    label: LOCAL_PLATFORM_NAME,
    icon: "monitor",
    status: "live",
    crumbs: [OPS_NAV_SECTION, LOCAL_PLATFORM_NAME],
  },
  {
    id: "ops-start-guide",
    path: "/settings/ops-start-guide",
    label: "启停说明",
    icon: "wrench",
    status: "live",
    crumbs: [OPS_NAV_SECTION, "启停说明"],
  },
  {
    id: "apollo-hub",
    path: "/apollo",
    label: "Hub 舰队",
    icon: "server",
    status: "live",
    crumbs: [OPS_NAV_SECTION, "Hub 舰队"],
  },
  {
    id: "apollo-release",
    path: "/apollo/release",
    label: "Release 通道",
    icon: "stairs",
    status: "live",
    crumbs: [OPS_NAV_SECTION, "Release"],
  },
  {
    id: "apollo-spoke",
    path: "/apollo/spoke",
    label: "Spoke 详情",
    icon: "plug",
    status: "live",
    crumbs: [OPS_NAV_SECTION, "Spoke"],
  },
  {
    id: "apollo-ferry",
    path: "/apollo/ferry",
    label: "Ferry 摆渡",
    icon: "film",
    status: "live",
    crumbs: [OPS_NAV_SECTION, "Ferry"],
  },
  {
    id: "apollo-assets",
    path: "/apollo/assets",
    label: "FDE 资产包",
    icon: "spark",
    status: "live",
    crumbs: [OPS_NAV_SECTION, "资产包"],
  },
  {
    id: "apollo-change-mgmt",
    path: "/apollo/change",
    label: "变更审批",
    icon: "inbox",
    status: "live",
    crumbs: [OPS_NAV_SECTION, "变更审批"],
  },
  {
    id: "apollo-config",
    path: "/apollo/config",
    label: "配置与密钥",
    icon: "wrench",
    status: "live",
    crumbs: [OPS_NAV_SECTION, "配置与密钥"],
  },
  {
    id: "integration-cases",
    path: "/apollo/cases",
    label: "接入案例",
    icon: "activity",
    status: "live",
    crumbs: [OPS_NAV_SECTION, "接入案例"],
  },
  {
    id: "apollo-saas-provisioning",
    path: "/apollo/provisioning",
    label: "SaaS 开通",
    icon: "apps",
    status: "live",
    crumbs: [OPS_NAV_SECTION, "SaaS 开通"],
  },
];

export function isNavPage(item: NavItem): item is NavPage {
  return "path" in item;
}

export function navPages(): NavPage[] {
  return NAV_ITEMS.filter(isNavPage);
}

export function findNavPage(pathname: string): NavPage | undefined {
  const pages = navPages();
  const exact = pages.find((p) => p.path === pathname);
  if (exact) return exact;
  // longest prefix match (e.g. nested)
  return pages
    .filter((p) => p.path !== "/" && pathname.startsWith(p.path))
    .sort((a, b) => b.path.length - a.path.length)[0];
}

export const DEMO_VERSION = "v1.6.5";
