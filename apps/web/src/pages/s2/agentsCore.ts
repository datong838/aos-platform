/**
 * Phase 2 · 对话机器人 — 纯函数模块
 *
 * 把所有可测的纯逻辑从 AgentsPage 组件里抽出来，便于 vitest 覆盖。
 * 组件只负责状态编排和渲染，业务规则集中在本文件。
 */

// -------------------- 类型 --------------------

export type AgentSource = "platform" | "plugin" | "external";
export type AgentStatus = "active" | "draft" | "stopped";

export type ToolKind = "API" | "Function" | "MCP" | "HTTP";
export type ToolState = "on" | "recommended" | "disabled" | "hitl";

/** 工具箱里的单个工具 */
export interface AgentTool {
  id: string;
  name: string;
  kind: ToolKind;
  state: ToolState;
  /** 触发 HITL 时记录的工具调用 ID（仅当 state === "hitl" 时有意义） */
  hitlCallId?: string;
}

/** 选中 Agent 详情 */
export interface AgentItem {
  id: string;
  name: string;
  description: string;
  source: AgentSource;
  status: AgentStatus;
  calls: number;
  modelId: string;
  prompt: string;
  icon: string;
  tools: AgentTool[];
  /** 业务域（向导 Step1） */
  domain?: string;
  /** 成熟度 L0–L4（向导 Step3） */
  level?: string;
}

/** 模型目录条目（对齐后端 /v1/aip/models） */
export interface CatalogModel {
  id: string;
  kind?: string;
  ready?: boolean;
  provider?: string;
  /** 展示名（可选） */
  label?: string;
  /** 副标题（可选） */
  blurb?: string;
}

// -------------------- MOCK 数据 --------------------

/** 平台内置 3 个 + 插件 1 + 外部 1，覆盖三类来源 */
export const MOCK_AGENTS: AgentItem[] = [
  {
    id: "ag-order-assist",
    name: "订单助手",
    description: "处理订单查询、退换货、物流追问。优先读取 Order 对象与 Wiki.sla 结构化字段。",
    source: "platform",
    status: "active",
    calls: 1234,
    modelId: "glm-4-plus",
    prompt:
      "你是订单助手。优先读 ${user.order}.status 与 ${context.wiki}.sla，禁止臆造字段。写回必须走 Action / Draft。",
    icon: "📦",
    tools: [
      { id: "t-order-q", name: "Object Query · 订单", kind: "API", state: "on" },
      { id: "t-refund", name: "Action · 发起退款", kind: "Function", state: "hitl", hitlCallId: "call_8821" },
      { id: "t-wiki-sla", name: "Wiki · SLA 查询", kind: "API", state: "recommended" },
      { id: "t-track", name: "HTTP · 物流追踪", kind: "HTTP", state: "on" },
    ],
  },
  {
    id: "ag-risk-scan",
    name: "风险扫描",
    description: "实时扫描交易异常模式，识别刷单、欺诈、价格异常，输出风险评分。",
    source: "platform",
    status: "active",
    calls: 567,
    modelId: "glm-4-air",
    prompt: "你是风险分析助手。读取 ${context.risk}.score，输出风险等级。",
    icon: "⚠",
    tools: [
      { id: "t-risk-q", name: "Function · risk_score", kind: "Function", state: "on" },
      { id: "t-alert", name: "Action · 推送告警", kind: "Function", state: "hitl", hitlCallId: "call_8830" },
    ],
  },
  {
    id: "ag-doc-qa",
    name: "文档问答",
    description: "知识库检索型 Agent，仅查询 Wiki 不做写回。",
    source: "platform",
    status: "draft",
    calls: 89,
    modelId: "deepseek-v3",
    prompt: "你是文档问答助手。仅基于 ${context.wiki} 回答。",
    icon: "📄",
    tools: [{ id: "t-wiki", name: "MCP · Wiki 检索", kind: "MCP", state: "on" }],
  },
  {
    id: "ag-video-cut",
    name: "短视频生产",
    description: "从脚本到混剪，调用 Media Job Capability 提交 GPU 渲染任务。",
    source: "plugin",
    status: "active",
    calls: 312,
    modelId: "glm-4-plus",
    prompt: "你是短视频生产 Agent。读取 ${user.brand}.style，输出 30s 脚本。",
    icon: "🎬",
    tools: [
      { id: "t-render", name: "Function · 提交渲染", kind: "Function", state: "recommended" },
      { id: "t-clip", name: "MCP · 素材混剪", kind: "MCP", state: "on" },
    ],
  },
  {
    id: "ag-erp-bridge",
    name: "ERP 桥接",
    description: "外部 ERP 系统桥接，HTTP 调用回写库存数据。",
    source: "external",
    status: "stopped",
    calls: 45,
    modelId: "glm-4-air",
    prompt: "你是 ERP 桥接 Agent。调用 ${context.erp}.inventory。",
    icon: "🔗",
    tools: [{ id: "t-erp", name: "HTTP · ERP 回写", kind: "HTTP", state: "disabled" }],
  },
];

/** 当 /v1/aip/models 未就绪时的兜底模型列表（对齐 agents.html Step2） */
export const MOCK_MODELS: CatalogModel[] = [
  { id: "glm-4-plus", kind: "text", ready: true, provider: "智谱", label: "GLM-4-Plus", blurb: "通用旗舰 · 128K 上下文" },
  { id: "glm-4-air", kind: "text", ready: true, provider: "智谱", label: "GLM-4-Air", blurb: "轻量高速 · 低延迟" },
  { id: "deepseek-v3", kind: "text", ready: true, provider: "DeepSeek", label: "DeepSeek-V3", blurb: "推理增强 · 开源" },
];

/** 视觉稿业务域 chips */
export const WIZARD_DOMAINS = [
  "设备运维",
  "电商客服",
  "风控分析",
  "内容创作",
  "知识检索",
  "财务报销",
] as const;

export type WizardIconKey = "chat" | "tool" | "alert" | "chart" | "doc" | "box";

export const WIZARD_ICON_KEYS: { key: WizardIconKey; title: string }[] = [
  { key: "chat", title: "对话" },
  { key: "tool", title: "工具" },
  { key: "alert", title: "告警" },
  { key: "chart", title: "图表" },
  { key: "doc", title: "文档" },
  { key: "box", title: "包裹" },
];

export const WIZARD_ONTOLOGY_OPTIONS: { id: string; label: string; hint: string; defaultOn?: boolean }[] = [
  { id: "Order", label: "Order（订单）", hint: "工单编号、状态、SLA、负责人", defaultOn: true },
  { id: "Device", label: "Device（设备）", hint: "设备编号、位置、健康度、维保记录", defaultOn: true },
  { id: "WorkOrder", label: "WorkOrder（工单）", hint: "工单类型、优先级、处理人" },
  { id: "KnowledgeDoc", label: "KnowledgeDoc（知识文档）", hint: "Wiki 知识库关联文档" },
];

export const WIZARD_BUILTIN_TOOLS: { name: string; desc: string; defaultOn?: boolean }[] = [
  { name: "Object Query · 对象查询", desc: "读取本体数据的基础能力", defaultOn: true },
  { name: "Request Clarification · 澄清追问", desc: "向用户追问不明确的参数", defaultOn: true },
  { name: "Action · 动作执行", desc: "写回操作（需 HITL 审批）" },
  { name: "Function · 函数调用", desc: "调用 AIP Logic 注册的函数" },
];

export const WIZARD_EXTERNAL_TOOLS: {
  name: string;
  desc: string;
  badge: string;
  badgeTone: "ok" | "warn" | "bad";
  disabled?: boolean;
}[] = [
  { name: "PDF 解析器", desc: "提取 PDF 文本/表格/图片 · C1 Job", badge: "已扫描", badgeTone: "ok" },
  { name: "数据清洗引擎", desc: "去重/标准化/异常值检测 · C1 Job", badge: "已扫描", badgeTone: "ok" },
  { name: "邮件发送服务", desc: "SMTP/API 发送通知邮件 · C0 Sync", badge: "已扫描", badgeTone: "ok" },
  { name: "图表生成器", desc: "从数据集生成可视化图表 · C1 Job", badge: "已扫描", badgeTone: "ok" },
  { name: "Web 搜索", desc: "需先完成安全扫描方可启用", badge: "待扫描", badgeTone: "warn", disabled: true },
  { name: "代码沙箱执行", desc: "需管理员审批 · 检测到 eval() 调用", badge: "P1 风险", badgeTone: "bad", disabled: true },
];

export type MaturityLevel = "L0" | "L1" | "L2" | "L3" | "L4";

export const WIZARD_MATURITY_LEVELS: {
  id: MaturityLevel;
  title: string;
  desc: string;
  recommended?: boolean;
  risk?: boolean;
}[] = [
  { id: "L0", title: "只读问答", desc: "仅查询 Object/Wiki，不做任何写回。适合知识检索型 Agent。" },
  { id: "L1", title: "Draft 暂存", desc: "写操作自动进入 Draft 审批台，人工审批后才生效。" },
  {
    id: "L2",
    title: "HITL 人机协同",
    desc: "写操作执行前弹出确认窗口，人工一键批准。适合大多数业务场景。",
    recommended: true,
  },
  { id: "L3", title: "Capability 委托", desc: "通过 Capability 接入其他智能体执行写操作。需要被委托智能体已发布。" },
  {
    id: "L4",
    title: "无人值守写回",
    desc: "全自动执行写回，无需人工确认。须 Evals 门控全绿方可启用。",
    risk: true,
  },
];

export const MATURITY_LEVEL_LABEL: Record<MaturityLevel, string> = {
  L0: "L0 只读",
  L1: "L1 Draft",
  L2: "L2 HITL",
  L3: "L3 Capability",
  L4: "L4 无人值守",
};
// -------------------- 来源筛选 --------------------

export const SOURCE_FILTERS = ["all", "platform", "plugin", "external"] as const;
export type SourceFilter = (typeof SOURCE_FILTERS)[number];

export const SOURCE_LABELS: Record<AgentSource, string> = {
  platform: "平台",
  plugin: "插件",
  external: "外部",
};

export const SOURCE_BADGE_STYLE: Record<
  AgentSource,
  { bg: string; text: string }
> = {
  platform: { bg: "#DBEAFE", text: "#1D4ED8" },
  plugin: { bg: "#F3E8FF", text: "#7C3AED" },
  external: { bg: "#F1F5F9", text: "#475569" },
};

/** 按关键词 + 来源 Tab 过滤 Agent 列表 */
export function filterAgents(
  agents: AgentItem[],
  filter: SourceFilter,
  keyword: string,
): AgentItem[] {
  const kw = keyword.trim().toLowerCase();
  return agents.filter((a) => {
    if (filter !== "all" && a.source !== filter) return false;
    if (!kw) return true;
    return (
      a.name.toLowerCase().includes(kw) ||
      a.description.toLowerCase().includes(kw) ||
      a.id.toLowerCase().includes(kw)
    );
  });
}

// -------------------- 状态徽章 --------------------

export function statusLabel(s: AgentStatus): string {
  return s === "active" ? "运行中" : s === "draft" ? "Draft" : "已停用";
}

export function statusStyle(
  s: AgentStatus,
): { bg: string; text: string } {
  if (s === "active") return { bg: "#DCFCE7", text: "#15803D" };
  if (s === "draft") return { bg: "#FEF3C7", text: "#B45309" };
  return { bg: "#E5E7EB", text: "#6B7280" };
}

// -------------------- 工具箱 / HITL --------------------

export const TOOL_KIND_LABEL: Record<ToolKind, string> = {
  API: "API",
  Function: "Function",
  MCP: "MCP",
  HTTP: "HTTP",
};

export const TOOL_KIND_STYLE: Record<
  ToolKind,
  { bg: string; text: string }
> = {
  API: { bg: "#DBEAFE", text: "#1D4ED8" },
  Function: { bg: "#FEF3C7", text: "#B45309" },
  MCP: { bg: "#F3E8FF", text: "#7C3AED" },
  HTTP: { bg: "#F1F5F9", text: "#475569" },
};

/** 工具开关状态 → 徽章文案 */
export function toolStateLabel(state: ToolState): string {
  switch (state) {
    case "on":
      return "已开启";
    case "recommended":
      return "★ 推荐";
    case "disabled":
      return "已禁用";
    case "hitl":
      return "确认中";
  }
}

/** 工具开关状态 → 徽章配色 */
export function toolStateStyle(
  state: ToolState,
): { bg: string; text: string } {
  switch (state) {
    case "on":
      return { bg: "#DCFCE7", text: "#15803D" };
    case "recommended":
      return { bg: "#FFEDD5", text: "#EA580C" };
    case "disabled":
      return { bg: "#F3F4F6", text: "#6B7280" };
    case "hitl":
      return { bg: "#FEF3C7", text: "#B45309" };
  }
}

/** HITL 脉冲动画的 CSS keyframes 名（测试可断言） */
export const HITL_PULSE_ANIMATION_NAME = "aos-hitl-pulse";

/** 注入 HITL 脉冲动画的 <style> 文本 */
export const HITL_PULSE_STYLE_TEXT = `
@keyframes ${HITL_PULSE_ANIMATION_NAME} {
  0%, 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.55); }
  50%      { box-shadow: 0 0 0 6px rgba(245, 158, 11, 0); }
}
.${HITL_PULSE_ANIMATION_NAME} {
  animation: ${HITL_PULSE_ANIMATION_NAME} 1.4s ease-in-out infinite;
}
`;

/** 判断某工具是否处于 HITL 确认中状态（用于驱动脉冲动画） */
export function isHitlPending(tool: AgentTool): boolean {
  return tool.state === "hitl";
}

/** 切换工具开关（disabled ↔ on），HITL 态不可直接关闭需先批准 */
export function toggleTool(tool: AgentTool): AgentTool {
  if (tool.state === "hitl") return tool; // 确认中不能直接切
  if (tool.state === "on") return { ...tool, state: "disabled" };
  if (tool.state === "disabled") return { ...tool, state: "on" };
  // recommended 切到 on
  return { ...tool, state: "on" };
}

/** 批准 HITL 调用：从 hitl 转为 on，清空 callId */
export function approveHitl(tool: AgentTool): AgentTool {
  if (tool.state !== "hitl") return tool;
  return { ...tool, state: "on", hitlCallId: undefined };
}

/** 拒绝 HITL 调用：回到 disabled */
export function rejectHitl(tool: AgentTool): AgentTool {
  if (tool.state !== "hitl") return tool;
  return { ...tool, state: "disabled", hitlCallId: undefined };
}

/** 统计工具箱中各状态的数量 */
export function countToolStates(
  tools: AgentTool[],
): { on: number; recommended: number; disabled: number; hitl: number } {
  const acc = { on: 0, recommended: 0, disabled: 0, hitl: 0 };
  for (const t of tools) {
    acc[t.state] += 1;
  }
  return acc;
}

// -------------------- 系统提示词变量插值 --------------------

/** ${user.name} / ${context.foo} / ${user.order}.bar 形式 */
const VAR_RE = /\$\{(?<scope>user|context)\.(?<key>[a-zA-Z_][\w]*)\}/g;

export interface PromptVar {
  scope: "user" | "context";
  key: string;
  raw: string; // 形如 "${user.name}"
}

/** 从提示词文本中提取所有 ${user.x} / ${context.x} 变量引用 */
export function extractPromptVars(prompt: string): PromptVar[] {
  const out: PromptVar[] = [];
  for (const m of prompt.matchAll(VAR_RE)) {
    const scope = (m.groups?.scope ?? "user") as "user" | "context";
    const key = m.groups?.key ?? "";
    if (!key) continue;
    out.push({ scope, key, raw: m[0] });
  }
  // 去重（同 raw 只保留一次）
  const seen = new Set<string>();
  const uniq: PromptVar[] = [];
  for (const v of out) {
    if (seen.has(v.raw)) continue;
    seen.add(v.raw);
    uniq.push(v);
  }
  return uniq;
}

/**
 * 用变量字典渲染提示词，未提供的变量保留原 ${...} 占位。
 * 例：renderPrompt("Hi ${user.name}", { user: { name: "张三" } }) → "Hi 张三"
 */
export function renderPrompt(
  prompt: string,
  vars: { user?: Record<string, unknown>; context?: Record<string, unknown> },
): string {
  return prompt.replace(VAR_RE, (full, scope: string, key: string) => {
    const bag = scope === "user" ? vars.user : vars.context;
    const val = bag?.[key];
    if (val == null) return full;
    return String(val);
  });
}

// -------------------- 向导校验 --------------------

export interface WizardDraft {
  name: string;
  description: string;
  icon: string;
  domain: string;
  source: AgentSource;
  modelId: string;
  prompt: string;
  ontology: string[];
  level: MaturityLevel;
  guardNoInvent: boolean;
  guardAutoDraft: boolean;
}

export function emptyWizardDraft(defaultModelId = ""): WizardDraft {
  return {
    name: "",
    description: "",
    icon: "chat",
    domain: "设备运维",
    source: "platform",
    modelId: defaultModelId,
    prompt: "",
    ontology: WIZARD_ONTOLOGY_OPTIONS.filter((o) => o.defaultOn).map((o) => o.id),
    level: "L2",
    guardNoInvent: true,
    guardAutoDraft: true,
  };
}

/** Step 1 基础信息：name 3-20、icon、业务域 */
export function validateStep1(draft: WizardDraft): string[] {
  const errs: string[] = [];
  const name = draft.name.trim();
  if (name.length < 3 || name.length > 20) {
    errs.push("名称长度须为 3-20 个字符");
  }
  if (!draft.icon) errs.push("请选择一个图标");
  if (!draft.domain.trim()) errs.push("请选择业务域");
  return errs;
}

/** Step 2 能力配置：modelId、prompt */
export function validateStep2(draft: WizardDraft): string[] {
  const errs: string[] = [];
  if (!draft.modelId) errs.push("请选择一个 LLM 模型");
  if (draft.prompt.trim().length < 5) {
    errs.push("系统提示词至少 5 个字符");
  }
  return errs;
}

/** Step 3 安全等级 */
export function validateStep3(draft: WizardDraft): string[] {
  const errs: string[] = [];
  if (!draft.level) errs.push("请选择成熟度等级");
  return errs;
}

/** 整个 draft 是否可创建 */
export function canCreateAgent(draft: WizardDraft): boolean {
  return [
    ...validateStep1(draft),
    ...validateStep2(draft),
    ...validateStep3(draft),
  ].length === 0;
}

/** 把 draft 转成 AgentItem（新建落库用） */
export function draftToAgent(
  draft: WizardDraft,
  idGen: () => string,
): AgentItem {
  return {
    id: idGen(),
    name: draft.name.trim(),
    description: draft.description.trim(),
    source: draft.source,
    status: "draft",
    calls: 0,
    modelId: draft.modelId,
    prompt: draft.prompt,
    icon: draft.icon,
    tools: [],
    domain: draft.domain,
    level: draft.level,
  };
}

export function modelDisplayName(m: CatalogModel): string {
  return m.label || m.id;
}

export function modelDisplayBlurb(m: CatalogModel): string {
  if (m.blurb) return m.blurb;
  const kind = (m.kind ?? "text") === "text" ? "文本" : String(m.kind);
  return `${kind} · ${m.provider || "默认供应商"}`;
}

export function levelSummaryLabel(level: MaturityLevel): string {
  const row = WIZARD_MATURITY_LEVELS.find((l) => l.id === level);
  return row ? `${level} · ${row.title}` : level;
}

// -------------------- 调用次数格式化 --------------------

/** 1234 → "1,234"；超过万用「万」单位 */
export function formatCalls(n: number): string {
  if (n >= 10000) {
    const w = n / 10000;
    return `${w.toFixed(w >= 10 ? 0 : 1)}万`;
  }
  return n.toLocaleString("en-US");
}

// -------------------- 模型目录解析 --------------------

/**
 * 把后端 /v1/aip/models 的返回归一成 CatalogModel[]。
 * 兼容 {items: [...]}、直接数组、空。
 */
export function parseModelsPayload(payload: unknown): CatalogModel[] {
  if (!payload) return [];
  const items =
    Array.isArray(payload) ? payload : (payload as { items?: unknown }).items;
  if (!Array.isArray(items)) return [];
  return items
    .map((m): CatalogModel | null => {
      if (!m || typeof m !== "object") return null;
      const id = String((m as { id?: unknown }).id ?? "").trim();
      if (!id) return null;
      return {
        id,
        kind: String((m as { kind?: unknown }).kind ?? "text"),
        ready: Boolean((m as { ready?: unknown }).ready ?? true),
        provider: String((m as { provider?: unknown }).provider ?? ""),
      };
    })
    .filter((m): m is CatalogModel => m !== null);
}

/** 从 Agent 详情或模型列表中，给出当前 Agent 的模型显示文案 */
export function resolveModelLabel(
  agent: AgentItem,
  models: CatalogModel[],
): string {
  const m = models.find((x) => x.id === agent.modelId);
  if (m && m.provider) return `${m.id} · ${m.provider}`;
  return agent.modelId;
}

// -------------------- 试运行（离线 mock 回复） --------------------

/** 根据用户输入 + Agent 配置生成 mock 回复（前端无 SSE 时的兜底） */
export function generateTrialReply(
  agent: AgentItem,
  userText: string,
): string {
  const t = userText.trim();
  // 优先按 agent.id 路由（避免订单文本在风险 Agent 下误命中）
  if (agent.id.includes("order")) {
    return `已读取 Order 对象与 Wiki.sla。建议：派单维修 → 进入 Draft（${agent.name} 示意回复）。`;
  }
  if (agent.id.includes("risk")) {
    return `风险评分 72/100（中危）。已推送告警，等待 HITL 确认。`;
  }
  if (agent.id.includes("doc")) {
    return `从 Wiki 检索到 3 条相关条目。根据 ${agent.name} 配置，仅展示结构化字段。`;
  }
  // 文本兜底分支：按用户输入关键词匹配
  if (t.includes("订单")) {
    return `已读取 Order 对象与 Wiki.sla。建议：派单维修 → 进入 Draft（${agent.name} 示意回复）。`;
  }
  if (t.includes("风险")) {
    return `风险评分 72/100（中危）。已推送告警，等待 HITL 确认。`;
  }
  if (t.includes("文档")) {
    return `从 Wiki 检索到 3 条相关条目。根据 ${agent.name} 配置，仅展示结构化字段。`;
  }
  // 通用兜底：带上 agent 名字 + 用户输入片段
  const snip = t.length > 40 ? t.slice(0, 40) + "…" : t;
  return `[${agent.name}] 收到「${snip}」。我已按提示词规则处理（mock 回复）。`;
}
