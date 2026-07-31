import { describe, expect, it } from "vitest";
import {
  MOCK_AGENTS,
  SOURCE_FILTERS,
  SOURCE_LABELS,
  filterAgents,
  statusLabel,
  statusStyle,
  toolStateLabel,
  toggleTool,
  approveHitl,
  rejectHitl,
  countToolStates,
  extractPromptVars,
  renderPrompt,
  validateStep1,
  validateStep2,
  canCreateAgent,
  draftToAgent,
  formatCalls,
  parseModelsPayload,
  generateTrialReply,
  type AgentItem,
  type AgentTool,
  type WizardDraft,
} from "./agentsCore";

// ─── MOCK 数据 ───

describe("AgentsPage · MOCK_AGENTS 初始数据", () => {
  it("有 5 个预设 Agent", () => {
    expect(MOCK_AGENTS).toHaveLength(5);
  });

  it("每个 Agent 有完整字段", () => {
    for (const a of MOCK_AGENTS) {
      expect(a.id.length).toBeGreaterThan(0);
      expect(a.name.length).toBeGreaterThan(0);
      expect(a.source.length).toBeGreaterThan(0);
      expect(a.status.length).toBeGreaterThan(0);
      expect(a.tools).toBeInstanceOf(Array);
    }
  });

  it("覆盖三种来源：platform/plugin/external", () => {
    const sources = new Set(MOCK_AGENTS.map((a) => a.source));
    expect(sources.has("platform")).toBe(true);
    expect(sources.has("plugin")).toBe(true);
    expect(sources.has("external")).toBe(true);
  });
});

// ─── filterAgents ───

describe("AgentsPage · filterAgents 过滤", () => {
  it("all 过滤器返回全部", () => {
    expect(filterAgents(MOCK_AGENTS, "all", "")).toHaveLength(5);
  });

  it("platform 过滤器只返回平台来源", () => {
    const items = filterAgents(MOCK_AGENTS, "platform", "");
    expect(items.every((a) => a.source === "platform")).toBe(true);
  });

  it("关键词搜索匹配名称", () => {
    const items = filterAgents(MOCK_AGENTS, "all", "订单");
    expect(items.length).toBeGreaterThan(0);
    expect(items[0].name).toContain("订单");
  });

  it("关键词搜索不匹配时返回空", () => {
    expect(filterAgents(MOCK_AGENTS, "all", "zzz_nonexistent")).toHaveLength(0);
  });
});

// ─── 状态徽章 ───

describe("AgentsPage · 状态标签和样式", () => {
  it("statusLabel 返回正确中文", () => {
    expect(statusLabel("active")).toBe("运行中");
    expect(statusLabel("draft")).toBe("Draft");
    expect(statusLabel("stopped")).toBe("已停用");
  });

  it("statusStyle 返回正确配色", () => {
    const active = statusStyle("active");
    expect(active.bg).toBeTruthy();
    expect(active.text).toBeTruthy();
  });

  it("SOURCE_LABELS 覆盖所有来源", () => {
    for (const sf of SOURCE_FILTERS) {
      if (sf === "all") continue;
      expect(SOURCE_LABELS[sf as keyof typeof SOURCE_LABELS]).toBeTruthy();
    }
  });
});

// ─── 工具箱/HITL ───

describe("AgentsPage · 工具状态管理", () => {
  it("toolStateLabel 返回正确文案", () => {
    expect(toolStateLabel("on")).toBe("已开启");
    expect(toolStateLabel("recommended")).toBe("★ 推荐");
    expect(toolStateLabel("disabled")).toBe("已禁用");
    expect(toolStateLabel("hitl")).toBe("确认中");
  });

  it("toggleTool: on → disabled", () => {
    const tool: AgentTool = { id: "t1", name: "T", kind: "API", state: "on" };
    expect(toggleTool(tool).state).toBe("disabled");
  });

  it("toggleTool: disabled → on", () => {
    const tool: AgentTool = { id: "t1", name: "T", kind: "API", state: "disabled" };
    expect(toggleTool(tool).state).toBe("on");
  });

  it("toggleTool: hitl 不可直接切换", () => {
    const tool: AgentTool = { id: "t1", name: "T", kind: "API", state: "hitl", hitlCallId: "c1" };
    expect(toggleTool(tool).state).toBe("hitl");
  });

  it("approveHitl: hitl → on", () => {
    const tool: AgentTool = { id: "t1", name: "T", kind: "API", state: "hitl", hitlCallId: "c1" };
    const approved = approveHitl(tool);
    expect(approved.state).toBe("on");
    expect(approved.hitlCallId).toBeUndefined();
  });

  it("rejectHitl: hitl → disabled", () => {
    const tool: AgentTool = { id: "t1", name: "T", kind: "API", state: "hitl", hitlCallId: "c1" };
    const rejected = rejectHitl(tool);
    expect(rejected.state).toBe("disabled");
    expect(rejected.hitlCallId).toBeUndefined();
  });

  it("countToolStates 正确统计各状态", () => {
    const tools: AgentTool[] = [
      { id: "1", name: "A", kind: "API", state: "on" },
      { id: "2", name: "B", kind: "Function", state: "on" },
      { id: "3", name: "C", kind: "MCP", state: "hitl", hitlCallId: "c" },
      { id: "4", name: "D", kind: "HTTP", state: "disabled" },
    ];
    const counts = countToolStates(tools);
    expect(counts.on).toBe(2);
    expect(counts.hitl).toBe(1);
    expect(counts.disabled).toBe(1);
  });
});

// ─── 提示词变量 ───

describe("AgentsPage · 提示词变量提取", () => {
  it("提取 ${user.x} 和 ${context.x}", () => {
    const vars = extractPromptVars("Hello ${user.name} from ${context.org}");
    expect(vars).toHaveLength(2);
    expect(vars[0].scope).toBe("user");
    expect(vars[0].key).toBe("name");
  });

  it("去重相同变量", () => {
    const vars = extractPromptVars("${user.name} ${user.name}");
    expect(vars).toHaveLength(1);
  });

  it("renderPrompt 替换变量", () => {
    const result = renderPrompt("Hi ${user.name}", { user: { name: "张三" } });
    expect(result).toBe("Hi 张三");
  });

  it("renderPrompt 保留未提供变量", () => {
    const result = renderPrompt("Hi ${user.unknown}", {});
    expect(result).toContain("${user.unknown}");
  });
});

// ─── 向导校验 ───

describe("AgentsPage · 向导校验", () => {
  const validDraft: WizardDraft = {
    name: "测试机器人",
    description: "",
    icon: "chat",
    domain: "设备运维",
    source: "platform",
    modelId: "glm-4-plus",
    prompt: "你是一个助手",
    ontology: ["Order", "Device"],
    level: "L2",
    guardNoInvent: true,
    guardAutoDraft: true,
  };

  it("validateStep1: 名称太短", () => {
    const errs = validateStep1({ ...validDraft, name: "ab" });
    expect(errs.length).toBeGreaterThan(0);
  });

  it("validateStep1: 有效名称通过", () => {
    const errs = validateStep1(validDraft);
    expect(errs).toHaveLength(0);
  });

  it("validateStep1: 缺少业务域", () => {
    const errs = validateStep1({ ...validDraft, domain: "" });
    expect(errs.length).toBeGreaterThan(0);
  });

  it("validateStep2: 缺少 modelId", () => {
    const errs = validateStep2({ ...validDraft, modelId: "" });
    expect(errs.length).toBeGreaterThan(0);
  });

  it("canCreateAgent: 完整 draft 返回 true", () => {
    expect(canCreateAgent(validDraft)).toBe(true);
  });

  it("draftToAgent: 生成 AgentItem", () => {
    const agent = draftToAgent(validDraft, () => "test-id");
    expect(agent.id).toBe("test-id");
    expect(agent.name).toBe("测试机器人");
    expect(agent.status).toBe("draft");
    expect(agent.domain).toBe("设备运维");
    expect(agent.level).toBe("L2");
  });
});

// ─── 格式化 & 模型解析 ───

describe("AgentsPage · formatCalls 调用次数格式化", () => {
  it("小于万的数字加千分位", () => {
    expect(formatCalls(1234)).toBe("1,234");
  });

  it("超过万使用万单位", () => {
    expect(formatCalls(15000)).toBe("1.5万");
  });

  it("十万以上取整", () => {
    expect(formatCalls(120000)).toBe("12万");
  });
});

describe("AgentsPage · parseModelsPayload 模型列表解析", () => {
  it("解析 {items: [...]} 格式", () => {
    const result = parseModelsPayload({ items: [{ id: "m1" }, { id: "m2" }] });
    expect(result).toHaveLength(2);
  });

  it("解析直接数组", () => {
    const result = parseModelsPayload([{ id: "m1" }]);
    expect(result).toHaveLength(1);
  });

  it("空/null 返回空数组", () => {
    expect(parseModelsPayload(null)).toHaveLength(0);
    expect(parseModelsPayload({})).toHaveLength(0);
  });
});

describe("AgentsPage · generateTrialReply 试运行回复", () => {
  const agent: AgentItem = MOCK_AGENTS[0];

  it("订单相关回复包含 Order", () => {
    const reply = generateTrialReply(agent, "查询订单");
    expect(reply.length).toBeGreaterThan(0);
  });

  it("空输入也有兜底回复", () => {
    const reply = generateTrialReply(agent, "");
    expect(reply.length).toBeGreaterThan(0);
  });
});
