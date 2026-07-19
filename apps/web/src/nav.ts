/** DEMO_PAGES full narrative — order locked to foundry/html demo.js v1.6.5 */
export type NavSection = { section: string };
export type NavPage = {
  id: string;
  path: string;
  label: string;
  icon: IconName;
  /** live = React 已接线；s2 = 蓝图占位（T-UI S2） */
  status: "live" | "s2";
  crumbs?: string[];
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
  | "search";

export const NAV_ITEMS: NavItem[] = [
  { id: "index", path: "/", label: "概览", icon: "home", status: "live", crumbs: ["工作区", "AOS 概览"] },
  { section: "工作台" },
  { id: "workshop", path: "/workshop", label: "应用列表", icon: "apps", status: "live", crumbs: ["工作台", "应用列表"] },
  {
    id: "workshop-canvas",
    path: "/workshop/canvas",
    label: "画布编辑",
    icon: "layers",
    status: "live",
    crumbs: ["工作台", "画布编辑"],
  },
  {
    id: "workshop-module",
    path: "/workshop/inbox",
    label: "运营台",
    icon: "inbox",
    status: "live",
    crumbs: ["工作台", "运营台"],
  },
  {
    id: "workshop-object-view",
    path: "/workshop/graph",
    label: "知识图谱",
    icon: "graph",
    status: "live",
    crumbs: ["工作台", "知识图谱"],
  },
  {
    id: "workshop-aip-chat",
    path: "/workshop/buddy",
    label: "智能助手",
    icon: "chat",
    status: "live",
    crumbs: ["工作台", "智能助手"],
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
    id: "workshop-publish",
    path: "/workshop/publish",
    label: "发布入口",
    icon: "server",
    status: "live",
    crumbs: ["工作台", "发布入口"],
  },
  {
    id: "workshop-module-interface",
    path: "/workshop/module-interface",
    label: "模块接口",
    icon: "apps",
    status: "live",
    crumbs: ["工作台", "模块接口"],
  },
  {
    id: "workshop-events",
    path: "/workshop/events",
    label: "事件配置",
    icon: "bell",
    status: "live",
    crumbs: ["工作台", "事件配置"],
  },
  {
    id: "analytics",
    path: "/analytics",
    label: "分析建模",
    icon: "table",
    status: "live",
    crumbs: ["工作台", "分析建模"],
  },
  { section: "AIP 决策引擎" },
  {
    id: "agents",
    path: "/aip/studio",
    label: "对话工作室",
    icon: "chat",
    status: "live",
    crumbs: ["AIP", "对话工作室"],
  },
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
    label: "智能体管理工作台",
    icon: "wrench",
    status: "live",
    crumbs: ["AIP", "智能体管理工作台"],
  },
  {
    id: "aip-capabilities",
    path: "/aip/capabilities",
    label: "重能力接入",
    icon: "film",
    status: "live",
    crumbs: ["AIP", "重能力接入"],
  },
  {
    id: "aip-draft-inbox",
    path: "/aip/drafts",
    label: "提案审批台",
    icon: "inbox",
    status: "live",
    crumbs: ["AIP", "提案审批台"],
  },
  {
    id: "aip-evals",
    path: "/aip/evals",
    label: "评测门控",
    icon: "check",
    status: "live",
    crumbs: ["AIP", "评测门控"],
  },
  {
    id: "aip-decision-lineage",
    path: "/aip/lineage",
    label: "决策谱系",
    icon: "git",
    status: "live",
    crumbs: ["AIP", "决策谱系"],
  },
  {
    id: "aip-model-providers",
    path: "/aip/model-providers",
    label: "大模型接入(插件)",
    icon: "plug",
    status: "live",
    crumbs: ["AIP", "大模型接入(插件)"],
  },
  {
    id: "aip-model-router",
    path: "/aip/model-router",
    label: "模型路由",
    icon: "spark",
    status: "live",
    crumbs: ["AIP", "模型路由"],
  },
  {
    id: "aip-maturity",
    path: "/aip/maturity",
    label: "成熟度楼梯",
    icon: "stairs",
    status: "live",
    crumbs: ["AIP", "成熟度楼梯"],
  },
  { section: "本体 · 数字孪生" },
  {
    id: "ontology",
    path: "/ontology",
    label: "本体管理（数字孪生）",
    icon: "ontology",
    status: "live",
    crumbs: ["本体", "本体管理"],
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
  { section: "数据集成" },
  {
    id: "data-connection",
    path: "/data",
    label: "数据连接",
    icon: "plug",
    status: "live",
    crumbs: ["数据", "数据连接"],
  },
  {
    id: "data-connection-agents",
    path: "/data/agents",
    label: "边缘代理",
    icon: "server",
    status: "live",
    crumbs: ["数据", "边缘代理"],
  },
  {
    id: "media-sets",
    path: "/data/media-sets",
    label: "媒体集",
    icon: "film",
    status: "live",
    crumbs: ["数据", "媒体集"],
  },
  {
    id: "pipeline-list",
    path: "/data/pipelines",
    label: "管道构建",
    icon: "workflow",
    status: "live",
    crumbs: ["数据", "管道构建"],
  },
  {
    id: "pipeline-proposals",
    path: "/data/pipeline-proposals",
    label: "管道提案",
    icon: "git",
    status: "live",
    crumbs: ["数据", "管道提案"],
  },
  {
    id: "schedules",
    path: "/data/schedules",
    label: "计划编辑器",
    icon: "bell",
    status: "live",
    crumbs: ["数据", "计划编辑器"],
  },
  {
    id: "builds",
    path: "/data/builds",
    label: "搭建",
    icon: "layers",
    status: "live",
    crumbs: ["数据", "搭建"],
  },
  {
    id: "dataset",
    path: "/data/datasets",
    label: "数据集预览",
    icon: "table",
    status: "live",
    crumbs: ["数据", "数据集"],
  },
  {
    id: "code-repositories",
    path: "/data/code-repos",
    label: "代码库",
    icon: "layers",
    status: "live",
    crumbs: ["数据", "代码库"],
  },
  {
    id: "lineage",
    path: "/data/lineage",
    label: "数据沿袭",
    icon: "git",
    status: "live",
    crumbs: ["数据", "沿袭"],
  },
  {
    id: "health",
    path: "/data/health",
    label: "数据健康",
    icon: "heart",
    status: "live",
    crumbs: ["数据", "健康"],
  },
  { section: "交付 Apollo" },
  {
    id: "apollo-hub",
    path: "/apollo",
    label: "Hub 舰队",
    icon: "server",
    status: "live",
    crumbs: ["Apollo", "Hub 舰队"],
  },
  {
    id: "apollo-release",
    path: "/apollo/release",
    label: "Release 通道",
    icon: "stairs",
    status: "live",
    crumbs: ["Apollo", "Release"],
  },
  {
    id: "apollo-spoke",
    path: "/apollo/spoke",
    label: "Spoke 详情",
    icon: "plug",
    status: "live",
    crumbs: ["Apollo", "Spoke"],
  },
  {
    id: "apollo-ferry",
    path: "/apollo/ferry",
    label: "Ferry 摆渡",
    icon: "film",
    status: "live",
    crumbs: ["Apollo", "Ferry"],
  },
  {
    id: "apollo-assets",
    path: "/apollo/assets",
    label: "FDE 资产包",
    icon: "spark",
    status: "live",
    crumbs: ["Apollo", "资产包"],
  },
  {
    id: "apollo-change-mgmt",
    path: "/apollo/change",
    label: "变更审批",
    icon: "inbox",
    status: "live",
    crumbs: ["Apollo", "变更审批"],
  },
  {
    id: "apollo-config",
    path: "/apollo/config",
    label: "配置与密钥",
    icon: "wrench",
    status: "live",
    crumbs: ["Apollo", "配置与密钥"],
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
