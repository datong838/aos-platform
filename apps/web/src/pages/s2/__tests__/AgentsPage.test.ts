import { describe, expect, it } from "vitest";
import {
  // 数据
  MOCK_AGENTS,
  MOCK_MODELS,
  SOURCE_LABELS,
  HITL_PULSE_ANIMATION_NAME,
  HITL_PULSE_STYLE_TEXT,
  // 过滤
  filterAgents,
  // 状态徽章
  statusLabel,
  statusStyle,
  toolStateLabel,
  toolStateStyle,
  // HITL
  isHitlPending,
  toggleTool,
  approveHitl,
  rejectHitl,
  countToolStates,
  // 变量插值
  extractPromptVars,
  renderPrompt,
  // 向导校验
  validateStep1,
  validateStep2,
  canCreateAgent,
  draftToAgent,
  // 格式化
  formatCalls,
  // 模型解析
  parseModelsPayload,
  resolveModelLabel,
  // 试运行
  generateTrialReply,
  type AgentItem,
  type AgentTool,
  type WizardDraft,
} from "../agentsCore";

// ==================== MOCK 数据完整性 ====================

describe("Phase 2 · MOCK 数据", () => {
  it("MOCK_AGENTS 覆盖 platform/plugin/external 三类来源", () => {
    const sources = new Set(MOCK_AGENTS.map((a) => a.source));
    expect(sources.has("platform")).toBe(true);
    expect(sources.has("plugin")).toBe(true);
    expect(sources.has("external")).toBe(true);
  });

  it("每个 MOCK Agent 有 id/name/prompt/tools", () => {
    for (const a of MOCK_AGENTS) {
      expect(a.id).toBeTruthy();
      expect(a.name).toBeTruthy();
      expect(a.prompt.length).toBeGreaterThan(0);
      expect(Array.isArray(a.tools)).toBe(true);
    }
  });

  it("MOCK_MODELS 至少有 3 个", () => {
    expect(MOCK_MODELS.length).toBeGreaterThanOrEqual(3);
    for (const m of MOCK_MODELS) {
      expect(m.id).toBeTruthy();
    }
  });
});

// ==================== 来源筛选 ====================

describe("Phase 2 · filterAgents", () => {
  it("all 过滤返回全部", () => {
    const r = filterAgents(MOCK_AGENTS, "all", "");
    expect(r.length).toBe(MOCK_AGENTS.length);
  });

  it("platform 只返回 platform 来源", () => {
    const r = filterAgents(MOCK_AGENTS, "platform", "");
    expect(r.every((a) => a.source === "platform")).toBe(true);
    expect(r.length).toBeGreaterThan(0);
  });

  it("plugin 只返回 plugin 来源", () => {
    const r = filterAgents(MOCK_AGENTS, "plugin", "");
    expect(r.every((a) => a.source === "plugin")).toBe(true);
  });

  it("external 只返回 external 来源", () => {
    const r = filterAgents(MOCK_AGENTS, "external", "");
    expect(r.every((a) => a.source === "external")).toBe(true);
  });

  it("关键词按名称匹配", () => {
    const r = filterAgents(MOCK_AGENTS, "all", "订单");
    expect(r.length).toBe(1);
    expect(r[0].name).toContain("订单");
  });

  it("关键词按描述匹配（大小写不敏感）", () => {
    const r = filterAgents(MOCK_AGENTS, "all", "ERP");
    expect(r.length).toBe(1);
    expect(r[0].id).toBe("ag-erp-bridge");
  });

  it("关键词按 id 匹配", () => {
    const r = filterAgents(MOCK_AGENTS, "all", "ag-risk");
    expect(r.length).toBe(1);
    expect(r[0].id).toBe("ag-risk-scan");
  });

  it("来源 + 关键词组合生效", () => {
    const r = filterAgents(MOCK_AGENTS, "plugin", "视频");
    expect(r.length).toBe(1);
    expect(r[0].source).toBe("plugin");
    expect(r[0].name).toContain("短视频");
  });

  it("无匹配返回空数组", () => {
    const r = filterAgents(MOCK_AGENTS, "all", "不存在的关键词xyz");
    expect(r).toEqual([]);
  });

  it("空白关键词不筛选", () => {
    const r1 = filterAgents(MOCK_AGENTS, "all", "   ");
    expect(r1.length).toBe(MOCK_AGENTS.length);
  });
});

// ==================== 来源标签 ====================

describe("Phase 2 · SOURCE_LABELS", () => {
  it("三种来源都有标签", () => {
    expect(SOURCE_LABELS.platform).toBe("平台");
    expect(SOURCE_LABELS.plugin).toBe("插件");
    expect(SOURCE_LABELS.external).toBe("外部");
  });
});

// ==================== 状态徽章 ====================

describe("Phase 2 · 状态徽章", () => {
  it("statusLabel 三种状态", () => {
    expect(statusLabel("active")).toBe("运行中");
    expect(statusLabel("draft")).toBe("Draft");
    expect(statusLabel("stopped")).toBe("已停用");
  });

  it("statusStyle active 绿色", () => {
    const s = statusStyle("active");
    expect(s.text).toBe("#15803D");
  });

  it("statusStyle draft 黄色", () => {
    const s = statusStyle("draft");
    expect(s.text).toBe("#B45309");
  });

  it("statusStyle stopped 灰色", () => {
    const s = statusStyle("stopped");
    expect(s.text).toBe("#6B7280");
  });
});

// ==================== 工具状态 ====================

describe("Phase 2 · 工具状态徽章", () => {
  it("toolStateLabel 四种状态", () => {
    expect(toolStateLabel("on")).toBe("已开启");
    expect(toolStateLabel("recommended")).toBe("★ 推荐");
    expect(toolStateLabel("disabled")).toBe("已禁用");
    expect(toolStateLabel("hitl")).toBe("确认中");
  });

  it("toolStateStyle on 绿色", () => {
    expect(toolStateStyle("on").text).toBe("#15803D");
  });

  it("toolStateStyle recommended 橙色", () => {
    expect(toolStateStyle("recommended").text).toBe("#EA580C");
  });

  it("toolStateStyle hitl 黄色", () => {
    expect(toolStateStyle("hitl").text).toBe("#B45309");
  });

  it("toolStateStyle disabled 灰色", () => {
    expect(toolStateStyle("disabled").text).toBe("#6B7280");
  });
});

// ==================== HITL 脉冲 ====================

describe("Phase 2 · HITL 脉冲动画", () => {
  it("动画 keyframes 名定义", () => {
    expect(HITL_PULSE_ANIMATION_NAME).toBe("aos-hitl-pulse");
  });

  it("样式文本包含动画定义", () => {
    expect(HITL_PULSE_STYLE_TEXT).toContain("@keyframes aos-hitl-pulse");
    expect(HITL_PULSE_STYLE_TEXT).toContain("box-shadow");
    expect(HITL_PULSE_STYLE_TEXT).toContain("animation");
    expect(HITL_PULSE_STYLE_TEXT).toContain("infinite");
  });

  it("isHitlPending：仅 hitl 态返回 true", () => {
    const mk = (state: AgentTool["state"]): AgentTool => ({
      id: "x",
      name: "x",
      kind: "API",
      state,
    });
    expect(isHitlPending(mk("hitl"))).toBe(true);
    expect(isHitlPending(mk("on"))).toBe(false);
    expect(isHitlPending(mk("disabled"))).toBe(false);
    expect(isHitlPending(mk("recommended"))).toBe(false);
  });
});

// ==================== 工具开关切换 ====================

describe("Phase 2 · toggleTool", () => {
  const mk = (state: AgentTool["state"]): AgentTool => ({
    id: "x",
    name: "x",
    kind: "API",
    state,
  });

  it("on → disabled", () => {
    expect(toggleTool(mk("on")).state).toBe("disabled");
  });

  it("disabled → on", () => {
    expect(toggleTool(mk("disabled")).state).toBe("on");
  });

  it("recommended → on", () => {
    expect(toggleTool(mk("recommended")).state).toBe("on");
  });

  it("hitl 不可直接切换（保持原样）", () => {
    const t = mk("hitl");
    expect(toggleTool(t)).toEqual(t);
  });
});

describe("Phase 2 · approveHitl", () => {
  it("hitl → on，清空 callId", () => {
    const t: AgentTool = {
      id: "x",
      name: "x",
      kind: "Function",
      state: "hitl",
      hitlCallId: "call_123",
    };
    const r = approveHitl(t);
    expect(r.state).toBe("on");
    expect(r.hitlCallId).toBeUndefined();
  });

  it("非 hitl 态不受影响", () => {
    const t: AgentTool = { id: "x", name: "x", kind: "API", state: "on" };
    expect(approveHitl(t)).toEqual(t);
  });
});

describe("Phase 2 · rejectHitl", () => {
  it("hitl → disabled，清空 callId", () => {
    const t: AgentTool = {
      id: "x",
      name: "x",
      kind: "Function",
      state: "hitl",
      hitlCallId: "call_456",
    };
    const r = rejectHitl(t);
    expect(r.state).toBe("disabled");
    expect(r.hitlCallId).toBeUndefined();
  });

  it("非 hitl 态不受影响", () => {
    const t: AgentTool = { id: "x", name: "x", kind: "API", state: "on" };
    expect(rejectHitl(t)).toEqual(t);
  });
});

describe("Phase 2 · countToolStates", () => {
  it("正确统计各状态数量", () => {
    const tools: AgentTool[] = [
      { id: "1", name: "a", kind: "API", state: "on" },
      { id: "2", name: "b", kind: "API", state: "on" },
      { id: "3", name: "c", kind: "API", state: "recommended" },
      { id: "4", name: "d", kind: "API", state: "disabled" },
      { id: "5", name: "e", kind: "API", state: "hitl" },
    ];
    const c = countToolStates(tools);
    expect(c.on).toBe(2);
    expect(c.recommended).toBe(1);
    expect(c.disabled).toBe(1);
    expect(c.hitl).toBe(1);
  });

  it("空列表返回全 0", () => {
    const c = countToolStates([]);
    expect(c).toEqual({ on: 0, recommended: 0, disabled: 0, hitl: 0 });
  });
});

// ==================== 变量插值 ====================

describe("Phase 2 · extractPromptVars", () => {
  it("提取 user 变量", () => {
    const v = extractPromptVars("你好 ${user.name}");
    expect(v).toHaveLength(1);
    expect(v[0].scope).toBe("user");
    expect(v[0].key).toBe("name");
    expect(v[0].raw).toBe("${user.name}");
  });

  it("提取 context 变量", () => {
    const v = extractPromptVars("读取 ${context.wiki}");
    expect(v).toHaveLength(1);
    expect(v[0].scope).toBe("context");
    expect(v[0].key).toBe("wiki");
  });

  it("同时提取 user + context", () => {
    const v = extractPromptVars("${user.name} 访问 ${context.wiki}.sla");
    expect(v).toHaveLength(2);
    const scopes = v.map((x) => x.scope).sort();
    expect(scopes).toEqual(["context", "user"]);
  });

  it("重复变量去重", () => {
    const v = extractPromptVars("${user.name} 和 ${user.name} 是同一人");
    expect(v).toHaveLength(1);
  });

  it("无变量返回空数组", () => {
    expect(extractPromptVars("普通文本无变量")).toEqual([]);
  });

  it("点号后的非法字符不匹配", () => {
    expect(extractPromptVars("${user.123}")).toEqual([]);
    expect(extractPromptVars("${user.}")).toEqual([]);
  });

  it("不支持 user/context 之外的 scope", () => {
    expect(extractPromptVars("${system.foo}")).toEqual([]);
  });
});

describe("Phase 2 · renderPrompt", () => {
  it("替换 user 变量", () => {
    expect(
      renderPrompt("你好 ${user.name}", { user: { name: "张三" } }),
    ).toBe("你好 张三");
  });

  it("替换 context 变量", () => {
    expect(
      renderPrompt("读取 ${context.sla}", { context: { sla: "24h" } }),
    ).toBe("读取 24h");
  });

  it("同时替换 user + context", () => {
    expect(
      renderPrompt("${user.name} → ${context.wiki}", {
        user: { name: "李四" },
        context: { wiki: "WikiDoc" },
      }),
    ).toBe("李四 → WikiDoc");
  });

  it("未提供的变量保留原 ${...} 占位", () => {
    expect(renderPrompt("${user.name} 未知", {})).toBe("${user.name} 未知");
  });

  it("null / undefined 值保留占位", () => {
    expect(
      renderPrompt("${user.x}", { user: { x: undefined } }),
    ).toBe("${user.x}");
  });

  it("数字值转成字符串", () => {
    expect(
      renderPrompt("数量 ${context.count}", { context: { count: 42 } }),
    ).toBe("数量 42");
  });

  it("链式 ${user.order}.bar 只匹配 ${user.order} 部分", () => {
    expect(
      renderPrompt("${user.order}.status", { user: { order: "ORD-1" } }),
    ).toBe("ORD-1.status");
  });
});

// ==================== 向导校验 ====================

const VALID_DRAFT: WizardDraft = {
  name: "测试助手",
  description: "测试",
  icon: "💬",
  source: "platform",
  modelId: "glm-4-plus",
  prompt: "你是测试助手。",
};

describe("Phase 2 · validateStep1", () => {
  it("合法 draft 无错误", () => {
    expect(validateStep1(VALID_DRAFT)).toEqual([]);
  });

  it("名称太短", () => {
    expect(
      validateStep1({ ...VALID_DRAFT, name: "ab" }),
    ).toContain("名称长度须为 3-20 个字符");
  });

  it("名称太长", () => {
    expect(
      validateStep1({ ...VALID_DRAFT, name: "a".repeat(21) }),
    ).toContain("名称长度须为 3-20 个字符");
  });

  it("名称恰好 3 字符通过", () => {
    expect(validateStep1({ ...VALID_DRAFT, name: "abc" })).toEqual([]);
  });

  it("名称恰好 20 字符通过", () => {
    expect(validateStep1({ ...VALID_DRAFT, name: "a".repeat(20) })).toEqual([]);
  });

  it("名称两端空白被 trim", () => {
    expect(validateStep1({ ...VALID_DRAFT, name: "  测试助手  " })).toEqual([]);
  });

  it("未选图标报错", () => {
    expect(
      validateStep1({ ...VALID_DRAFT, icon: "" }),
    ).toContain("请选择一个图标");
  });
});

describe("Phase 2 · validateStep2", () => {
  it("合法 draft 无错误", () => {
    expect(validateStep2(VALID_DRAFT)).toEqual([]);
  });

  it("未选模型报错", () => {
    expect(
      validateStep2({ ...VALID_DRAFT, modelId: "" }),
    ).toContain("请选择一个 LLM 模型");
  });

  it("提示词太短", () => {
    expect(
      validateStep2({ ...VALID_DRAFT, prompt: "ab" }),
    ).toContain("系统提示词至少 5 个字符");
  });

  it("提示词为空白报错", () => {
    expect(
      validateStep2({ ...VALID_DRAFT, prompt: "     " }),
    ).toContain("系统提示词至少 5 个字符");
  });
});

describe("Phase 2 · canCreateAgent", () => {
  it("合法 draft 返回 true", () => {
    expect(canCreateAgent(VALID_DRAFT)).toBe(true);
  });

  it("名称非法返回 false", () => {
    expect(canCreateAgent({ ...VALID_DRAFT, name: "x" })).toBe(false);
  });

  it("无模型返回 false", () => {
    expect(canCreateAgent({ ...VALID_DRAFT, modelId: "" })).toBe(false);
  });

  it("无图标返回 false", () => {
    expect(canCreateAgent({ ...VALID_DRAFT, icon: "" })).toBe(false);
  });
});

describe("Phase 2 · draftToAgent", () => {
  it("把 draft 转成 AgentItem，初始状态为 draft", () => {
    const a = draftToAgent(VALID_DRAFT, () => "ag-test-1");
    expect(a.id).toBe("ag-test-1");
    expect(a.name).toBe("测试助手");
    expect(a.status).toBe("draft");
    expect(a.calls).toBe(0);
    expect(a.tools).toEqual([]);
    expect(a.source).toBe("platform");
  });

  it("description 被 trim", () => {
    const a = draftToAgent(
      { ...VALID_DRAFT, description: "  带空白的描述  " },
      () => "ag-x",
    );
    expect(a.description).toBe("带空白的描述");
  });

  it("使用 idGen 生成不同 id", () => {
    let n = 0;
    const gen = () => `ag-${++n}`;
    const a1 = draftToAgent(VALID_DRAFT, gen);
    const a2 = draftToAgent(VALID_DRAFT, gen);
    expect(a1.id).toBe("ag-1");
    expect(a2.id).toBe("ag-2");
  });
});

// ==================== formatCalls ====================

describe("Phase 2 · formatCalls", () => {
  it("小于万的数字加千分位", () => {
    expect(formatCalls(1234)).toBe("1,234");
    expect(formatCalls(0)).toBe("0");
    expect(formatCalls(999)).toBe("999");
  });

  it("达到万用万单位", () => {
    expect(formatCalls(10000)).toBe("1.0万");
    expect(formatCalls(12345)).toBe("1.2万");
  });

  it("超过 10 万省略小数", () => {
    expect(formatCalls(100000)).toBe("10万");
    expect(formatCalls(999999)).toBe("100万");
  });
});

// ==================== parseModelsPayload ====================

describe("Phase 2 · parseModelsPayload", () => {
  it("解析 {items: [...]} 形式", () => {
    const r = parseModelsPayload({
      items: [{ id: "m1", kind: "text" }, { id: "m2", kind: "image" }],
    });
    expect(r).toHaveLength(2);
    expect(r[0].id).toBe("m1");
    expect(r[1].kind).toBe("image");
  });

  it("解析数组形式", () => {
    const r = parseModelsPayload([{ id: "m1" }, { id: "m2" }]);
    expect(r).toHaveLength(2);
  });

  it("过滤掉无 id 的条目", () => {
    const r = parseModelsPayload({ items: [{ id: "" }, { id: "m1" }, {}] });
    expect(r).toHaveLength(1);
    expect(r[0].id).toBe("m1");
  });

  it("null / undefined 返回空数组", () => {
    expect(parseModelsPayload(null)).toEqual([]);
    expect(parseModelsPayload(undefined)).toEqual([]);
  });

  it("非数组 items 返回空数组", () => {
    expect(parseModelsPayload({ items: "not array" })).toEqual([]);
    expect(parseModelsPayload({})).toEqual([]);
  });

  it("ready 字段默认 true", () => {
    const r = parseModelsPayload([{ id: "m1" }]);
    expect(r[0].ready).toBe(true);
  });

  it("provider 字段默认空串", () => {
    const r = parseModelsPayload([{ id: "m1" }]);
    expect(r[0].provider).toBe("");
  });
});

// ==================== resolveModelLabel ====================

describe("Phase 2 · resolveModelLabel", () => {
  const agent: AgentItem = {
    id: "a1",
    name: "A",
    description: "",
    source: "platform",
    status: "active",
    calls: 0,
    modelId: "glm-4-plus",
    prompt: "",
    icon: "💬",
    tools: [],
  };

  it("模型列表命中：返回 id · provider", () => {
    const r = resolveModelLabel(agent, [
      { id: "glm-4-plus", provider: "智谱" },
    ]);
    expect(r).toBe("glm-4-plus · 智谱");
  });

  it("模型列表未命中：返回裸 modelId", () => {
    const r = resolveModelLabel(agent, [{ id: "other" }]);
    expect(r).toBe("glm-4-plus");
  });

  it("模型列表为空：返回裸 modelId", () => {
    const r = resolveModelLabel(agent, []);
    expect(r).toBe("glm-4-plus");
  });

  it("provider 为空时不带 ·", () => {
    const r = resolveModelLabel(agent, [
      { id: "glm-4-plus", provider: "" },
    ]);
    expect(r).toBe("glm-4-plus");
  });
});

// ==================== generateTrialReply ====================

describe("Phase 2 · generateTrialReply", () => {
  const orderAgent = MOCK_AGENTS.find((a) => a.id === "ag-order-assist")!;
  const riskAgent = MOCK_AGENTS.find((a) => a.id === "ag-risk-scan")!;
  const docAgent = MOCK_AGENTS.find((a) => a.id === "ag-doc-qa")!;

  it("订单类回复包含 Order / Wiki.sla", () => {
    const r = generateTrialReply(orderAgent, "我的订单 ORD-123 怎么样了");
    expect(r).toContain("Order");
    expect(r).toContain("Wiki.sla");
  });

  it("agent.id 含 order 触发订单分支", () => {
    const r = generateTrialReply(orderAgent, "随便说点什么");
    expect(r).toContain("Order");
  });

  it("风险类回复包含风险评分", () => {
    const r = generateTrialReply(riskAgent, "这个订单有风险吗");
    expect(r).toContain("风险评分");
  });

  it("agent.id 含 risk 触发风险分支", () => {
    const r = generateTrialReply(riskAgent, "检查一下");
    expect(r).toContain("风险");
  });

  it("文档类回复包含 Wiki", () => {
    const r = generateTrialReply(docAgent, "帮我查文档");
    expect(r).toContain("Wiki");
  });

  it("兜底回复带 agent 名字", () => {
    const r = generateTrialReply(orderAgent, "xyz_random_query");
    expect(r).toContain(orderAgent.name);
  });

  it("兜底回复截断长输入", () => {
    const long = "这是一段非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的输入";
    // 用一个非 order/risk/doc 的 agent（取 ERP 桥接）才会走兜底分支
    const erpAgent = MOCK_AGENTS.find((a) => a.id === "ag-erp-bridge")!;
    const r = generateTrialReply(erpAgent, long);
    expect(r).toContain("…");
  });
});
