/**
 * AIP 前台中文展示词典：方案代号/英文码不得作为主文案。
 * 权威来源：ecommerce-37-logic-catalog + W0A Capability Crosswalk。
 */

const LOGIC_NAMES: Record<string, string> = {
  D01: "数据与经营健康巡检",
  D02: "内外机会研究",
  D03: "增长方案生成",
  D04: "审批后任务拆解",
  D05: "执行监控与调整建议",
  D06: "效果归因与复盘",
  C01: "热点竞品与获客机会研究",
  C02: "人群与内容策略",
  C03: "文案与种草内容生产",
  C04: "短视频策划",
  C05: "多平台适配",
  C06: "事实品牌与合规审核",
  C07: "互动线索识别与交接",
  C08: "内容到成交归因与优化",
  G01: "需求诊断",
  G02: "产品检索与推荐",
  G03: "成分分析",
  G04: "产品对比",
  G05: "异议识别与处理",
  G06: "促单与成交交接",
  S01: "意图与情绪识别",
  S02: "身份与订单安全查询",
  S03: "物流查询与异常分诊",
  S04: "售后资格与工单草拟",
  S05: "投诉与人工升级",
  S06: "满意度与问题反哺",
  P01: "客户身份沉淀",
  P02: "客户标签与分层",
  P03: "跟进与触达排期",
  P04: "沉默客户与复购机会",
  P05: "关系反馈",
  A01: "活动机会与目标",
  A02: "人群商品与机制设计",
  A03: "预算与毛利模拟",
  A04: "跨同事任务编排",
  A05: "执行监控与止损",
  A06: "活动复盘",
  I01: "视觉草稿方案生成",
  V01: "视频草稿方案生成",
};

const CAPABILITY_NAMES: Record<string, string> = {
  "material.collect": "素材采集",
  "strategy.plan": "策略规划",
  "copy.generate": "文案生成",
  "script.compose": "脚本撰写",
  "speech.synthesize": "语音合成",
  "video.compose": "视频合成",
  "image.generate": "图像生成",
  "video.generate": "视频生成",
  "content.review": "内容审核",
  "live.orchestrate": "直播编排",
  "platform.adapt": "平台适配",
  "performance.review": "数据复盘",
};

const RISK_NAMES: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  critical: "严重",
};

const DEFINITION_READINESS_NAMES: Record<string, string> = {
  available: "定义可用",
  blocked: "定义未就绪",
  degraded: "定义降级",
};

const DIMENSION_NAMES: Record<string, string> = {
  providerRef: "供应商",
  modelRouteRef: "路由",
  evalGateRef: "评测门",
  licenseEvidenceRefs: "许可",
  dataDependencyRefs: "数据依赖",
  toolDependencyRefs: "工具依赖",
  budgetPolicyRef: "预算策略",
};

const INSTANCE_STATUS_NAMES: Record<string, string> = {
  provisioning: "待配置",
  active: "已启用",
  suspended: "已暂停",
  deleted: "已删除",
};

const RESPONSIBILITY_NAMES: Record<string, string> = {
  "service.escalation": "售后服务与升级",
  "growth.coordination": "增长协同",
  "production.coordination": "内容生产协同",
  "relationship.stewardship": "私域关系经营",
  "commerce.advisory": "导购与成交顾问",
  "campaign.coordination": "活动策划协同",
};

const BLOCKER_NAMES: Record<string, string> = {
  capability_binding_readiness_stale: "能力绑定就绪快照已过期，请刷新",
  skill_binding_readiness_stale: "技能绑定就绪快照已过期，请刷新",
  skill_binding_unavailable: "技能绑定不可用",
  capability_bindings_unavailable: "能力绑定不可用",
  agent_instance_not_installed: "尚未安装数字同事实例",
  agent_instance_not_active: "数字同事实例未启用",
  skill_templates_not_published: "技能模板尚未发布",
  provider_unknown: "模型供应商未知",
  eval_pack_unavailable: "评测包不可用",
  w0b_contracts_unavailable: "公共生产契约尚未就绪",
  aip7_route_authority_unavailable: "模型路由权威尚未就绪",
  provider_health_unavailable_or_stale: "供应商健康检查不可用或已过期",
  CAPABILITY_BINDING_NOT_ACTIVE: "能力绑定未激活",
  MODEL_ROUTE_BLOCKED: "模型路由被阻断",
  PROVIDER_HEALTH_UNAVAILABLE: "供应商健康检查不可用",
};

const BINDING_STATUS_NAMES: Record<string, string> = {
  active: "已激活",
  draft: "草稿",
  suspended: "已暂停",
  revoked: "已撤销",
  provisioning: "待配置",
};

function logicKey(raw: string): string {
  const text = String(raw || "").trim();
  if (!text) return "";
  const short = text.includes(".") ? text.split(".").pop() || text : text;
  return short.toUpperCase();
}

/** ecommerce.logic.S01 / S01 / ecommerce.skill.S01 → 意图与情绪识别 */
export function logicDisplayName(canonicalLogicId: string): string {
  const key = logicKey(canonicalLogicId);
  return LOGIC_NAMES[key] || canonicalLogicId;
}

export function capabilityDisplayName(capabilityId: string): string {
  return CAPABILITY_NAMES[capabilityId] || capabilityId;
}

export function responsibilityDisplayName(responsibility: string): string {
  return RESPONSIBILITY_NAMES[responsibility] || responsibility;
}

export function blockerDisplayName(code: string): string {
  const raw = String(code || "");
  const [head, tail] = raw.split(":");
  const mapped = BLOCKER_NAMES[head] || BLOCKER_NAMES[raw];
  if (mapped && tail) {
    const logic = LOGIC_NAMES[logicKey(tail)];
    return logic ? `${mapped}（${logic}）` : `${mapped}（${tail}）`;
  }
  if (mapped) return mapped;
  if (raw.startsWith("skill_revision_not_published")) {
    const id = raw.split(":")[1] || "";
    const name = LOGIC_NAMES[logicKey(id)];
    return name ? `技能尚未发布：${name}` : "技能尚未发布";
  }
  return raw;
}

export function bindingStatusDisplayName(status: string): string {
  return BINDING_STATUS_NAMES[status] || status;
}

export function instanceStatusDisplayName(status: string): string {
  return INSTANCE_STATUS_NAMES[status] || status;
}

export function riskDisplayName(risk: string): string {
  return RISK_NAMES[String(risk || "").toLowerCase()] || risk;
}

export function definitionReadinessDisplayName(readiness: string): string {
  return DEFINITION_READINESS_NAMES[String(readiness || "").toLowerCase()] || readiness;
}

export function dimensionDisplayName(key: string): string {
  return DIMENSION_NAMES[key] || key;
}

const TEMPLATE_NAMES: Record<string, string> = {
  "ecommerce.content_officer": "内容官",
  "ecommerce.campaign_planner": "活动策划师",
  "ecommerce.customer_service": "客服专员",
  "ecommerce.data_advisor": "数据参谋",
  "ecommerce.private_domain_manager": "私域管家",
  "ecommerce.shopping_advisor": "导购顾问",
};

export function templateDisplayName(templateId: string): string {
  const raw = String(templateId || "").trim();
  return TEMPLATE_NAMES[raw] || raw;
}

export function formatBlockers(codes: string[]): string {
  return codes.map(blockerDisplayName).join("；");
}

/** W-L1：分栏就绪阶梯（installed ≠ 可派发） */
export const AGENT_READINESS_LADDER = [
  { id: "published", label: "已发布" },
  { id: "installed", label: "已安装" },
  { id: "binding", label: "已绑定" },
  { id: "evaluated", label: "已评测" },
  { id: "operational", label: "可运营" },
  { id: "runnable", label: "可派发" },
] as const;

export type AgentReadinessStageId = (typeof AGENT_READINESS_LADDER)[number]["id"];

export type AgentReadinessLadder = {
  stages: Array<{ id: AgentReadinessStageId; label: string; done: boolean }>;
  current: AgentReadinessStageId | "none";
  dispatchable: boolean;
};

export function deriveAgentReadinessLadder(input: {
  templatePublished: boolean;
  installed: boolean;
  hasActiveSkillBinding: boolean;
  skillsPublished: boolean;
  capabilityOperational: boolean;
  runtimeReadiness: "blocked" | "runnable";
}): AgentReadinessLadder {
  const dispatchable = input.runtimeReadiness === "runnable";
  const flags: Record<AgentReadinessStageId, boolean> = {
    published: input.templatePublished,
    installed: input.installed,
    binding: input.installed && input.hasActiveSkillBinding,
    evaluated: input.installed && input.hasActiveSkillBinding && input.skillsPublished,
    operational: input.installed && input.capabilityOperational,
    runnable: dispatchable,
  };
  const stages = AGENT_READINESS_LADDER.map((stage) => ({
    id: stage.id,
    label: stage.label,
    done: flags[stage.id],
  }));
  let current: AgentReadinessStageId | "none" = "none";
  for (const stage of stages) {
    if (stage.done) current = stage.id;
    else break;
  }
  return { stages, current, dispatchable };
}

export function agentReadinessLadderSummary(ladder: AgentReadinessLadder): string {
  if (ladder.dispatchable) return "可派发（runnable）";
  if (!ladder.stages.find((s) => s.id === "installed")?.done) return "尚未安装（≠可派发）";
  const next = ladder.stages.find((s) => !s.done);
  return next ? `已安装未可派发 · 卡在「${next.label}」` : "已安装未可派发";
}
