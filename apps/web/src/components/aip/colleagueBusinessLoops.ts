export type ColleagueRoleKey =
  | "customer_service"
  | "private_domain_manager"
  | "shopping_advisor"
  | "data_advisor"
  | "content_officer"
  | "campaign_planner";

export type ColleagueBusinessLoopDefinition = {
  roleKey: ColleagueRoleKey;
  roleName: string;
  businessInput: string;
  businessOutput: string;
  contributionLabel: string;
  workshopHref: string;
  contributionHref: string;
};

function workshopHref(path: string, roleKey: ColleagueRoleKey, focus?: "contribution"): string {
  const params = new URLSearchParams({ colleague: roleKey });
  if (focus) params.set("focus", focus);
  return `${path}?${params.toString()}`;
}

export const COLLEAGUE_BUSINESS_LOOP_DEFINITIONS: Record<ColleagueRoleKey, ColleagueBusinessLoopDefinition> = {
  customer_service: {
    roleKey: "customer_service", roleName: "客服专员",
    businessInput: "客户问题、订单与售后事实",
    businessOutput: "答复草稿、工单建议与升级判断",
    contributionLabel: "客户关系工作台 · 服务处置",
    workshopHref: workshopHref("/workshop/customer", "customer_service"),
    contributionHref: workshopHref("/workshop/customer", "customer_service", "contribution"),
  },
  private_domain_manager: {
    roleKey: "private_domain_manager", roleName: "私域管家",
    businessInput: "客户分层、授权与关系信号",
    businessOutput: "运营计划、触达草稿与效果回读",
    contributionLabel: "客户关系工作台 · 生命周期运营",
    workshopHref: workshopHref("/workshop/customer", "private_domain_manager"),
    contributionHref: workshopHref("/workshop/customer", "private_domain_manager", "contribution"),
  },
  shopping_advisor: {
    roleKey: "shopping_advisor", roleName: "导购顾问",
    businessInput: "顾客需求、商品、库存与价格约束",
    businessOutput: "可解释推荐草稿与顾客反馈",
    contributionLabel: "日常任务总控 · 导购协作",
    workshopHref: workshopHref("/workshop/cockpit", "shopping_advisor"),
    contributionHref: workshopHref("/workshop/cockpit", "shopping_advisor", "contribution"),
  },
  data_advisor: {
    roleKey: "data_advisor", roleName: "数据参谋",
    businessInput: "经营问题与正式经营数据",
    businessOutput: "经营结论、证据与任务建议",
    contributionLabel: "经营参谋 · 分析与复盘",
    workshopHref: workshopHref("/workshop/analyst", "data_advisor"),
    contributionHref: workshopHref("/workshop/analyst", "data_advisor", "contribution"),
  },
  content_officer: {
    roleKey: "content_officer", roleName: "内容官",
    businessInput: "选题、商品事实、素材与渠道约束",
    businessOutput: "内容方案、脚本、素材任务与发布草稿",
    contributionLabel: "内容与活动 / 多媒体工作台",
    workshopHref: workshopHref("/workshop/content-campaign", "content_officer"),
    contributionHref: workshopHref("/workshop/media-studio", "content_officer", "contribution"),
  },
  campaign_planner: {
    roleKey: "campaign_planner", roleName: "活动策划师",
    businessInput: "经营机会、商品、人群、预算与风险约束",
    businessOutput: "活动方案、审批建议与协作任务",
    contributionLabel: "内容与活动工作台 · 活动策划",
    workshopHref: workshopHref("/workshop/content-campaign", "campaign_planner"),
    contributionHref: workshopHref("/workshop/content-campaign", "campaign_planner", "contribution"),
  },
};

export type ColleagueBusinessLoop = ColleagueBusinessLoopDefinition & {
  logicLabels: string[];
  runtimeReadiness: "blocked" | "runnable";
};

export function buildColleagueBusinessLoop(
  roleKey: string,
  logicIds: readonly string[],
  runtimeReadiness: "blocked" | "runnable",
): ColleagueBusinessLoop {
  const definition = COLLEAGUE_BUSINESS_LOOP_DEFINITIONS[roleKey as ColleagueRoleKey];
  if (!definition) throw new Error(`未知数字同事角色：${roleKey}`);
  return {
    ...definition,
    logicLabels: [...new Set(logicIds.map((value) => value.trim()).filter(Boolean))],
    runtimeReadiness,
  };
}
