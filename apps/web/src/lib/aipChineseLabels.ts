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
  r0: "只读",
  r1: "低风险",
  r2: "需人工审批",
  r3: "高风险",
  r4: "禁止自动执行",
  low: "低",
  medium: "中",
  high: "高",
  critical: "严重",
};

const ACTION_NAMES: Record<string, string> = {
  closeworkorder: "关闭工单",
  close_work_order: "关闭工单",
  send_notice: "发送通知",
  cancelorder: "取消订单",
  cancel_order: "取消订单",
  publish_content: "发布内容",
  create_refund: "发起退款",
  updatewikicard: "更新知识卡片",
};

const OBJECT_TYPE_NAMES: Record<string, string> = {
  order: "订单",
  workorder: "工单",
  contentdraft: "内容草稿",
  customerlite: "客户",
  product: "商品",
  productsku: "商品规格",
  payment: "支付",
  shipment: "发货",
};

const DEFINITION_READINESS_NAMES: Record<string, string> = {
  available: "定义可用",
  blocked: "定义条件待补齐",
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
  roles_not_fully_runnable: "部分数字同事仍需补齐运行条件",
  capabilities_not_fully_runnable: "当前方案所需专业能力仍需补齐运行条件",
  tools_not_fully_runnable: "当前方案所需工具仍需补齐运行条件",
  routes_not_fully_runnable: "部分模型路由仍需补齐运行条件",
  eval_gates_not_fully_passed: "评测门尚未全部通过",
  capability_binding_readiness_stale: "能力绑定状态需要刷新",
  skill_binding_readiness_stale: "技能绑定状态需要刷新",
  skill_binding_unavailable: "缺少有效技能绑定",
  capability_bindings_unavailable: "缺少有效能力绑定",
  agent_instance_not_installed: "尚未安装数字同事实例",
  agent_instance_not_active: "数字同事实例未启用",
  skill_templates_not_published: "技能模板尚未发布",
  provider_unknown: "模型供应商未知",
  eval_pack_unavailable: "缺少有效评测包",
  w0b_contracts_unavailable: "缺少公共上线审批记录",
  aip7_route_authority_unavailable: "缺少模型路由权威记录",
  provider_health_unavailable_or_stale: "供应商健康检查缺失或已过期",
  CAPABILITY_BINDING_NOT_ACTIVE: "能力绑定未激活",
  MODEL_ROUTE_BLOCKED: "模型路由被阻断",
  PROVIDER_HEALTH_UNAVAILABLE: "缺少供应商健康检查",
  price_unit_mismatch: "计价单位与用量凭证不一致",
  pricing_unit_mismatch: "计价单位与用量凭证不一致",
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
  return "存在尚未归类的运行阻断";
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

export function actionDisplayName(actionTypeId: string): string {
  const key = String(actionTypeId || "").trim().toLowerCase();
  return ACTION_NAMES[key] || "受控业务动作";
}

export function objectTypeDisplayName(objectType: string): string {
  const key = String(objectType || "").trim().toLowerCase();
  return OBJECT_TYPE_NAMES[key] || objectType || "业务对象";
}

/** Only changes the business-facing title; the original authority ID stays untouched. */
export function businessDisplayName(value: string, fallback = "未命名业务能力"): string {
  const exactNames: Record<string, string> = {
    "aip.skill-publication.approval": "技能发布审批",
    "ecommerce-standard": "电商标准生产流程",
    "w-t2-v1": "当前智能体默认工具包",
    "w-j3 sample chain: closeworkorder after eval gate": "评测通过后的工单关闭申请",
    "电商增长方案包（d3：w03 客户与私域运营台 + l05 分润异常检测）": "电商增长与客户运营方案包",
    "provider 不可用": "模型供应商故障回退",
  };
  const raw = String(value || "").trim();
  if (exactNames[raw.toLowerCase()]) return exactNames[raw.toLowerCase()];
  const clean = String(value || "")
    .replace(/^\s*(?:(?:AIP-[A-Z0-9]+)|(?:[DCGSPAVI]\d+)|(?:W-?[A-Z]?\d+)|(?:L\d+))\s*[·:：—-]?\s*/i, "")
    .replace(/(?:隔离\s*)?\bdry[- ]?run\b/gi, "隔离试运行")
    .trim();
  return clean || fallback;
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

const TOOL_KIND_NAMES: Record<string, string> = {
  action: "受控写回动作",
  query: "业务对象查询",
  "object query": "业务对象查询",
  function: "业务逻辑工具",
  logic: "业务逻辑工具",
  clarify: "信息补充确认",
  "request clarification": "信息补充确认",
  capability: "专业能力",
  wiki: "知识字段读取",
  command: "受控命令",
  variable: "应用变量",
};

const RUNTIME_MODE_NAMES: Record<string, string> = {
  native: "并行调用",
  prompted: "逐项调用",
  auto: "自动提交确认",
  form: "表单人工确认",
  draft: "仅生成草稿",
};

const CONTRACT_SECTION_NAMES: Record<string, string> = {
  "task brief": "任务简报",
  "evidence bundle": "证据包",
  "eval contract": "评测契约",
  "responsibility plan": "职责计划",
  "stage template": "阶段模板",
  "artifact relation": "产物关系",
  "review issue": "评审问题",
  "impact preview": "影响预览",
  "production context": "生产上下文",
  "start decision": "启动决策",
};

const STATUS_NAMES: Record<string, string> = {
  running: "运行中",
  active: "已启用",
  ready: "就绪",
  available: "可使用",
  blocked: "已阻断",
  stale: "已过期",
  unknown: "状态未知",
  draft: "草稿",
  frozen: "已冻结",
  published: "已发布",
  evaluated: "已评测",
  approved: "已批准",
  rejected: "已驳回",
  open: "待处理",
  resolved: "已解决",
  passed: "已通过",
  healthy: "健康",
  failed: "失败",
  idle: "未运行",
  complete: "完整",
  partial: "部分",
};

export function toolKindDisplayName(kind: string): string {
  const key = String(kind || "").trim().toLowerCase();
  return TOOL_KIND_NAMES[key] || "业务工具";
}

export function toolDisplayName(input: {
  id: string;
  kind: string;
  name?: string;
  nameZh?: string;
}): string {
  const chineseName = String(input.nameZh || "").trim();
  if (chineseName) {
    return chineseName
      .replace("关闭/写回（HITL）", "关闭或写回（需人工确认）")
      .replace("Echo（演示）", "连通性校验");
  }
  const logicName = logicDisplayName(input.id);
  if (logicName && logicName !== input.id) return logicName;
  const name = String(input.name || "").trim();
  if (name && /[\u3400-\u9fff]/.test(name)) {
    return name
      .replace("关闭/写回（HITL）", "关闭或写回（需人工确认）")
      .replace("Echo（演示）", "连通性校验");
  }
  return toolKindDisplayName(input.kind);
}

export function runtimeModeDisplayName(mode: string): string {
  const key = String(mode || "").trim().toLowerCase();
  return RUNTIME_MODE_NAMES[key] || "按策略调用";
}

export function contractSectionDisplayName(section: string): string {
  const key = String(section || "").trim().toLowerCase();
  return CONTRACT_SECTION_NAMES[key] || section;
}

export function statusDisplayName(status: string): string {
  const key = String(status || "").trim().toLowerCase();
  return STATUS_NAMES[key] || status;
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
